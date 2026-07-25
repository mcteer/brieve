# SPDX-License-Identifier: Apache-2.0
"""US1 — a scripted agent completes an in-scope governed call through the adapter.

Quickstart Scenario A. Covers SC-001 (exactly one execution), SC-004 (audit
retrievable by correlation ID), SC-005 (authority narrowing holds).
"""

from __future__ import annotations

import pytest

from core.authority.types import AuthorityScope
from tests.harness import (
    assert_audit_chain,
    assert_correlated,
    assert_no_secret_values,
    assert_scope_narrowed,
)
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture


@pytest.mark.anyio
async def test_adapter_allow_executes_tool_body_exactly_once() -> None:
    handler = CountingHandler(result="echoed")
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {"payload": "hello"})],
        registry_tools={"echo": handler},
    )

    result = await agent.run("go", deps=deps)

    assert handlers["echo"].call_count == 1, "tool body must run exactly once on the allow path"
    assert result.output == "done"


@pytest.mark.anyio
async def test_adapter_allow_is_correlated_and_audited() -> None:
    """GATE:correlation — one ID joins the run to its tool decision."""
    agent, deps, _handlers, audit = governed_agent_fixture(
        tool_calls=[("echo", {"payload": "hello"})],
    )

    await agent.run("go", deps=deps)

    assert_correlated(audit, [], deps.correlation_id)
    assert_audit_chain(audit)
    entries = audit.list_by_correlation_id(deps.correlation_id)
    assert entries, "adapter-started run must leave a non-empty audit trail"
    assert all(e.correlation_id == deps.correlation_id for e in entries)


@pytest.mark.anyio
async def test_adapter_allow_leaks_no_secret_values() -> None:
    """GATE:no-secret-leak — audit, spans, and model-visible context stay clean."""
    agent, deps, _handlers, audit = governed_agent_fixture(
        tool_calls=[("echo", {"payload": "hello"})],
    )

    result = await agent.run("go", deps=deps)

    assert_no_secret_values(audit)
    # Model-visible context: the message history the model actually saw.
    assert_no_secret_values(repr(result.all_messages()))


@pytest.mark.anyio
async def test_adapter_bound_authority_is_narrowed() -> None:
    """SC-005 — authority bound through the adapter still satisfies 003 narrowing."""
    agent, deps, _handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {"payload": "hello"})],
        scope_tools=["echo"],
    )

    await agent.run("go", deps=deps)

    assert_scope_narrowed(
        deps.governed_run.authority,
        at_most=AuthorityScope(tool_names=frozenset({"echo"})),
    )
