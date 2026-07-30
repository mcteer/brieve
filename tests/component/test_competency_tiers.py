# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a definition's tier bounds what it may compose (ADR-0045, SC-009).

**The tier belongs to the definition, never to the request.** `resolve_composition` takes no
argument describing what the person asked for, and that absence is the mechanism rather than
an oversight. A tier that could be raised by asking differently would be a suggestion.

That is what makes this least privilege applied to *capability* rather than to credentials:
what an agent may compose is bounded at design time and reviewable like any other part of the
definition — not negotiated at run time by whoever is talking to it.
"""

from __future__ import annotations

import inspect

import pytest

from core.authority.bindings import DefinitionBindings
from core.authority.types import AuthorityScope
from core.packs.isolation import IsolationRefused, reachable_tools, resolve_composition
from core.packs.loader import InMemoryPackLoader
from core.packs.manifest import PackManifest, ToolDeclaration, WorkflowDeclaration
from core.packs.registration import LoadedPack, PlatformBindings, load_packs
from core.registry.memory import ToolRegistry


def _pack() -> PackManifest:
    return PackManifest(
        name="vault",
        product="vault",
        version="0.1.0",
        provenance="authored",
        probe="vault_probe",
        tools=(
            ToolDeclaration(name="vault_read", risk_class="read", transport="native", handler="h"),
        ),
        workflows=(
            WorkflowDeclaration(name="read-configuration", minimum_tier=1, paved=True),
            WorkflowDeclaration(name="assemble-freely", minimum_tier=2, paved=False),
            WorkflowDeclaration(name="rotate-credential", minimum_tier=3, paved=False),
            # Declares a low minimum but is NOT paved. The case a `minimum_tier >= tier`
            # check alone would wave through at tier 1, whose whole meaning is paved-only.
            WorkflowDeclaration(name="unpaved-but-cheap", minimum_tier=1, paved=False),
        ),
    )


def _loaded() -> dict[str, LoadedPack]:
    loader = InMemoryPackLoader()
    loader.add(_pack())
    return load_packs(
        ["vault"],
        loader=loader,
        registry=ToolRegistry(),
        bindings=PlatformBindings(
            handlers={"h": lambda args: "ok"},
            probes={"vault_probe": lambda p: (True, "up")},
        ),
    )


def _at(tier: int) -> DefinitionBindings:
    return DefinitionBindings(
        agent_definition_id="applier", packs=frozenset({"vault"}), binding_map={}, tier=tier
    )


def test_a_lower_tier_definition_may_run_a_paved_workflow() -> None:
    assert resolve_composition("read-configuration", _at(1), _loaded()).paved is True


def test_a_lower_tier_definition_is_refused_a_higher_tier_workflow() -> None:
    with pytest.raises(IsolationRefused) as caught:
        resolve_composition("assemble-freely", _at(1), _loaded())
    assert caught.value.reason_code == "above_tier"


def test_tier_one_is_confined_to_paved_paths_even_at_a_low_minimum() -> None:
    """The case a minimum-tier comparison alone would miss.

    `unpaved-but-cheap` declares `minimum_tier = 1`, so `tier >= minimum` passes. But tier 1
    means *fully-paved golden paths only*, and an unpaved workflow reachable there would make
    the lowest tier's whole meaning depend on what each pack happened to declare.
    """
    with pytest.raises(IsolationRefused) as caught:
        resolve_composition("unpaved-but-cheap", _at(1), _loaded())
    assert caught.value.reason_code == "above_tier"


def test_a_higher_tier_definition_may_compose_freely() -> None:
    assert resolve_composition("assemble-freely", _at(2), _loaded()).name == "assemble-freely"
    assert resolve_composition("unpaved-but-cheap", _at(2), _loaded()).paved is False


def test_the_tier_wins_because_the_request_is_not_an_input() -> None:
    """**Asserted against the signature, not against behaviour.**

    A behavioural row would only show that today's caller does not pass the request. This
    shows there is nowhere to pass it — the function accepts a workflow name, the
    definition's bindings, and what is loaded. Nothing describing what was asked for.
    """
    parameters = set(inspect.signature(resolve_composition).parameters)
    assert parameters == {"workflow_name", "bindings", "loaded"}
    for request_shaped in ("request", "message", "user_input", "requested_tier", "prompt"):
        assert request_shaped not in parameters, (
            f"resolve_composition accepts {request_shaped!r}; a tier that can be influenced "
            f"by what was asked for is a suggestion, not a bound"
        )


def test_an_unknown_workflow_refuses_rather_than_defaulting_open() -> None:
    with pytest.raises(IsolationRefused) as caught:
        resolve_composition("no-such-workflow", _at(3), _loaded())
    assert caught.value.reason_code == "pack_not_loaded"


def test_a_tier_change_never_alters_which_tools_are_reachable() -> None:
    """ADR-0044's disjointness, asserted rather than assumed.

    The ceiling answers about tools and the tier answers about composition. If a tier also
    moved the tool set, the same question would have two answers from two mechanisms, and
    they would eventually disagree — silently, because both would look like they were working.
    """
    loaded = _loaded()
    ceiling = AuthorityScope(tool_names=frozenset({"vault_read"}), product_actions=frozenset())

    at_every_tier = {reachable_tools(_at(tier), loaded, ceiling) for tier in (1, 2, 3, 9)}
    assert at_every_tier == {frozenset({"vault_read"})}, (
        "changing the tier changed the reachable tool set; the tier bounds composition and "
        "the ceiling bounds tools, and no rule may live in both engines"
    )
