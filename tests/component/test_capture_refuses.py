# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the seam between capture and delivery (015, SC-009b).

This is the clarified decision made into a row, and it is a decision about *asymmetry*, so
it needs both halves in one place to be legible:

- **Capture refuses.** An entry that could not be written locally means a step whose effect
  would exist with no record of it. That is the gap the whole platform exists to close, and
  `start_governed_run` has always behaved this way for AUTHORITY_ISSUED — this is the same
  rule one layer out.
- **Delivery never refuses.** A destination that is unreachable means an entry that exists
  in one place instead of two. That is a *narrower* window, not a missing record, and
  refusing runs over it would make an outage at the collector into an outage of the
  platform — trading a real availability loss for an evidence gain that is already bounded
  and already observable as backlog.

Written as one file rather than two because the tempting mistake is to treat these the same
— either refusing on both (which makes the second copy a single point of failure for
governed work) or refusing on neither (which is the silently-dropping emitter this feature
exists to retire). Neither error is visible if the two halves live apart.
"""

from __future__ import annotations

from typing import Any

from core.audit.egress import ship_pass
from core.audit.schema import AuditEntry
from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler
from tests.component.test_audit_egress import FakeDestination, _prepared
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    assert_denied_closed,
    assert_no_side_effect,
    fake_identity_fabric,
    frozen_clock,
)


class LocalAppendFails(InMemoryAuditSink):
    """The first copy is unwritable. Everything downstream of that is unrecorded."""

    def __init__(self, fail_after: int) -> None:
        super().__init__()
        self._fail_after = fail_after
        self._appends = 0

    def append_event(self, **kwargs: Any) -> AuditEntry:
        if self._appends >= self._fail_after:
            raise RuntimeError("the evidence store is unwritable")
        self._appends += 1
        return super().append_event(**kwargs)


def test_a_step_whose_entry_cannot_be_captured_is_refused() -> None:
    """FR-014, capture half — no effect without a record of it.

    The tool must not run. Asserting the denial alone would pass against an implementation
    that executed and then reported failure, which is the version that leaves exactly the
    unrecorded effect this rule exists to prevent.
    """
    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register("echo", handler)
    # 0 = authority_issued, 1 = run_start, 2+ = the invoke path.
    audit = LocalAppendFails(fail_after=2)

    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-capture-refuses",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fake_identity_fabric(tool_names={"echo"}),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )
    result = invoke_tool(run, "echo", {})

    assert_denied_closed(result, reason="internal_error")
    assert result.evidential_gap is True, "the refusal did not name the reason it happened"
    assert_no_side_effect(handler)


def test_a_destination_that_cannot_be_reached_refuses_nothing() -> None:
    """FR-014a, delivery half — availability is not traded for a narrower window.

    The entries are already captured; what failed is the second copy. Making runs wait on
    that would put a collector outage on the critical path of every governed step, and buy
    a property the backlog already reports honestly.
    """
    local, _ = _prepared(streams=2)
    destination = FakeDestination()
    destination.fail_next = True

    outcome = ship_pass(local=local, destination=destination)

    assert outcome.failures, "a delivery failure was not reported at all"
    assert outcome.shipped == 0
    # Nothing raised, nothing refused, and the shortfall is a number somebody can watch.
    assert outcome.backlog == 8
    assert local.watermarks == {}, "the watermark advanced past entries never delivered"
