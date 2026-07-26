# SPDX-License-Identifier: Apache-2.0
"""Delegation grant — the requesting user's durable consent to a task.

Two-level authority (ADR-0026, FR-001/FR-002): the grant is the *human*-meaningful
unit ("I said yes to this task") and lives for hours; the per-step
:class:`~core.authority.types.TaskCredentialRef` manufactured under it is the
*technically*-meaningful one and lives for minutes.

Merging them would force a choice between a token that outlives its safety margin and
a run that dies when its token does. Keeping them apart is what lets a run survive a
disruption without anything long-lived being written down.

A grant holds **no credential material**. That is enforced structurally — there is no
field for it — rather than by convention.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict

from core.authority.clock import Clock
from core.authority.errors import AuthorityRefuseError
from core.authority.types import AuthorityScope

#: Ceiling on how long consent may last, absent a shorter definition-supplied maximum.
DEFAULT_MAX_RUN_DURATION = timedelta(hours=8)


class GrantExpiredError(AuthorityRefuseError):
    """Consent has lapsed.

    Deliberately *not* an ordinary refusal: an expired grant is withdrawn permission,
    and the run parks for re-consent rather than failing (FR-005). Callers on the
    resume path catch this to park; callers mid-run catch it at the same boundary.
    """

    def __init__(
        self,
        message: str = "delegation grant expired",
        *,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, reason_code="grant_expired", correlation_id=correlation_id)


class DelegationGrant(BaseModel):
    """Durable consent. Referenced by a checkpoint via ``grant_id`` only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    grant_id: str
    subject_user_id: str
    agent_definition_id: str
    requested_scope: AuthorityScope
    issued_at: datetime
    expires_at: datetime

    def is_expired(self, clock: Clock) -> bool:
        return clock.now() >= self.expires_at

    def assert_live(self, clock: Clock, *, correlation_id: str | None = None) -> None:
        """Raise :class:`GrantExpiredError` if consent has lapsed."""
        if self.is_expired(clock):
            raise GrantExpiredError(correlation_id=correlation_id)


def issue_grant(
    *,
    subject_user_id: str,
    agent_definition_id: str,
    requested_scope: AuthorityScope,
    clock: Clock,
    duration: timedelta,
    max_run_duration: timedelta = DEFAULT_MAX_RUN_DURATION,
    correlation_id: str | None = None,
) -> DelegationGrant:
    """Record consent, or refuse.

    Refuses a blank subject, a blank definition, or a duration exceeding the
    definition's maximum — a grant that outlives its definition's ceiling would let a
    run hold authority the definition never permitted.

    There is deliberately no ``renew`` here. Only a human extends consent, through a
    surface this feature does not build (ADR-0016).
    """
    if not subject_user_id.strip():
        raise AuthorityRefuseError(
            "requesting user identity is absent",
            reason_code="identity_unavailable",
            correlation_id=correlation_id,
        )
    if not agent_definition_id.strip():
        raise AuthorityRefuseError(
            "agent definition is absent",
            reason_code="identity_unavailable",
            correlation_id=correlation_id,
        )
    if duration <= timedelta(0):
        raise AuthorityRefuseError(
            "grant duration must be positive",
            reason_code="authority_refused",
            correlation_id=correlation_id,
        )
    if duration > max_run_duration:
        raise AuthorityRefuseError(
            "grant duration exceeds the agent definition's maximum run duration",
            reason_code="authority_refused",
            correlation_id=correlation_id,
        )

    issued_at = clock.now()
    return DelegationGrant(
        grant_id=secrets.token_hex(16),
        subject_user_id=subject_user_id,
        agent_definition_id=agent_definition_id,
        requested_scope=requested_scope,
        issued_at=issued_at,
        expires_at=issued_at + duration,
    )
