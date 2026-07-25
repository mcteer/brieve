# SPDX-License-Identifier: Apache-2.0
"""Built-in governance/enforcement hooks (must run first among co-resident hooks)."""

from __future__ import annotations

from core.hooks.types import (
    CapabilityKind,
    HookContext,
    HookDecision,
    HookPhase,
    HookRegistration,
)

GOVERNANCE_HOOK_NAME = "governance"


def _allow(_ctx: HookContext) -> HookDecision:
    return HookDecision(outcome="allow", reason_code="ok", message="allowed")


def builtin_governance_hooks() -> list[HookRegistration]:
    """Return the required pre/post governance hooks for a governed pipeline."""
    return [
        HookRegistration(
            name=GOVERNANCE_HOOK_NAME,
            phase=HookPhase.PRE,
            capability_kind=CapabilityKind.GOVERNANCE,
            handler=_allow,
        ),
        HookRegistration(
            name=GOVERNANCE_HOOK_NAME,
            phase=HookPhase.POST,
            capability_kind=CapabilityKind.GOVERNANCE,
            handler=_allow,
        ),
    ]


def has_governance_pre_hook(hooks: list[HookRegistration]) -> bool:
    return any(
        h.phase == HookPhase.PRE
        and h.capability_kind == CapabilityKind.GOVERNANCE
        and h.name == GOVERNANCE_HOOK_NAME
        for h in hooks
    )
