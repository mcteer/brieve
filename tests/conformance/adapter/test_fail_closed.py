# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the adapter path fails closed (FR-008, SC-002/SC-003).

An injected fault in the capability chain must deny with zero tool-body
executions. There is no branch in the adapter that turns an enforcement error
into an allow, and this is the case that would catch one appearing.
"""

from __future__ import annotations

import pytest

from adapters.pydantic_ai.run_context import AdapterRunContext
from adapters.pydantic_ai.tools import GovernedToolError, GovernedToolset
from tests.harness import assert_no_side_effect
from tests.harness.adapter_fixtures import (
    CountingHandler,
    build_failing_capability,
    build_probe_capability,
    governed_agent_fixture,
)


@pytest.mark.anyio
async def test_capability_fault_denies_with_zero_executions() -> None:
    """A co-resident capability that raises must not produce an executed tool."""
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
        capabilities=[build_failing_capability()],
    )

    with pytest.raises(Exception) as exc:
        await agent.run("go", deps=deps)

    assert not isinstance(exc.value, AssertionError), (
        "the framework tool body ran directly — governance was bypassed"
    )
    assert handlers["echo"].call_count == 0
    assert_no_side_effect(handlers["echo"])


@pytest.mark.anyio
async def test_missing_governed_run_denies_rather_than_executing() -> None:
    """No active run means no authority — the mapping denies before the body."""
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
    )
    deps.governed_run.state = deps.governed_run.state.__class__.REFUSED

    with pytest.raises(GovernedToolError) as exc:
        await agent.run("go", deps=deps)

    assert exc.value.reason_code == "run_unavailable"
    assert handlers["echo"].call_count == 0


@pytest.mark.anyio
async def test_absent_deps_denies() -> None:
    """A context without governed deps cannot be allowed through."""

    class _NoDeps:
        deps = None

    toolset = GovernedToolset(wrapped=object())  # type: ignore[arg-type]
    with pytest.raises(GovernedToolError) as exc:
        await toolset.call_tool("echo", {}, _NoDeps(), None)  # type: ignore[arg-type]

    assert exc.value.reason_code == "run_unavailable"


def test_capability_with_unreachable_toolset_wrapper_is_rejected() -> None:
    """A capability governance would silently swallow must fail at build time.

    ``GovernedToolset`` is terminal, so a co-resident ``get_wrapper_toolset``
    never runs. Installing it quietly would leave the capability looking active
    while doing nothing — the silent-pass failure ADR-0047 exists to prevent.
    """
    from pydantic_ai.capabilities.abstract import AbstractCapability
    from pydantic_ai.toolsets import AbstractToolset, WrapperToolset

    from adapters.pydantic_ai.agent import build_governed_agent

    class _WrappingCapability(AbstractCapability[AdapterRunContext]):
        def get_wrapper_toolset(
            self, toolset: AbstractToolset[AdapterRunContext]
        ) -> AbstractToolset[AdapterRunContext] | None:
            return WrapperToolset(toolset)

    with pytest.raises(GovernedToolError) as exc:
        build_governed_agent("test", capabilities=[_WrappingCapability()])

    assert exc.value.reason_code == "unreachable_capability_wrapper"
    assert "_WrappingCapability" in str(exc.value)
    assert "wrap_tool_execute" in str(exc.value), "the error must name the supported alternative"


@pytest.mark.anyio
async def test_observing_capability_is_still_accepted() -> None:
    """The rejection is narrow: wrap_tool_execute capabilities compose normally."""
    probe: list[str] = []
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
        capabilities=[build_probe_capability(probe)],
    )

    await agent.run("go", deps=deps)

    assert probe, "wrap_tool_execute capability must still run"
    assert handlers["echo"].call_count == 1


def test_adapter_run_context_reports_inactive_when_run_refused() -> None:
    """The guard the mapping relies on is itself asserted."""
    from core.run import RunState

    class _Run:
        state = RunState.REFUSED
        correlation_id = "c"
        subject_user_id = "u"
        agent_definition_id = "d"

    ctx = AdapterRunContext(governed_run=_Run())  # type: ignore[arg-type]
    assert ctx.is_active() is False
