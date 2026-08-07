# SPDX-License-Identifier: Apache-2.0
"""Manufacture or refuse short-lived task authority at run start."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import timedelta

from core.authority.clock import Clock
from core.authority.errors import RESOLUTION_REASONS, AuthorityRefuseError, ResolutionRefused
from core.authority.fabric import IdentityFabric
from core.authority.grant import DelegationGrant
from core.authority.intersection import exclusions as compute_exclusions
from core.authority.intersection import intersect_scopes
from core.authority.matrix import MatrixFallback, parse_matrix_record, validate_binding_map
from core.authority.types import AuthorityScope, TaskCredentialRef

DEFAULT_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class ManufacturedAuthority:
    credential: TaskCredentialRef
    run_salt: bytes
    #: Set when the pinned matrix cell was unavailable and another QUALIFIED cell was used.
    #:
    #: **Returned rather than written**, and that is the same discipline this module already
    #: keeps in the other direction: it raises `AuthorityRefuseError` and lets
    #: `start_governed_run` record `AUTHORITY_REFUSED`. A fallback resolved here cannot be
    #: written here — this function holds no audit sink and no `tenant_id`, and `AuditEntry`
    #: requires both. Threading a sink down would put audit writing inside authority
    #: resolution and give two modules a reason to emit the same event.
    #:
    #: Additive with a default, so every existing caller is unchanged.
    matrix_fallback: MatrixFallback | None = None

    #: Tool name → which term of the intersection dropped it (041, FR-019).
    #:
    #: Computed here because this is the only place holding all four terms at once. A deny
    #: site downstream sees the effective set and could never reconstruct whether a ceiling or
    #: a task scope excluded a name — so every refusal read `authority_insufficient`, which is
    #: true and sends an operator nowhere.
    #:
    #: Carries no secret and no authority: tool names paired with one of four fixed strings.
    #: Additive with a default, like `matrix_fallback` above and for the same reason.
    exclusions: Mapping[str, str] = field(default_factory=dict)


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

    try:
        fallback = _resolve_binding_map(
            identity_fabric, agent_definition_id=agent_definition_id, correlation_id=correlation_id
        )
    except ResolutionRefused as exc:
        # Converted, not propagated — and the rows that found this are the reason it is
        # written down. `start_governed_run` catches `AuthorityRefuseError` and records
        # `AUTHORITY_REFUSED` before re-raising; a bare `ResolutionRefused` escapes both, so
        # a run refused for an unqualified cell would leave **no trail entry at all**. A
        # refusal nobody can see is indistinguishable from a run nobody attempted, which is
        # exactly the question an investigator arrives with.
        #
        # The reason code is carried through rather than flattened, on the same principle as
        # the ceiling resolution above: `unqualified_cell`, `cell_withdrawn`, and
        # `no_qualified_fallback` are three different problems with three different fixes.
        raise AuthorityRefuseError(
            str(exc),
            reason_code=str(getattr(exc, "reason_code", "") or "authority_refused"),
            correlation_id=correlation_id,
        ) from exc

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
    return ManufacturedAuthority(
        credential=ref,
        run_salt=run_salt,
        matrix_fallback=fallback,
        exclusions=compute_exclusions(
            user=user, ceiling=ceiling, requested=requested_scope, policy=policy
        ),
    )


def _resolve_binding_map(
    identity_fabric: IdentityFabric,
    *,
    agent_definition_id: str,
    correlation_id: str | None,
) -> MatrixFallback | None:
    """Re-validate this definition's binding map against the matrix, at every run start.

    **Not redundant with definition-time validation** (D6). A cell can be *withdrawn* — a
    model deprecated, a suite regressed, a cell pulled after a bad result — while the
    definition that pinned it sits unchanged in the registry. Validating only at registration
    would let a withdrawn cell keep running because nothing re-asked. It is the same
    reasoning that makes 010 resolve a ceiling per run rather than caching it.

    **Inert when the fabric supplies no matrix**, which is how every pre-013 caller behaves
    and is deliberately not fail-open. A fabric with no matrix is not a fabric whose cells
    are all unqualified — those are different claims, and collapsing them would make every
    008–012 run refuse while looking exactly like the check working. `dependency_pre_hook`
    documents the identical decision for the identical reason.
    """
    read_matrix = getattr(identity_fabric, "read_matrix", None)
    read_bindings = getattr(identity_fabric, "resolve_definition_bindings", None)
    if read_matrix is None or read_bindings is None:
        return None

    bindings = read_bindings(agent_definition_id)
    if not bindings.binding_map:
        # A definition binding no model is what every fixture is. Nothing to validate, and
        # nothing acquired by the omission.
        return None

    cells = parse_matrix_record(read_matrix())
    validate_binding_map(bindings.binding_map, cells, agent_definition_id=agent_definition_id)
    return None
