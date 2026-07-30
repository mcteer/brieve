# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — pack hooks are a new enforcement surface, and it is bounded.

The plan says this plainly rather than claiming 013 adds no enforcement point, because that
claim was wrong: **pack hooks are authored outside this repository and run inside the
pipeline.** Two bounds hold, and this file asserts both.

**A pack may not register at `GOVERNANCE`.** `has_required_governance_hooks` decides whether
enforcement is whole by looking for built-in names among hooks whose
`capability_kind == GOVERNANCE`. A pack able to register at that kind could contribute a
hook to the very set that check inspects — enforcement authored by whoever ships a pack.
Refused at load, which is where a manifest is read, rather than at review, which is where
somebody looked.

**Governance still runs first.** The refusal above stops a pack entering the governance set;
this asserts that a pack hook admitted at `OTHER` cannot get in front of one that is not.
The two are different failures — one is impersonation, the other is ordering — and a bound
on only the first would let a pack hook see a call before the governance hooks that would
have denied it.
"""

from __future__ import annotations

import pytest

from core.hooks.engine import sort_hooks
from core.hooks.governance import builtin_governance_hooks, has_required_governance_hooks
from core.hooks.types import (
    CapabilityKind,
    HookContext,
    HookDecision,
    HookPhase,
    HookRegistration,
)
from core.packs.loader import validate_manifest
from core.packs.manifest import ManifestError, PackHookDeclaration, PackManifest, ToolDeclaration
from core.packs.registration import PlatformBindings, register_pack
from core.registry.memory import ToolRegistry


def _allow(ctx: HookContext) -> HookDecision:
    return HookDecision(outcome="allow", reason_code="ok", hook_name="from_pack")


def _manifest(*hooks: PackHookDeclaration) -> PackManifest:
    return PackManifest(
        name="vault",
        product="vault",
        version="0.1.0",
        provenance="authored",
        probe="vault_probe",
        tools=(ToolDeclaration(name="read", risk_class="read", transport="native", handler="h"),),
        hooks=hooks,
    )


def _bindings() -> PlatformBindings:
    return PlatformBindings(
        handlers={"h": lambda args: "ok"},
        hooks={"hk": _allow},
        probes={"vault_probe": lambda product: (True, "up")},
    )


def test_a_pack_declaring_a_governance_hook_is_refused_at_load() -> None:
    with pytest.raises(ManifestError) as caught:
        validate_manifest(
            _manifest(
                PackHookDeclaration(
                    name="looks_official",
                    phase=HookPhase.PRE,
                    capability_kind=CapabilityKind.GOVERNANCE,
                    handler="hk",
                )
            )
        )
    assert caught.value.reason_code == "governance_hook_from_pack"


def test_a_pack_hook_at_other_registers_and_runs_in_its_phase() -> None:
    """The positive control. A bound that refused everything would also pass the row above."""
    loaded = register_pack(
        _manifest(
            PackHookDeclaration(
                name="pack_pre",
                phase=HookPhase.PRE,
                capability_kind=CapabilityKind.OTHER,
                handler="hk",
            )
        ),
        registry=ToolRegistry(),
        bindings=_bindings(),
    )
    assert [h.name for h in loaded.hook_registrations] == ["pack_pre"]
    assert loaded.hook_registrations[0].phase is HookPhase.PRE
    assert loaded.hook_registrations[0].capability_kind is CapabilityKind.OTHER


def test_a_pack_hook_cannot_complete_the_governance_set() -> None:
    """The refusal's actual purpose, asserted at the check it protects.

    Even naming itself after a built-in, a pack hook is at `OTHER` — and
    `has_required_governance_hooks` looks only at `GOVERNANCE`. So enforcement-is-whole
    stays false without the real ones, which is what stops a pack satisfying the platform's
    own completeness check.
    """
    impostors = [
        HookRegistration(
            name=builtin.name,
            phase=HookPhase.PRE,
            capability_kind=CapabilityKind.OTHER,
            handler=_allow,
        )
        for builtin in builtin_governance_hooks()
        if builtin.phase is HookPhase.PRE
    ]
    assert impostors, "no built-in pre-hooks found; this row would pass vacuously"
    assert has_required_governance_hooks(impostors) is False
    assert has_required_governance_hooks(list(builtin_governance_hooks())) is True


def test_governance_still_runs_first_with_pack_hooks_present() -> None:
    """Ordering, which the load-time refusal does not cover.

    A pack hook admitted at `OTHER` must not get in front of a governance hook. Otherwise a
    third-party hook sees a call before the hooks that would have denied it.
    """
    pack_hook = HookRegistration(
        name="pack_pre", phase=HookPhase.PRE, capability_kind=CapabilityKind.OTHER, handler=_allow
    )
    # Pack hook first in the input, so a sort that preserved input order would fail here.
    ordered = sort_hooks([pack_hook, *builtin_governance_hooks()], HookPhase.PRE)

    kinds = [h.capability_kind for h in ordered]
    assert CapabilityKind.OTHER in kinds, "the pack hook was dropped rather than ordered"
    first_other = kinds.index(CapabilityKind.OTHER)
    assert all(k is CapabilityKind.GOVERNANCE for k in kinds[:first_other])
    assert ordered[-1].name == "pack_pre"
