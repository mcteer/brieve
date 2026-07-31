# SPDX-License-Identifier: Apache-2.0
"""A skipped step says so, and says why (ROADMAP gap 0c).

The hole this closes: a step records its result and *then* audits its outcome. Killed
between the two, the effect happened, is durably recorded, and has no entry in the trail —
and the resume correctly does not repeat it, so the entry was never going to appear later
either. The trail was short by one and nothing explained it.

These are hermetic because the property is about what the loop *writes*, not about surviving
a real kill. The kill itself is the enclave's job, and the row there now reconciles outcomes
against re-observations instead of bounding the gap.
"""

from __future__ import annotations

from typing import Any

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from surfaces.dispatch.entrypoint import _run_steps
from tests.harness import (
    DEFAULT_AGENT_DEFINITION_ID,
    fake_identity_fabric,
    frozen_clock,
)


class _Durability:
    """Records brackets and nothing else — the loop's only other collaborator."""

    def __init__(self) -> None:
        self.intents: list[int] = []

    def record_intent(self, record: Any) -> None:
        self.intents.append(record.step_index)

    def record_result(self, record: Any) -> None:
        return None

    def save(self, *_a: Any, **_k: Any) -> None:
        return None

    def load(self, *_a: Any, **_k: Any) -> Any:
        return None


def _run(skip: Any) -> tuple[InMemoryAuditSink, _Durability, list[int], list[int]]:
    audit = InMemoryAuditSink()
    run = start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-skip-records",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fake_identity_fabric(tool_names={"echo"}),
        clock=frozen_clock(),
        registry=ToolRegistry(),
        audit_sink=audit,
    )
    durability = _Durability()
    _, executed, skipped = _run_steps(
        run,
        durability=durability,
        blob_id="corr-skip-records",
        total_steps=5,
        tools=[],
        invoke_tools=False,
        skip_reason=skip,
    )
    return audit, durability, executed, skipped


def _reobserved(audit: InMemoryAuditSink) -> list[Any]:
    return [e for e in audit.all_entries() if e.event_type is AuditEventType.STEP_REOBSERVED]


def test_a_skipped_step_is_named_in_the_trail_with_its_reason() -> None:
    """The record an investigator reads instead of inferring from a count."""
    audit, _, executed, skipped = _run(lambda step: "result_recorded" if step in (1, 3) else None)

    assert executed == [0, 2, 4]
    assert skipped == [1, 3]

    entries = _reobserved(audit)
    assert [e.payload["step_index"] for e in entries] == [1, 3]
    assert {e.payload["reason"] for e in entries} == {"result_recorded"}


def test_the_reason_distinguishes_the_three_ways_a_step_can_be_already_done() -> None:
    """Three different claims, and collapsing them to "skipped" loses the difference.

    A closed result is the step's own record that it finished. Re-observation is a judgement
    about an open bracket. The checkpoint mark is a coarser backstop for steps that never
    bracketed at all. An investigator asking "how do you know?" gets a different answer for
    each, and a boolean would have given the same one.
    """
    reasons = {0: "below_checkpoint", 1: "reobserved_complete", 2: "result_recorded"}
    audit, _, _, _ = _run(lambda step: reasons.get(step))

    assert [(e.payload["step_index"], e.payload["reason"]) for e in _reobserved(audit)] == [
        (0, "below_checkpoint"),
        (1, "reobserved_complete"),
        (2, "result_recorded"),
    ]


def test_a_fresh_run_records_no_re_observations() -> None:
    """Nothing is already done on a first dispatch, so the trail says nothing about it.

    Worth pinning: an event emitted per step regardless of outcome would double the size of
    every run's trail to say "this ran normally", which the outcome already says.
    """
    audit, durability, executed, skipped = _run(lambda _step: None)

    assert executed == [0, 1, 2, 3, 4]
    assert skipped == []
    assert _reobserved(audit) == []
    assert durability.intents == [0, 1, 2, 3, 4]


def test_every_step_is_accounted_for_by_exactly_one_record() -> None:
    """The reconciliation the enclave row performs, asserted on the mechanism itself.

    **Within ONE allocation** — which is the part that partitions. Executed steps open an
    intent, skipped steps emit a re-observation, and no step does both. Across allocations
    the records overlap instead: a step the first allocation ran has an outcome, and the
    resumed allocation re-observes it. The enclave row asserts the weaker cross-allocation
    property for that reason, and an earlier draft of it asserted a partition and was wrong.
    """
    audit, durability, executed, skipped = _run(
        lambda step: "result_recorded" if step in (0, 4) else None
    )

    accounted = set(durability.intents) | {e.payload["step_index"] for e in _reobserved(audit)}
    assert accounted == set(range(5))
    assert set(executed).isdisjoint({e.payload["step_index"] for e in _reobserved(audit)})
