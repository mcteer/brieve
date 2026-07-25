# SPDX-License-Identifier: Apache-2.0
"""US4 — per-definition ceilings resolve through the adapter (FR-007)."""

from __future__ import annotations

import pytest

from adapters.pydantic_ai.tools import GovernedToolError
from core.authority.errors import AuthorityRefuseError
from core.authority.types import AuthorityScope
from tests.harness import fake_identity_fabric
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture
from tests.harness.fake_identity_fabric import FakeIdentityFabric

BROAD = "agent-def-broad"
NARROW = "agent-def-narrow"


def _two_definition_fabric() -> FakeIdentityFabric:
    return fake_identity_fabric(
        tool_names={"echo", "admin"},
        ceilings={
            BROAD: AuthorityScope(tool_names=frozenset({"echo", "admin"})),
            NARROW: AuthorityScope(tool_names=frozenset({"echo"})),
        },
    )


@pytest.mark.anyio
async def test_broad_definition_may_use_its_wider_ceiling() -> None:
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("admin", {})],
        registry_tools={"echo": CountingHandler(), "admin": handler},
        agent_definition_id=BROAD,
        scope_tools=["echo", "admin"],
        fabric=_two_definition_fabric(),
    )

    await agent.run("go", deps=deps)

    assert handlers["admin"].call_count == 1


def test_narrow_definition_cannot_request_beyond_its_ceiling() -> None:
    """The ceiling is per-definition: the narrow one refuses at start."""
    with pytest.raises(AuthorityRefuseError):
        governed_agent_fixture(
            tool_calls=[("admin", {})],
            registry_tools={"echo": CountingHandler(), "admin": CountingHandler()},
            agent_definition_id=NARROW,
            scope_tools=["echo", "admin"],
            fabric=_two_definition_fabric(),
        )


def test_unknown_definition_refuses_rather_than_opening_a_ceiling() -> None:
    with pytest.raises(AuthorityRefuseError):
        governed_agent_fixture(
            tool_calls=[("echo", {})],
            agent_definition_id="agent-def-absent",
            scope_tools=["echo"],
            fabric=_two_definition_fabric(),
        )


@pytest.mark.anyio
async def test_narrow_definition_still_allows_its_own_tools() -> None:
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
        agent_definition_id=NARROW,
        scope_tools=["echo"],
        fabric=_two_definition_fabric(),
    )

    await agent.run("go", deps=deps)

    assert handlers["echo"].call_count == 1
    assert deps.agent_definition_id == NARROW


@pytest.mark.anyio
async def test_definition_is_carried_on_the_governed_run() -> None:
    """Live policy re-resolution is per-definition, so the run must carry the id."""
    agent, deps, _handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        agent_definition_id=NARROW,
        scope_tools=["echo"],
        fabric=_two_definition_fabric(),
    )

    await agent.run("go", deps=deps)

    assert deps.governed_run.agent_definition_id == NARROW
    _ = GovernedToolError  # imported for the deny-path sibling test module
