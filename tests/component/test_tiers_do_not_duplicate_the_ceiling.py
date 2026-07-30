# SPDX-License-Identifier: Apache-2.0
"""ADR-0044 disjointness — no rule lives in two engines.

The ceiling answers **"may this agent call `apply`?"**. The tier answers **"may this agent
*compose*?"**. If either could answer the other's question, the same question would have two
answers from two mechanisms — and they would eventually disagree *silently*, because both
would look like they were working.

This is the failure that has no symptom until it matters: an agent denied a tool by its tier
while its ceiling permits it looks like a correct refusal, and an agent allowed a tool by its
tier while its ceiling forbids it looks like a working agent.
"""

from __future__ import annotations

import ast
import inspect

from core.authority.bindings import DefinitionBindings
from core.authority.types import AuthorityScope
from core.packs import isolation, workflows
from core.packs.isolation import reachable_tools, reachable_workflows, resolve_composition
from core.packs.loader import InMemoryPackLoader
from core.packs.manifest import PackManifest, ToolDeclaration, WorkflowDeclaration
from core.packs.registration import LoadedPack, PlatformBindings, load_packs
from core.registry.memory import ToolRegistry

CEILING = AuthorityScope(
    tool_names=frozenset({"vault_read", "vault_write"}), product_actions=frozenset()
)


def _loaded() -> dict[str, LoadedPack]:
    loader = InMemoryPackLoader()
    loader.add(
        PackManifest(
            name="vault",
            product="vault",
            version="0.1.0",
            provenance="authored",
            probe="vault_probe",
            tools=(
                ToolDeclaration(
                    name="vault_read", risk_class="read", transport="native", handler="h"
                ),
                ToolDeclaration(
                    name="vault_write",
                    risk_class="secret_touching",
                    transport="native",
                    handler="h",
                    observer="obs",
                    repeatable=False,
                ),
            ),
            workflows=(
                WorkflowDeclaration(name="paved", minimum_tier=1, paved=True),
                WorkflowDeclaration(name="free", minimum_tier=3, paved=False),
            ),
        )
    )
    return load_packs(
        ["vault"],
        loader=loader,
        registry=ToolRegistry(),
        bindings=PlatformBindings(
            handlers={"h": lambda args: "ok"},
            observers={"obs": object()},  # type: ignore[dict-item]
            probes={"vault_probe": lambda p: (True, "up")},
        ),
    )


def _at(tier: int) -> DefinitionBindings:
    return DefinitionBindings(
        agent_definition_id="applier", packs=frozenset({"vault"}), binding_map={}, tier=tier
    )


def test_the_tool_set_is_identical_at_every_tier() -> None:
    """The disjointness claim, stated as an equality across the whole tier range."""
    loaded = _loaded()
    sets = {tier: reachable_tools(_at(tier), loaded, CEILING) for tier in range(1, 6)}
    assert len(set(sets.values())) == 1, f"the tier moved the tool set: {sets}"
    assert next(iter(sets.values())) == frozenset({"vault_read", "vault_write"})


def test_the_workflow_set_narrows_with_tier_while_the_tool_set_does_not() -> None:
    """Both halves in one row, because the property is the *contrast*.

    Asserting only that tiers restrict workflows would pass on an implementation where tiers
    restricted tools as well.
    """
    loaded = _loaded()

    tools_low = reachable_tools(_at(1), loaded, CEILING)
    tools_high = reachable_tools(_at(3), loaded, CEILING)
    assert tools_low == tools_high

    permitted_low = {
        name
        for name, record in reachable_workflows(_at(1), loaded).items()
        if record.permitted_for(1)
    }
    permitted_high = {
        name
        for name, record in reachable_workflows(_at(3), loaded).items()
        if record.permitted_for(3)
    }
    assert permitted_low < permitted_high, "the tier did not bound composition at all"


def test_the_tier_resolver_never_receives_a_ceiling() -> None:
    """Structural: composition resolution cannot consult the tool jurisdiction.

    A signature that accepted a ceiling would let a future edit make a tier decision depend
    on tool authorization — the duplication, arriving as a one-line convenience.
    """
    parameters = set(inspect.signature(resolve_composition).parameters)
    assert "ceiling" not in parameters and "scope" not in parameters


def test_the_tool_resolver_never_receives_a_tier() -> None:
    """And the same in the other direction.

    `reachable_tools` takes bindings, which *carry* a tier — so this asserts the function
    does not read it, by checking its source for the attribute rather than its signature.
    """
    source = inspect.getsource(reachable_tools)
    assert ".tier" not in source, (
        "reachable_tools reads the tier; the ceiling answers about tools and the tier "
        "answers about composition, and neither may be derived from the other"
    )


def test_neither_module_imports_the_other_engines_vocabulary() -> None:
    """The two jurisdictions do not share a decision function.

    `core.packs.workflows` decides about composition and knows nothing about scopes;
    `AuthorityScope` never reaches it. That absence is what keeps the two engines from
    growing a shared helper that quietly answers both questions.
    """
    # Code, not prose. The module's docstring EXPLAINS the ceiling — that is the module
    # being documented, not the module knowing the other jurisdiction. Same distinction the
    # product-blindness row makes, for the same reason: a check that flags explanation
    # teaches people to delete the explanation.
    tree = ast.parse(inspect.getsource(workflows))
    identifiers = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "AuthorityScope" not in identifiers
    assert not any("ceiling" in name.lower() for name in identifiers), (
        f"workflows.py code touches the ceiling: "
        f"{[n for n in identifiers if 'ceiling' in n.lower()]}"
    )

    # And isolation, which touches both, keeps them in separate functions rather than one.
    isolation_source = inspect.getsource(isolation)
    assert "def reachable_tools" in isolation_source
    assert "def resolve_composition" in isolation_source
