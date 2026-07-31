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

import re
from collections.abc import Iterable, Mapping
from typing import Any

from core.authority.bindings import DefinitionBindings, parse_definition_bindings
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
#: Which packs a definition reaches, its per-role model bindings, and its tier (013).
#: Written by the same apply as the ceiling, so a definition never holds one without
#: the other.
DEFINITION_BINDINGS_PATH = "harness-authority/data/definition-bindings"
#: The Qualified Model Matrix (013). One record, not one per definition: a cell is an
#: estate-wide authorization fact, and per-definition copies would let two definitions
#: disagree about whether a model is qualified.
MATRIX_PATH = "harness-authority/data/model-matrix"

#: Policies the `agent_registry` engine appends to every registration on its own.
#:
#: Terraform registers one policy; Vault stores three. The engine adds these unless the
#: registration sets ``no_default_ceiling_policy``, which this repository has never set —
#: **so the effective ceiling has never been the declared one, and nothing had looked.**
#:
#: Their contents are benign (self-inspection, and reading two well-known policies), and
#: that is exactly why this is worth naming rather than shrugging at: the finding is not
#: that Vault granted something dangerous, it is that a difference existed where the whole
#: point of the mechanism is that no difference exists. The next default the engine adds
#: may not be benign, and without this there would still be nothing watching.
ENGINE_APPENDED_POLICIES = frozenset({"default", "default-ceiling"})

