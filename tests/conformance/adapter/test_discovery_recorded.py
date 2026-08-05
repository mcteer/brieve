# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — a search is recorded, cannot be refused, and is not an act (D5, D6).

ADR-0061's two halves, asserted separately because they fail separately.

**Recorded** is the easy half: the queries and matches reach the trail, including a search
that matched nothing — which is the record most worth having, since a model repeatedly
looking for a capability it was never granted is intent that leaves no other trace.

**Never refused** is the half with teeth, and it is asserted *structurally*: a search must
produce no governed decision at all. Not "a decision that always allows" — none. A decision
point that currently happens to allow everything is one policy change away from making
disclosure part of the authority path, which is the property ADR-0040 called a pure
optimization and ADR-0061 preserved deliberately.

**The exemption is positional, not a name match** (D6). Nothing in the adapter compares a
tool name to `search_tools`; a search cannot reach the governed entry because of where the
layers sit. The row proves the converse too: a genuinely registered tool *named*
`search_tools`, in a run without disclosure, routes to `invoke_tool` like any other tool. A
name-based exemption would have made that tool silently ungoverned — a bypass anybody could
create by choosing a name.
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


def _events(audit: Any, kind: AuditEventType) -> list[dict[str, Any]]:
    return [e.payload for e in audit.all_entries() if e.event_type == kind]


async def _search_run(queries: list[str], *, tools: list[str], then: str) -> Any:
    handlers = {name: CountingHandler(result="ok") for name in tools}
    _unused, deps, made, audit = governed_agent_fixture(
        tool_calls=[], registry_tools=handlers, scope_tools=tools
    )
    agent = build_governed_agent(
        scripted_search_model(queries=queries, then_call=(then, {"payload": "x"})),
        toolsets=[deferred_toolset(echo_toolset(tools))],
        defer_disclosure=True,
    )
    await agent.run("go", deps=deps)
    return audit, made


@pytest.mark.anyio
async def test_a_search_is_written_to_the_trail() -> None:
    """D5 — queries, matches, and how much remains hidden."""
    audit, _ = await _search_run(["echo"], tools=["echo", "other"], then="echo")

    observed = _events(audit, AuditEventType.DISCOVERY_OBSERVED)
    assert len(observed) == 1, f"expected one discovery record, got {observed}"
    assert observed[0]["queries"] == ["echo"]
    assert observed[0]["matched"] == ["echo"]
    assert observed[0]["undisclosed_remaining"] == 1, (
        "the record must say how much the model still cannot see"
    )


@pytest.mark.anyio
async def test_a_search_that_finds_nothing_is_still_written() -> None:
    """D5 — the empty match is the record ADR-0061 exists for."""
    audit, _ = await _search_run(["nothing-matches-this-query"], tools=["echo"], then="echo")

    observed = _events(audit, AuditEventType.DISCOVERY_OBSERVED)
    assert observed, "a search matching nothing wrote no record"
    assert observed[0]["matched"] == [], f"expected an empty match, got {observed[0]}"


@pytest.mark.anyio
async def test_a_search_never_reaches_the_governed_entry(monkeypatch: Any) -> None:
    """D5/D6 — never refused, measured at the entry rather than inferred from the trail.

    The audit payloads deliberately carry no tool name (hashes and argument keys only), so
    a row that searched the trail for the string `search_tools` would assert nothing and
    pass. That is the vacuous-assertion failure this repository has shipped before, and it
    is why this spies on the governed entry directly: the question is whether `invoke_tool`
    was ever asked about the search, and nothing else answers it.

    Note the assertion is the ABSENCE of a decision, not an allowed one. A search that was
    decided-and-permitted would be one policy change away from refusable, which is exactly
    what ADR-0061 forecloses.
    """
    import adapters.pydantic_ai.tools as tools_mod
    from core.tools.invoke import invoke_tool

    seen: list[str] = []

    def spy(run: Any, tool_name: str, tool_args: Any, **kwargs: Any) -> Any:
        seen.append(tool_name)
        return invoke_tool(run, tool_name, tool_args, **kwargs)

    # Patched where the adapter LOOKS IT UP, not where it is defined: the adapter imported
    # the name at module load, so patching `core.tools.invoke` would leave the live
    # reference untouched and the spy would record nothing while the row still passed.
    monkeypatch.setattr(tools_mod, "invoke_tool", spy)

    audit, _ = await _search_run(["echo"], tools=["echo"], then="echo")

    assert seen == ["echo"], (
        f"the governed entry saw {seen} — a search must never reach it (ADR-0061)"
    )
    assert _events(audit, AuditEventType.DISCOVERY_OBSERVED), (
        "the search bypassed governance but was also not recorded"
    )


@pytest.mark.anyio
async def test_a_real_tool_named_search_tools_is_still_governed() -> None:
    """D6 — the exemption is positional, so a tool with that name is not exempt.

    Without disclosure there is no search layer, so a registered tool called
    `search_tools` is an ordinary tool and must be governed as one. If the adapter had
    exempted the *name*, this tool would execute ungoverned — which is the bypass the
    positional design forecloses.
    """
    handler = CountingHandler(result="ok")
    agent, deps, handlers, audit = governed_agent_fixture(
        tool_calls=[("search_tools", {"payload": "x"})],
        registry_tools={"search_tools": handler},
        scope_tools=["search_tools"],
    )

    await agent.run("go", deps=deps)

    # Governed execution is proven by the body running exactly once through the governed
    # path AND by a tool-outcome record existing for it. The trail carries no tool name, so
    # "it was governed" is asserted by the pair rather than by a string match.
    assert handlers["search_tools"].call_count == 1, (
        "a registered tool named `search_tools` did not execute — the disclosure "
        "exemption leaked into a run that has no search layer"
    )
    outcomes = _events(audit, AuditEventType.TOOL_OUTCOME)
    assert len(outcomes) == 1 and outcomes[0]["executed"] is True, (
        f"expected one governed execution record, got {outcomes}"
    )
    assert not _events(audit, AuditEventType.DISCOVERY_OBSERVED), (
        "a run without disclosure recorded a discovery — the name was treated as special"
    )


@pytest.mark.anyio
async def test_discovery_is_distinguishable_from_an_attempt() -> None:
    """D5/FR-006c — looking for a capability must not read as using one."""
    audit, _ = await _search_run(["echo"], tools=["echo"], then="echo")

    kinds = {e.event_type for e in audit.all_entries()}
    assert AuditEventType.DISCOVERY_OBSERVED in kinds
    assert AuditEventType.DISCOVERY_OBSERVED not in {
        AuditEventType.PRE_DECISION,
        AuditEventType.TOOL_OUTCOME,
        AuditEventType.POST_DECISION,
    }, "discovery shares an event type with tool execution"
