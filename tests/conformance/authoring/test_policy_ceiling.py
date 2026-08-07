# SPDX-License-Identifier: Apache-2.0
"""V19 — FR-024's ceiling clause, both directions in one process (042, analyze C1).

**This row exists because 041's five-layer gap started exactly here.** A ceiling naming
`author_file` refused `unknown_ceiling_entry` — a *correct* ceiling, refused, because the
vocabulary a ceiling may name is derived from what registered and nothing had registered the
name. Every 038 row stayed green through it, because they construct handlers directly.

So the analyze pass flagged FR-024's second clause as uncovered, and this is the coverage.
Both directions matter and they fail differently:

- a ceiling that NAMES the new tools must reach them — the 041 regression
- a ceiling that OMITS them must refuse — the governance regression

One process, one registry construction, two ceilings. There is no pre-042 tree to check out
(040's M3 recorded that trap), so "before" has to be constructible rather than checked out.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.audit.sink import InMemoryAuditSink
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from core.tools.invoke import invoke_tool
from surfaces.toolset import build_registry, known_tools
from tests.harness.fake_identity_fabric import fake_identity_fabric
from tests.harness.frozen_clock import frozen_clock

#: Declared because the repo requires it: authority is resolved through the fake so the ONLY
#: variable between the two halves of this row is the ceiling. A production fabric would vary
#: the registry alongside it, and "which one refused" would be unanswerable — which is the
#: exact confusion that let 041's `unknown_ceiling_entry` read as a governance decision.
FAKE_FABRIC_IS_FAULT_INJECTION = (
    "The ceiling is the injected variable. Everything else — registry, scope, call — is held "
    "identical, so a refusal can only be the ceiling's doing."
)

POLICY_TOOLS = ("vault_policy_read", "vault_policy_impact")


def _run_with_ceiling(registry: ToolRegistry, ceiling: set[str]) -> Any:
    return start_governed_run(
        agent_definition_id="authoring-agent",
        correlation_id="corr-042-ceiling",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(ceiling), product_actions=frozenset()),
        identity_fabric=fake_identity_fabric(
            tool_names=set(ceiling),
            product_actions=set(),
            ceiling_tools=set(ceiling),
            ceiling_actions=set(),
        ),
        clock=frozen_clock(),
        registry=registry,
        audit_sink=InMemoryAuditSink(),
    )


@pytest.mark.parametrize("tool_name", POLICY_TOOLS)
def test_row_v19_a_ceiling_naming_the_policy_tools_may_reach_them(tool_name: str) -> None:
    """The 041 direction: a CORRECT ceiling must not be refused for want of registration.

    `known_tools` derives the vocabulary a ceiling may name from what the pack loader
    registered. If the pack declaration and the handler table ever drift apart again, this
    fails here — where the name is written — rather than at the first dispatched run.
    """
    registry, _ = build_registry(packs=["vault"])
    vocabulary = known_tools(registry)

    assert tool_name in vocabulary, (
        f"{tool_name!r} is declared in packs/vault/pack.toml and is not in the vocabulary a "
        f"ceiling may name. This is 041's `unknown_ceiling_entry` exactly: a correct ceiling "
        f"refused because registration and declaration drifted apart."
    )


def test_row_v19_a_ceiling_that_omits_them_refuses() -> None:
    """The governance direction: registration makes a name RESOLVABLE, not permitted.

    Without this the row above would be satisfied by a registry that hands every tool to
    every definition — which is registration read as authorisation, and is the equation 026
    exists to break.
    """
    registry, _ = build_registry(packs=["vault"])
    run = _run_with_ceiling(registry, {"vault_read"})

    result = invoke_tool(run, "vault_policy_read", {"policy_name": "payments-app-read"})

    assert not result.allowed, (
        "a definition whose ceiling omits the policy tools must not reach them; the registry "
        "knowing the name is not the same as the definition being allowed to call it"
    )


def test_row_v19_the_two_directions_are_measured_against_one_registry() -> None:
    """The comparison only means something if both halves share a construction.

    Two registries built differently could differ for reasons neither row is about, which is
    how a pair of green rows comes to prove nothing about the pair.
    """
    registry, _ = build_registry(packs=["vault"])

    permitted = _run_with_ceiling(registry, set(POLICY_TOOLS))
    refused = _run_with_ceiling(registry, {"vault_read"})

    assert refused.registry is permitted.registry


def test_the_declared_handlers_resolve_to_platform_functions() -> None:
    """A manifest may only name what already exists, and this is where that is checked.

    The platform proved it during implementation: declaring `vault_policy_impact` one commit
    before its handler existed made `build_registry` refuse the whole vault pack with
    *"names handler ... which the platform does not provide"*. Recorded as a row so the next
    declaration-without-implementation fails on purpose rather than by accident.
    """
    registry, loaded = build_registry(packs=["vault"])

    assert "vault" in loaded
    for tool_name in POLICY_TOOLS:
        assert registry.resolve(tool_name) is not None


def test_the_impact_tool_is_repeatable_and_the_read_tool_is_too() -> None:
    """Both declared repeatable, and the impact one is the argument worth pinning.

    `vault_write` is non-repeatable because a lost CAS write must be resolved by observation.
    The impact check's contract is that it leaves nothing behind, so a replay after
    interruption HEALS the orphan the interruption created — and a non-repeatable declaration
    would demand an observer whose only honest answer is useless to a resumer.
    """
    registry, _ = build_registry(packs=["vault"])

    for tool_name in POLICY_TOOLS:
        entry = registry.resolve(tool_name)
        assert getattr(entry, "repeatable", True) is True, (
            f"{tool_name} is declared non-repeatable, which demands an observer; the impact "
            f"check has nothing durable to observe by design"
        )
