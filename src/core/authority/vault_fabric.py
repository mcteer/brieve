# SPDX-License-Identifier: Apache-2.0
"""The production identity fabric — authority resolved from the control-plane trust fabric.

Every feature from 002 to 009 resolved user scope, agent ceilings, policy, and product
entitlements through `FakeIdentityFabric` under `tests/harness/`. The behaviour those
features asserted was almost certainly right; what had never happened is any of it running
against the thing an operator actually configures. This is that.

**Two jurisdictions, and nothing here crosses between them.** A registration's
``ceiling_policies`` bound which *secrets* a run's token may read. The harness ceiling
record bounds which *tools* an agent may call. ADR-0044 requires them disjoint — "no rule
is duplicated across engines" — so neither is ever inferred from the other, in either
direction. That substitution is how a secrets grant would quietly become a tool grant, and
it is the single most dangerous shortcut available in this module.

**Every failure refuses, and none returns an empty scope.** An empty scope is a legitimate
answer meaning "this principal may do nothing"; a failure is the platform not knowing. They
must stay distinguishable through every layer, because one is a permissions decision and
the other is an outage — and ``AuthorityScope()`` in an exception handler is the shortest
path in this file and reads as fail-closed while destroying that distinction.

**No caching.** Policy is read on every step (FR-008). A cached scope used past its
freshness bound is a stale permission, and a narrowing that takes an interval to bite is
weaker than the guarantee 005 asserts. The cost is a network read per step, and it is the
cost of the guarantee rather than an oversight.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from core.authority.ceiling import parse_ceiling_record
from core.authority.errors import ResolutionRefused
from core.authority.types import AuthorityScope
from core.durability.credentials import VaultDatabaseCredentials, VaultReadFailed

#: Where the registry serves a registration, keyed by the id a run is started under.
REGISTRATION_PATH = "agent-registry/registration/display-name"

#: KV v2 puts data one level down. `harness-authority/data/...`, not `harness-authority/...`
#: — a detail that costs an afternoon exactly once, because the wrong path 404s and 404 is
#: how this module reports "no such record".
CEILING_PATH = "harness-authority/data/harness-ceilings"
ROLE_BINDING_PATH = "harness-authority/data/role-bindings"
POLICY_PATH = "harness-authority/data/policies"


class VaultIdentityFabric:
    """Resolves authority from the control-plane trust fabric, as an attested workload."""

    def __init__(
        self,
        *,
        credentials: VaultDatabaseCredentials,
        known_tools: Iterable[str],
        known_actions: Iterable[str],
        entitlement_source: Any | None = None,
    ) -> None:
        self._credentials = credentials
        self._known_tools = frozenset(known_tools)
        self._known_actions = frozenset(known_actions)
        self._entitlements = entitlement_source

    # ------------------------------------------------------------------ reads

    def _read(self, path: str) -> dict[str, Any] | None:
        """One trust-fabric read, with failures mapped to reason codes.

        The mapping is the point. `VaultReadFailed` already distinguishes a timeout from a
        refusal, and that distinction has to survive into the audit trail — a fabric that
        was slow and a fabric that was unreachable get different responses from whoever
        investigates.
        """
        try:
            return self._credentials.read_path(path)
        except VaultReadFailed as exc:
            raise ResolutionRefused(
                str(exc),
                reason_code="fabric_timeout" if exc.timed_out else "fabric_unreachable",
            ) from exc
        except Exception as exc:  # noqa: BLE001 — an unresolvable read must never permit
            # Including the identity being unavailable, which is what happens when this
            # runs outside an allocation. Refusing is right; permitting would mean a
            # process with no attested identity resolving authority for someone.
            raise ResolutionRefused(
                f"trust fabric read failed for {path!r}: {type(exc).__name__}: {exc}",
                reason_code="fabric_unreachable",
            ) from exc

    @staticmethod
    def _kv_data(response: dict[str, Any] | None) -> dict[str, Any] | None:
        """Unwrap a KV v2 envelope. ``{"data": {"data": {...}}}``."""
        if response is None:
            return None
        outer = response.get("data") or {}
        inner = outer.get("data")
        return inner if isinstance(inner, dict) else None

    # ------------------------------------------------------- IdentityFabric

    def resolve_ceiling(self, agent_definition_id: str) -> AuthorityScope:
        """The tool-authorization ceiling for this definition.

        Two reads, and both must succeed for different reasons. The registration proves
        the definition **exists** — an unregistered id must refuse rather than resolve to
        anything, including an empty ceiling that a later widening would fill. The ceiling
        record carries what it may **do**.
        """
        registration = self._read(f"{REGISTRATION_PATH}/{agent_definition_id}")
        if registration is None:
            raise ResolutionRefused(
                f"no registration for agent definition {agent_definition_id!r}",
                reason_code="unknown_agent_definition",
            )

        record = self._kv_data(self._read(f"{CEILING_PATH}/{agent_definition_id}"))
        if record is None:
            # The definition is registered and has a credential-issuance policy, and this
            # is precisely where inferring one jurisdiction from the other would happen.
            # It does not happen: a secrets grant is not a tool grant.
            raise ResolutionRefused(
                f"agent definition {agent_definition_id!r} is registered but has no "
                f"harness ceiling record; the credential-issuance policy is a different "
                f"jurisdiction (ADR-0044) and is never read as one",
                reason_code="missing_ceiling_record",
            )

        return parse_ceiling_record(
            record, known_tools=self._known_tools, known_actions=self._known_actions
        )

    def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
        """What this person may delegate, from the roles their claims resolved to."""
        roles = self._roles_for(subject_user_id)
        if not roles:
            raise ResolutionRefused(
                f"no role for subject {subject_user_id!r}",
                reason_code="no_role_for_subject",
            )

        scope = AuthorityScope()
        for role in sorted(roles):
            record = self._kv_data(self._read(f"{ROLE_BINDING_PATH}/{role}"))
            if record is None:
                raise ResolutionRefused(
                    f"role {role!r} has no binding record",
                    reason_code="unbound_role",
                )
            bound = parse_ceiling_record(
                record, known_tools=self._known_tools, known_actions=self._known_actions
            )
            # UNION across roles, then intersected downstream. Union is the only choice
            # that makes being granted a role additive — intersection would let a second
            # role REMOVE access, which nobody would predict from being given one.
            scope = AuthorityScope(
                tool_names=scope.tool_names | bound.tool_names,
                product_actions=scope.product_actions | bound.product_actions,
            )
        return scope

    def resolve_policy(self, agent_definition_id: str) -> AuthorityScope | None:
        """Current policy for this definition, read fresh on every call.

        ``None`` means unrestricted, and it is the *absence of a policy record* rather
        than a failure to read one — which is why `_read` raising is never caught here.
        """
        record = self._kv_data(self._read(f"{POLICY_PATH}/{agent_definition_id}"))
        if record is None:
            return None
        return parse_ceiling_record(
            record, known_tools=self._known_tools, known_actions=self._known_actions
        )

    def resolve_product_entitlements(self, subject_user_id: str, product: str) -> frozenset[str]:
        """What this **user** may do inside a managed product (ADR-0044 mirroring).

        Delegated to a source rather than answered here: a product's authorization system
        is outside this platform's boundary. Having no source is not "no entitlements" —
        that would be a denial nobody decided.
        """
        if self._entitlements is None:
            raise ResolutionRefused(
                f"no entitlement source configured for product {product!r}",
                reason_code="entitlement_unavailable",
            )
        result: frozenset[str] = self._entitlements.entitlements_for(subject_user_id, product)
        return result

    # ------------------------------------------------------------------ roles

    def _roles_for(self, subject_user_id: str) -> frozenset[str]:
        """The roles a subject holds.

        Overridden by the surface-aware assembly, which has the verified claims. The base
        implementation refuses rather than guessing: a fabric that invented a role would
        be deciding who someone is.
        """
        raise ResolutionRefused(
            f"no claims available for subject {subject_user_id!r}",
            reason_code="unknown_subject",
        )


class SubjectScopedVaultFabric(VaultIdentityFabric):
    """A :class:`VaultIdentityFabric` bound to one authenticated subject's roles.

    The roles come from the claims a surface already verified (008's `TokenVerifier` and
    `resolve_roles`), so this class does not re-derive them — a second derivation is a
    second answer to "who is this", and the two would diverge exactly when it mattered.
    """

    def __init__(self, *, roles: Iterable[str], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._roles = frozenset(roles)

    def _roles_for(self, subject_user_id: str) -> frozenset[str]:
        return self._roles


__all__ = ["SubjectScopedVaultFabric", "VaultIdentityFabric"]
