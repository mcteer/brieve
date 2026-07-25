# SPDX-License-Identifier: Apache-2.0
"""In-process fail-closed hook pipeline."""

from core.hooks.governance import builtin_governance_hooks
from core.hooks.types import CapabilityKind, HookContext, HookDecision, HookPhase, HookRegistration

__all__ = [
    "CapabilityKind",
    "HookContext",
    "HookDecision",
    "HookPhase",
    "HookRegistration",
    "builtin_governance_hooks",
]
