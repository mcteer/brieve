# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — deferred disclosure changes nothing governance can see (D1, D2).

**The owed gate row.** ADR-0040 words the property itself: *an identical operation must
produce identical governance outcomes whether or not the tool was disclosed eagerly.* That
sentence is what makes deferral a pure optimization rather than a second authority path, and
until now nothing asserted it — the row has sat on the constitution's Quality Gates since
the ADR was Accepted in 2026-07.

Both directions are covered, and the deny path is the one with teeth. An allow-path-only
comparison would pass for an implementation that consulted the disclosure layer's view of
the world where it should have consulted authority: a tool the model has "discovered" looks
permitted, and the difference only shows when policy says no.

The comparison excludes correlation-scoped values (ids, timestamps) by name rather than by
similarity, so a field that starts differing between postures fails rather than being
absorbed into a fuzzy match. It also excludes the deferred run's `DISCOVERY_OBSERVED`
entries: those exist only under deferral by design (ADR-0061) and are asserted separately in
`test_discovery_recorded.py`. What is compared is the span between `PRE_DECISION` and
`POST_DECISION` — the governed decision about the call itself.
"""

from __future__ import annotations

from typing import Any

import pytest

from adapters.pydantic_ai.agent import build_governed_agent
from adapters.pydantic_ai.governance import deferred_toolset
from core.audit.schema import AuditEventType
from tests.harness.adapter_fixtures import (
    CountingHandler,
    echo_toolset,
    governed_agent_fixture,
    scripted_search_model,
)

#: Fields whose difference between two runs is not a governance difference. Named
#: individually: a blanket "ignore anything that looks like an id" would also absorb a
#: subject or a tool name starting to differ, which is exactly what this row exists to catch.
_CORRELATION_SCOPED = {"correlation_id", "timestamp", "entry_hash", "prev_hash", "sequence"}

#: The span that describes the governed decision. `DISCOVERY_OBSERVED` sits outside it.
_DECISION_SPAN = {
    AuditEventType.PRE_DECISION,
    AuditEventType.TOOL_OUTCOME,
    AuditEventType.POST_DECISION,
}


def _decision_records(audit: Any) -> list[dict[str, Any]]:
    """The decision span, stripped of what legitimately differs between two runs."""
    records = []
    for entry in audit.all_entries():
        if entry.event_type not in _DECISION_SPAN:
            continue
        payload = {k: v for k, v in entry.payload.items() if k not in _CORRELATION_SCOPED}
        records.append({"event_type": entry.event_type.value, "payload": payload})
    return records


async def _run_eager(tool: str, args: dict[str, Any], *, scope: list[str]) -> Any:
    handler = CountingHandler(result="ok")
    agent, deps, handlers, audit = governed_agent_fixture(
        tool_calls=[(tool, args)],
        registry_tools={tool: handler},
        scope_tools=scope,
    )
    await _run_absorbing_denial(agent, deps)
    return audit, handlers


async def _run_absorbing_denial(agent: Any, deps: Any) -> None:
    """Run to completion, letting a governed denial end the run.

    A denied tool raises `GovernedToolError` out of the framework's call path, which is the
    correct behaviour and not what this row is about: the assertion is on the RECORDS the
    denial produced, and those are written before the raise. Swallowing it here keeps the
    row measuring parity rather than exception plumbing — and the denial is still proven,
    because the handler call count and the audit records are both checked.
    """
    from adapters.pydantic_ai.tools import GovernedToolError

    try:
        await agent.run("go", deps=deps)
    except GovernedToolError:
        pass


async def _run_deferred(tool: str, args: dict[str, Any], *, scope: list[str]) -> Any:
    """The same operation, reached by searching for it instead of being shown it."""
    handler = CountingHandler(result="ok")
    _unused, deps, handlers, audit = governed_agent_fixture(
        tool_calls=[],
        registry_tools={tool: handler},
        scope_tools=scope,
    )
    agent = build_governed_agent(
        scripted_search_model(queries=[tool], then_call=(tool, args)),
        toolsets=[deferred_toolset(echo_toolset([tool]))],
        defer_disclosure=True,
    )
    await _run_absorbing_denial(agent, deps)
    return audit, handlers


@pytest.mark.anyio
async def test_allow_path_is_identical_under_both_postures() -> None:
    """D1 — the operation the model was shown, and the one it had to find."""
    eager_audit, eager_handlers = await _run_eager("echo", {"payload": "x"}, scope=["echo"])
    deferred_audit, deferred_handlers = await _run_deferred(
        "echo", {"payload": "x"}, scope=["echo"]
    )

    assert eager_handlers["echo"].call_count == 1
    assert deferred_handlers["echo"].call_count == 1, (
        "the discovered tool did not execute — deferral must change disclosure, not behaviour"
    )
    assert _decision_records(deferred_audit) == _decision_records(eager_audit), (
        "the governed decision differs between disclosure postures (ADR-0040, SC-001)"
    )


@pytest.mark.anyio
async def test_deny_path_is_identical_under_both_postures() -> None:
    """D2 — the row that catches disclosure being consulted where authority should be.

    The tool is registered but outside the run's scope, so policy denies it. A discovered
    tool must be denied for the same reason an eagerly-disclosed one is: what a model knows
    about is not what it may do.
    """
    eager_audit, eager_handlers = await _run_eager("echo", {"payload": "x"}, scope=["other"])
    deferred_audit, deferred_handlers = await _run_deferred(
        "echo", {"payload": "x"}, scope=["other"]
    )

    assert eager_handlers["echo"].call_count == 0
    assert deferred_handlers["echo"].call_count == 0, (
        "a denied tool executed under deferral — disclosure became an authority path"
    )
    assert _decision_records(deferred_audit) == _decision_records(eager_audit), (
        "a denial differs between disclosure postures (ADR-0040, SC-001)"
    )


@pytest.mark.anyio
async def test_the_comparison_can_actually_fail() -> None:
    """A comparator that has never rejected anything asserts nothing.

    Two genuinely different operations must compare unequal. Without this, a
    `_decision_records` that silently returned `[]` — a stripper that removed too much, the
    failure mode this repository has shipped four times — would make both rows above pass
    while comparing nothing.
    """
    allowed, _ = await _run_eager("echo", {"payload": "x"}, scope=["echo"])
    denied, _ = await _run_eager("echo", {"payload": "x"}, scope=["other"])
    assert _decision_records(allowed), "the decision span stripper returned nothing"
    assert _decision_records(allowed) != _decision_records(denied), (
        "an allow and a deny compared equal — the comparator is vacuous"
    )
