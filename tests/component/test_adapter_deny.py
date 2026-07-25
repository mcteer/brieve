# SPDX-License-Identifier: Apache-2.0
"""US2 — adapter-path denials produce zero tool side effects.

Quickstart Scenario B. The adapter must not weaken 002/003 deny properties: an
adapter-shaped bypass would falsify Principle II and ADR-0006.
"""

from __future__ import annotations

from typing import cast

import pytest

from adapters.pydantic_ai.tools import GovernedToolError
from core.authority.types import AuthorityScope
from tests.harness import SECRET_MARKERS, assert_no_side_effect
from tests.harness.adapter_fixtures import CountingHandler, governed_agent_fixture
from tests.harness.fake_identity_fabric import FakeIdentityFabric


async def _run_expecting_denial(agent: object, deps: object) -> GovernedToolError:
    """Run the agent and return the governed refusal it raised."""
    with pytest.raises(GovernedToolError) as exc:
        await agent.run("go", deps=deps)  # type: ignore[attr-defined]
    return exc.value


@pytest.mark.anyio
async def test_unregistered_tool_is_denied_with_no_side_effect() -> None:
    """A tool the model can see but the registry does not hold is denied by core."""
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("ghost", {})],
        registry_tools={"echo": handler},
        framework_tools=["echo", "ghost"],
        scope_tools=["echo", "ghost"],
    )

    error = await _run_expecting_denial(agent, deps)

    assert error.reason_code
    assert handlers["echo"].call_count == 0
    assert_no_side_effect(handlers["echo"])


@pytest.mark.anyio
async def test_out_of_scope_tool_is_denied_with_no_side_effect() -> None:
    """Registered but outside the run's scope — still denied before the body."""
    handler = CountingHandler()
    other = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("other", {})],
        registry_tools={"echo": handler, "other": other},
        framework_tools=["echo", "other"],
        scope_tools=["echo"],
    )

    await _run_expecting_denial(agent, deps)

    assert handlers["other"].call_count == 0
    assert_no_side_effect(handlers["other"])


@pytest.mark.anyio
async def test_authority_insufficient_tool_is_denied() -> None:
    """Outside live effective authority — same posture as 003 authority denials."""
    handler = CountingHandler()
    restricted = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("restricted", {})],
        registry_tools={"echo": handler, "restricted": restricted},
        framework_tools=["echo", "restricted"],
        scope_tools=["echo", "restricted"],
    )
    # Shrink policy mid-run so the tool leaves live_effective without leaving scope.
    fabric = cast(FakeIdentityFabric, deps.governed_run.identity_fabric)
    fabric.shrink_policy(AuthorityScope(tool_names=frozenset({"echo"})))

    await _run_expecting_denial(agent, deps)

    assert handlers["restricted"].call_count == 0


@pytest.mark.anyio
async def test_denial_is_audited_under_the_run_correlation_id() -> None:
    """GATE:correlation — a denial is evidence, and it joins the same run."""
    agent, deps, _handlers, audit = governed_agent_fixture(
        tool_calls=[("ghost", {})],
        framework_tools=["echo", "ghost"],
        scope_tools=["echo", "ghost"],
    )

    await _run_expecting_denial(agent, deps)

    entries = audit.list_by_correlation_id(deps.correlation_id)
    assert entries, "denial must be audited under the run correlation ID"
    assert all(e.correlation_id == deps.correlation_id for e in entries)


@pytest.mark.anyio
async def test_deny_is_not_converted_into_a_successful_call() -> None:
    """GATE:fail-closed — core deny must not become an empty success.

    The mapping raises rather than returning; a returned value would look to the
    model like the action succeeded and produced nothing.
    """
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("ghost", {})],
        framework_tools=["echo", "ghost"],
        scope_tools=["echo", "ghost"],
    )

    error = await _run_expecting_denial(agent, deps)

    assert isinstance(error, GovernedToolError)
    assert handlers["echo"].call_count == 0


@pytest.mark.anyio
async def test_denial_message_explains_without_leaking(caplog: pytest.LogCaptureFixture) -> None:
    """FR-013 — say the action was refused without disclosing secrets or entitlements."""
    agent, deps, _handlers, _audit = governed_agent_fixture(
        tool_calls=[("ghost", {})],
        framework_tools=["echo", "ghost"],
        scope_tools=["echo", "ghost"],
    )

    error = await _run_expecting_denial(agent, deps)

    message = str(error)
    assert message, "a refusal must say something"
    for marker in SECRET_MARKERS:
        assert marker not in message
    # Must not enumerate what the requester may not see.
    assert "ceiling" not in message.lower()
    assert "entitlement" not in message.lower()
