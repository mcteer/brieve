# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — deferral is real, and the posture is stated (D3, D8).

**D3 — the schema is withheld until the model asks.** Measured at the boundary the platform
owns: a deferred tool reaches the model request carrying `defer_loading=True` before any
search, and `False` after the search that disclosed it. That flag is what the provider
adapter acts on to keep the parameter schema off the wire.

*Recorded precisely because the spec's wording was looser than what is measurable.* SC-002
says an undisclosed tool "contributes its name and one-line description and nothing else".
At the framework boundary that is not assertable for a model whose profile supports native
tool search: the framework hands the full `ToolDefinition` and the flag, and the
provider-side adapter does the withholding on the wire. What the platform can assert — and
therefore what this row asserts — is the flag and its transition. Claiming to measure bytes
the platform never sees would be a row asserting something weaker than its name, which is
what ADR-0047 forbids.

**D8 — a run says which posture it is in** (FR-004). Eager and deferred are distinguishable
on the run's own record, and neither presents as the other.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic_ai.models.function import FunctionModel

from adapters.pydantic_ai.agent import build_governed_agent, start_adapter_run
from adapters.pydantic_ai.governance import deferred_toolset
from core.audit.schema import AuditEventType
from core.authority.types import AuthorityScope
from core.disclosure import DisclosurePosture
from core.registry.memory import ToolRegistry
from tests.harness.adapter_fixtures import (
    CountingHandler,
    echo_toolset,
    governed_agent_fixture,
    scripted_search_model,
)
from tests.harness.capture_audit import capture_audit
from tests.harness.fake_identity_fabric import FakeBrokeredMaterialSource, fake_identity_fabric
from tests.harness.frozen_clock import frozen_clock

#: This row starts runs directly to compare what `RUN_START` records, so it needs two runs
#: differing only in disclosure posture — identity resolution is not its subject and no
#: authority behaviour is being exercised. The fake supplies the surrounding run cheaply;
#: what is asserted is the payload the platform wrote, not anything the fabric decided.
FAKE_FABRIC_IS_FAULT_INJECTION = "run-start recording with identity held constant"


@pytest.mark.anyio
async def test_a_deferred_tool_is_flagged_until_it_is_discovered() -> None:
    """D3 — the transition is the mechanism, observed per model request."""
    flags: list[dict[str, bool | None]] = []

    _unused, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[], registry_tools={"echo": CountingHandler(result="ok")}
    )
    scripted = scripted_search_model(queries=["echo"], then_call=("echo", {"payload": "x"}))
    respond = scripted.function
    assert respond is not None

    def observing(messages: Any, info: Any) -> Any:
        flags.append(
            {t.name: t.defer_loading for t in info.model_request_parameters.function_tools}
        )
        return respond(messages, info)

    agent = build_governed_agent(
        FunctionModel(observing),
        toolsets=[deferred_toolset(echo_toolset(["echo"]))],
        defer_disclosure=True,
    )
    await agent.run("go", deps=deps)

    assert flags[0]["echo"] is True, "the tool was disclosed before the model asked for it"
    assert flags[1]["echo"] is False, "discovery did not disclose the tool"


def test_the_run_states_which_posture_it_is_in() -> None:
    """D8 — eager and deferred are distinguishable on the run's own record."""
    seen = {}
    for posture in (DisclosurePosture.EAGER, DisclosurePosture.DEFERRED):
        audit = capture_audit()
        registry = ToolRegistry()
        registry.register("echo", CountingHandler(result="ok"))
        start_adapter_run(
            correlation_id=f"corr-{posture.value}",
            subject_user_id="user-1",
            agent_definition_id="agent-alpha",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
            identity_fabric=fake_identity_fabric(
                subject_user_id="user-1", tool_names={"echo"}, ceiling_tools={"echo"}
            ),
            registry=registry,
            clock=frozen_clock(),
            audit_sink=audit,
            brokered_material_source=FakeBrokeredMaterialSource(),
            disclosure_posture=posture.value,
        )
        starts = [e for e in audit.all_entries() if e.event_type == AuditEventType.RUN_START]
        seen[posture] = starts[0].payload.get("disclosure_posture")

    assert seen[DisclosurePosture.EAGER] == "eager"
    assert seen[DisclosurePosture.DEFERRED] == "deferred"
    assert seen[DisclosurePosture.EAGER] != seen[DisclosurePosture.DEFERRED], (
        "the two postures are indistinguishable on the record (FR-004, SC-006)"
    )


def test_a_run_that_states_no_posture_carries_none() -> None:
    """The field is absent rather than guessed for runs predating the option.

    An absent field says "nobody told us"; a defaulted `eager` would say "this run was
    deliberately eager", which is a claim nothing made.
    """
    audit = capture_audit()
    registry = ToolRegistry()
    registry.register("echo", CountingHandler(result="ok"))
    start_adapter_run(
        correlation_id="corr-silent",
        subject_user_id="user-1",
        agent_definition_id="agent-alpha",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fake_identity_fabric(
            subject_user_id="user-1", tool_names={"echo"}, ceiling_tools={"echo"}
        ),
        registry=registry,
        clock=frozen_clock(),
        audit_sink=audit,
        brokered_material_source=FakeBrokeredMaterialSource(),
    )
    starts = [e for e in audit.all_entries() if e.event_type == AuditEventType.RUN_START]
    assert "disclosure_posture" not in starts[0].payload
