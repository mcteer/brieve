# SPDX-License-Identifier: Apache-2.0
"""Mapping 4 of 4: framework run context to identity and correlation.

The deps object carried on an adapter-started run. It holds the governed run
produced by ``start_governed_run`` and nothing the core does not already own —
no scopes, no credentials, no audit state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.approvals import ApprovalHook, DenyAllApprovalHook
from core.durability import DurabilityProvider, InMemoryDurabilityProvider
from core.run import GovernedRun, RunState


@dataclass
class AdapterRunContext:
    """Deps for a governed agent run.

    ``governed_run`` is bound by ``start_adapter_run`` and is required before any
    tool mapping call; a missing or non-ACTIVE run denies rather than proceeds.
    """

    governed_run: GovernedRun
    approval_hook: ApprovalHook = field(default_factory=DenyAllApprovalHook)
    durability: DurabilityProvider = field(default_factory=InMemoryDurabilityProvider)

    @property
    def correlation_id(self) -> str:
        return self.governed_run.correlation_id

    @property
    def subject_user_id(self) -> str:
        return self.governed_run.subject_user_id

    @property
    def agent_definition_id(self) -> str:
        return self.governed_run.agent_definition_id

    def is_active(self) -> bool:
        """True when a governed run is bound and still ACTIVE."""
        return self.governed_run is not None and self.governed_run.state is RunState.ACTIVE
