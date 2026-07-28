# SPDX-License-Identifier: Apache-2.0
"""Built-in governance/enforcement hooks (must run first among co-resident hooks)."""

from __future__ import annotations

from core.dependencies.gate import DEPENDENCY_HOOK_NAME, dependency_pre_hook
from core.hooks.authority import AUTHORITY_HOOK_NAME, authority_pre_hook
from core.hooks.mirroring import MIRRORING_HOOK_NAME, mirroring_pre_hook
from core.hooks.types import (
    CapabilityKind,
    HookContext,
    HookDecision,
    HookPhase,
    HookRegistration,
)

GOVERNANCE_HOOK_NAME = "governance"

REQUIRED_GOVERNANCE_PRE_HOOKS = frozenset(
    {AUTHORITY_HOOK_NAME, MIRRORING_HOOK_NAME, GOVERNANCE_HOOK_NAME}
)


def _allow(_ctx: HookContext) -> HookDecision:
    return HookDecision(outcome="allow", reason_code="ok", message="allowed")


def builtin_governance_hooks() -> list[HookRegistration]:
    """Return required governance hooks: dependency → authority → mirroring → shell.

    The dependency gate runs FIRST among these, and the order is a decision rather than an
    accident. A call against an unreachable product cannot succeed whatever its authority
    says, so refusing it before manufacturing and checking authority avoids doing work
    that is certain to be wasted — and, more importantly, keeps the *reason* the caller
    sees accurate. Checking authority first would refuse a perfectly authorized call with
    a scope error when the actual problem is that a product is down, which sends whoever
    is debugging it to the wrong place entirely.

    It is inside this list rather than before the pipeline because a check placed before
    the pipeline is a second refusal path (Principle II), and gets none of the ordering or
    audit guarantees the pipeline provides.
    """
    return [
        HookRegistration(
            name=DEPENDENCY_HOOK_NAME,
            phase=HookPhase.PRE,
            capability_kind=CapabilityKind.GOVERNANCE,
            handler=dependency_pre_hook,
        ),
        HookRegistration(
            name=AUTHORITY_HOOK_NAME,
            phase=HookPhase.PRE,
            capability_kind=CapabilityKind.GOVERNANCE,
            handler=authority_pre_hook,
        ),
        HookRegistration(
            name=MIRRORING_HOOK_NAME,
            phase=HookPhase.PRE,
            capability_kind=CapabilityKind.GOVERNANCE,
            handler=mirroring_pre_hook,
        ),
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


def has_required_governance_hooks(hooks: list[HookRegistration]) -> bool:
    """All built-in governance pre-hooks must be present for enforcement to be whole."""
    present = {
        h.name
        for h in hooks
        if h.phase == HookPhase.PRE and h.capability_kind == CapabilityKind.GOVERNANCE
    }
    return REQUIRED_GOVERNANCE_PRE_HOOKS.issubset(present)


def has_governance_pre_hook(hooks: list[HookRegistration]) -> bool:
    """Alias — requires the full built-in governance pre-hook set (not name alone)."""
    return has_required_governance_hooks(hooks)