#: How the `agent_registry` engine says a registration is not there.
#:
#: **It answers 400, not 404**, with this in the body. Found against the live enclave and
#: not derivable from anywhere else: KV v2 404s a missing key, so a reader that generalised
#: from KV — which is every other read in this module — reports an unregistered definition
#: as an unreachable fabric. That is the one confusion `read_path` exists to prevent, and it
#: would have looked like an outage to anyone reading the trail.
REGISTRY_ABSENT_SIGNATURE = "does not exist"


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

    def _read_registration(self, agent_definition_id: str) -> dict[str, Any] | None:
        """Read a registration, treating the engine's own "not there" as absence.

        Separate from :meth:`_read` because the absence signature belongs to the registry
        engine, and the generic reader must not learn one backend's dialect — the next
        engine will have a different one, and a generic reader that accumulated them would
        eventually match a real error as absence.
        """
        try:
            return self._credentials.read_path(f"{REGISTRATION_PATH}/{agent_definition_id}")
        except VaultReadFailed as exc:
            if exc.status == 400 and REGISTRY_ABSENT_SIGNATURE in exc.detail:
                return None
            raise ResolutionRefused(
                str(exc),
                reason_code="fabric_timeout" if exc.timed_out else "fabric_unreachable",
            ) from exc
        except Exception as exc:  # noqa: BLE001 — an unresolvable read must never permit
            raise ResolutionRefused(
                f"registration read failed for {agent_definition_id!r}: {type(exc).__name__}",
                reason_code="fabric_unreachable",
            ) from exc

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
        registration = self._read_registration(agent_definition_id)
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

    def resolve_ceiling_paths(self, agent_definition_id: str) -> dict[str, frozenset[str]]:
        """The SECRETS half of the ceiling, as path → capabilities (016).

        `resolve_ceiling` above returns the harness half — tools and product actions, which
        the hooks enforce in-process. This returns what the registration's ceiling *policy*
        permits, which is what a task-scoped grant is bounded by. ADR-0044 keeps the two
        jurisdictions disjoint; this reads the other one rather than merging them.

        Parsed from the policy document because that is where the truth is. Deriving it from
        anywhere else — a convention, a second record — would create a copy that can disagree
        with what Vault actually enforces, and the copy would be the one we checked against.
        """
        registration = self._read_registration(agent_definition_id)
        if registration is None:
            raise ResolutionRefused(
                f"no registration for agent definition {agent_definition_id!r}",
                reason_code="unknown_agent_definition",
            )
        permitted: dict[str, frozenset[str]] = {}
        for name in registration.get("ceiling_policies") or []:
            # `default` and `default-ceiling` are Vault's own additions (ADR-0050) and grant
            # nothing at the agent secret space, so skipping them keeps the parse to policies
            # this platform authored.
            if name in ("default", "default-ceiling"):
                continue
            document = self._read(f"sys/policies/acl/{name}")
            if document is None:
                continue
            permitted.update(_policy_paths(str(document.get("policy", ""))))
        return permitted

    def resolve_definition_bindings(self, agent_definition_id: str) -> DefinitionBindings:
        """Which packs this definition reaches, its binding map, and its tier.

        **Refuses loudly when absent**, on the 010 ceiling pattern. A definition with no
        bindings record is not a definition that reaches nothing — those are different
        claims, and resolving the second to the first would let a record that failed to
        apply present as a definition deliberately scoped to nothing. The Terraform writes
        this in the same apply as the ceiling precisely so the absence means something went
        wrong rather than something was omitted.
        """
        record = self._kv_data(self._read(f"{DEFINITION_BINDINGS_PATH}/{agent_definition_id}"))
        if record is None:
            raise ResolutionRefused(
                f"agent definition {agent_definition_id!r} has no definition-bindings "
                f"record; it is written by the same apply as the ceiling, so its absence "
                f"means the apply is incomplete rather than that the definition reaches "
                f"nothing",
                reason_code="missing_ceiling_record",
            )
        return parse_definition_bindings(record, agent_definition_id=agent_definition_id)

    def read_matrix(self) -> Mapping[str, Any]:
        """The Qualified Model Matrix, raw. Parsing belongs to `core.authority.matrix`.

        Refuses loudly when absent for the same reason as above, and with a sharper
        consequence: an empty matrix resolves every binding map to `unqualified_cell`, so a
        matrix that failed to apply would present as every definition in the estate being
        wrongly configured.
        """
        record = self._kv_data(self._read(MATRIX_PATH))
        if record is None:
            raise ResolutionRefused(
                "no Qualified Model Matrix record; an absent matrix would refuse every "
                "binding map as unqualified, so this refuses as a fabric problem rather "
                "than as an estate of misconfigured definitions",
                reason_code="missing_ceiling_record",
            )
        return record

    def observed_policies(self, agent_definition_id: str) -> dict[str, list[str]]:
        """What the registry actually holds, split into configured and engine-appended.

        The fabric cannot see what Terraform *declared* — that lives in HCL, not in Vault.
        What it can see is the effective set and which members of it the engine adds on its
        own, and separating those is what turns research Finding 2 from a surprise into a
        record. A resolution that reported only the effective list would be accurate and
        would still leave a reader believing an operator had asked for all three.
        """
        registration = self._read_registration(agent_definition_id)
        if registration is None:
            raise ResolutionRefused(
                f"no registration for agent definition {agent_definition_id!r}",
                reason_code="unknown_agent_definition",
            )
        effective = [str(p) for p in (registration.get("data") or {}).get("ceiling_policies") or ()]
        return {
            "effective": sorted(effective),
            "engine_appended": sorted(set(effective) & ENGINE_APPENDED_POLICIES),
            "configured": sorted(set(effective) - ENGINE_APPENDED_POLICIES),
        }

    def list_definitions(self) -> list[str]:
        """Every registered agent definition id, tenant-wide.

        The registry is one per deployment and carries no tenant of its own, so "tenant-
        wide" is structural here rather than filtered — a limit recorded in the conformance
        contract rather than hidden, because a multi-tenant deployment sharing one registry
        would disclose definitions across tenants and the gap would look closed until
        someone deployed that topology.
        """
        try:
            keys = self._credentials.list_path(REGISTRATION_PATH)
        except VaultReadFailed as exc:
            raise ResolutionRefused(
                str(exc),
                reason_code="fabric_timeout" if exc.timed_out else "fabric_unreachable",
            ) from exc
        except Exception as exc:  # noqa: BLE001 — an unlistable registry must not read as empty
            raise ResolutionRefused(
                f"registry could not be listed: {type(exc).__name__}",
                reason_code="fabric_unreachable",
            ) from exc
        # An empty registry is a legitimate answer; an unreachable one raised above. The
        # difference matters because "no agents exist" and "we could not look" produce the
        # same screen otherwise, and only one of them is worth waiting out.
        return sorted(keys or ())

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


def _policy_paths(document: str) -> dict[str, frozenset[str]]:
    """Pull `path "x" { capabilities = [...] }` out of a Vault policy document.

    A deliberately small parser rather than an HCL dependency: these documents are written by
    this repository's own Terraform, in one shape, and a general parser would be a larger
    surface for no gain. If that ever stops being true this should fail loudly rather than
    silently return fewer paths — which is why an unparseable block yields nothing rather
    than a permissive default.
    """
    found: dict[str, frozenset[str]] = {}
    for match in re.finditer(
        r'path\s+"([^"]+)"\s*\{[^}]*capabilities\s*=\s*\[([^\]]*)\]', document, re.S
    ):
        path, raw = match.group(1), match.group(2)
        caps = frozenset(c.strip().strip("\"'") for c in raw.split(",") if c.strip())
        if caps:
            found[path] = caps
    return found
