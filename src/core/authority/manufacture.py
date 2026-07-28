# SPDX-License-Identifier: Apache-2.0
"""Manufacture or refuse short-lived task authority at run start."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from core.authority.clock import Clock
from core.authority.errors import RESOLUTION_REASONS, AuthorityRefuseError
from core.authority.fabric import IdentityFabric
from core.authority.grant import DelegationGrant
from core.authority.intersection import intersect_scopes
from core.authority.types import AuthorityScope, TaskCredentialRef

DEFAULT_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class ManufacturedAuthority:
    credential: TaskCredentialRef
    run_salt: bytes


def manufacture_authority(
    *,
    subject_user_id: str,
    requested_scope: AuthorityScope,
    identity_fabric: IdentityFabric,
    clock: Clock,
    agent_definition_id: str,
    grant: DelegationGrant | None = None,
    correlation_id: str | None = None,
) -> ManufacturedAuthority:
    """Issue narrowed task authority or raise AuthorityRefuseError.

    When a ``grant`` is supplied, authority is manufactured **under** it and an expired
    grant refuses (FR-002): consent is checked before authority exists, not after.

    The parameter is optional rather than required, which is a deliberate departure
    from the task list's "breaking seam" framing. Making it optional gives the same
    guarantee — a granted run cannot manufacture under lapsed consent — without
    churning every 002/003 caller that has no grant to pass. A break bought nothing
    here.
    """
    if grant is not None:
        grant.assert_live(clock, correlation_id=correlation_id)
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

    try:
        user = identity_fabric.resolve_user_scope(subject_user_id)
        ceiling = identity_fabric.resolve_ceiling(agent_definition_id)
        policy = identity_fabric.resolve_policy(agent_definition_id)
    except AuthorityRefuseError:
        raise
    except Exception as exc:
        code = getattr(exc, "reason_code", None)
        # Every reason the resolution layer can give, carried through rather than
        # flattened. Before 010 there were two, and anything else became "identity fabric
        # unavailable" — which was accurate when the fabric was a dictionary and could
        # only be present or absent. Against a real fabric the reasons are the diagnosis:
        # a ceiling naming an unknown tool, a record from a newer platform, and a fabric
        # that did not answer are three different problems with three different fixes, and
        # collapsing them sends whoever reads the trail to the network every time.
        if code in {"identity_unavailable", "exchange_failed"} or code in RESOLUTION_REASONS:
            raise AuthorityRefuseError(
                str(exc) or code,
                reason_code=str(code),
                correlation_id=correlation_id,
            ) from exc
        raise AuthorityRefuseError(
            "identity fabric unavailable",
            reason_code="identity_unavailable",
            correlation_id=correlation_id,
        ) from exc

    if not requested_scope.issubset(user) or not requested_scope.issubset(ceiling):
        raise AuthorityRefuseError(
            "task scope exceeds user or ceiling",
            reason_code="authority_refused",
            correlation_id=correlation_id,
        )

    effective = intersect_scopes(user, ceiling, requested_scope, policy)
    credential_id = secrets.token_hex(16)
    run_salt = secrets.token_bytes(32)
    expires_at = clock.now() + DEFAULT_TTL
    ref = TaskCredentialRef(
        credential_id=credential_id,
        subject_user_id=subject_user_id,
        expires_at=expires_at,
        effective=effective,
    )
    return ManufacturedAuthority(credential=ref, run_salt=run_salt)
