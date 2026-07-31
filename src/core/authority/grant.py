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
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.authority.clock import Clock
from core.authority.errors import AuthorityRefuseError
from core.authority.scope import EntailedScope, ScopeUndetermined
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

    #: WHAT THIS TASK ENTAILS, as path → capabilities (016, ADR-0056).
    #:
    #: The `task scope` term of Principle IV's intersection, and the only thing this feature
    #: adds to consent. `requested_scope` above stays the HARNESS half — tools and product
    #: actions, enforced in-process by the hooks — and this is the SECRETS half, enforced by
    #: the trust store against a grant it validates. ADR-0044 keeps those jurisdictions
    #: disjoint, so they live in one record as two fields rather than being merged.
    #:
    #: Still no credential material: these are paths, not tokens. A reader of a stored grant
    #: learns what the run may reach and gains no way to reach it.
    entailed_paths: Mapping[str, frozenset[str]] = Field(default_factory=dict)

    #: Which arrangement minted the token this grant authorises — `federated` when the
    #: organization's own IdP issued it, `platform_issued` when the platform did (US4).
    #: Recorded on the grant because "which protection was actually in force" is a property
    #: of the authority, not of the estate at the moment somebody asks.
    arrangement: Literal["federated", "platform_issued"] = "platform_issued"

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
    entailed_scope: EntailedScope | None = None,
    ceiling_paths: Mapping[str, frozenset[str]] | None = None,
    arrangement: Literal["federated", "platform_issued"] = "platform_issued",
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

    # ---- the task's own scope (016). Two refusals, and they are different claims.
    #
    # An UNDETERMINED scope means the platform cannot say what the task entails, which must
    # refuse rather than fall back to the ceiling: granting broadly to be safe is precisely
    # how a ceiling stops meaning anything (FR-004).
    #
    # A scope EXCEEDING the ceiling means the task wants more than the definition may ever
    # have. That is a defect somewhere upstream — a manifest, or a ceiling record — and
    # issuing the narrower intersection instead would paper over it, leaving a run that
    # half-works and a bug nobody sees (FR-003).
    entailed_paths: Mapping[str, frozenset[str]] = {}
    if entailed_scope is not None:
        try:
            entailed_scope.require_determined()
        except ScopeUndetermined as exc:
            raise AuthorityRefuseError(
                str(exc), reason_code="authority_refused", correlation_id=correlation_id
            ) from exc
        if ceiling_paths is not None and not entailed_scope.issubset_of(dict(ceiling_paths)):
            raise AuthorityRefuseError(
                "the task entails resources outside the agent definition's ceiling; the "
                "ceiling is the maximum a definition may EVER reach, so a task exceeding it "
                "is a defect upstream rather than a grant to narrow",
                reason_code="authority_refused",
                correlation_id=correlation_id,
            )
        entailed_paths = entailed_scope.paths

    issued_at = clock.now()
    return DelegationGrant(
        grant_id=secrets.token_hex(16),
        subject_user_id=subject_user_id,
        agent_definition_id=agent_definition_id,
        requested_scope=requested_scope,
        issued_at=issued_at,
        expires_at=issued_at + duration,
        entailed_paths=entailed_paths,
        arrangement=arrangement,
    )
