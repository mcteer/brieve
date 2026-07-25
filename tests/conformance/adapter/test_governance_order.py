# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — governance runs first among co-resident capabilities.

ADR-0019 and constitution Principle III. This is one of the three rows in force
for 004; it is merge-blocking, and it must fail if the ordering is inverted (the
companion break test proves the detector fires).
"""

from __future__ import annotations

import pytest

from adapters.pydantic_ai.governance import GOVERNANCE_PROBE_MARKER, GovernanceCapability
from tests.harness.adapter_fixtures import (
    CountingHandler,
    build_probe_capability,
    governed_agent_fixture,
)


def assert_governance_first(probe_log: list[str], handler: CountingHandler) -> None:
    """The shared ordering assertion. Used here and by the break test.

    Each probe entry records what the governed run's probe log already contained
    when that co-resident capability observed the call. Governance-first means the
    governance marker was already there — the co-resident capability never sees a
    call governance has not yet admitted.
    """
    assert handler.call_count == 1, "allow path must execute the tool body exactly once"
    assert probe_log, "co-resident capability never ran; ordering is unobservable"
    for entry in probe_log:
        assert GOVERNANCE_PROBE_MARKER in entry, (
            "non-governance capability observed the call before governance: "
            f"{entry!r} (expected {GOVERNANCE_PROBE_MARKER!r} already recorded)"
        )


@pytest.mark.anyio
async def test_governance_precedes_co_resident_capability() -> None:
    probe_log: list[str] = []
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
        capabilities=[build_probe_capability(probe_log)],
    )

    await agent.run("go", deps=deps)

    assert_governance_first(probe_log, handlers["echo"])


@pytest.mark.anyio
async def test_governance_is_outermost_even_when_listed_last() -> None:
    """Ordering must not depend on how a caller happens to order the list.

    ``GovernanceCapability`` declares ``position='outermost'``, so the framework
    sorts it first regardless. This is the property that survives a refactor by
    someone who does not know the rule.
    """
    probe_log: list[str] = []
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
        capabilities=[build_probe_capability(probe_log), GovernanceCapability()],
    )

    await agent.run("go", deps=deps)

    assert_governance_first(probe_log, handlers["echo"])


@pytest.mark.anyio
async def test_adapter_tool_path_reaches_invoke_tool() -> None:
    """Governed-entry interception: the body runs via core, not the framework.

    The framework tool bodies in the fixture raise if executed directly, so a
    successful run with a counted registry execution proves the call went through
    ``invoke_tool``. Unit-lane duplicate lives in tests/unit/test_adapter_mappings.py.
    """
    handler = CountingHandler()
    agent, deps, handlers, _audit = governed_agent_fixture(
        tool_calls=[("echo", {})],
        registry_tools={"echo": handler},
    )

    await agent.run("go", deps=deps)

    assert handlers["echo"].call_count == 1
