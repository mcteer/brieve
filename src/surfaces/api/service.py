# SPDX-License-Identifier: Apache-2.0
"""The API as a served process — the assembly `create_app` has always deserved.

**Nothing here decides anything.** It reads the environment, constructs the production
collaborators, and hands them to `create_app`. Every rule this surface enforces lives in
the app and in core; this file only makes them reachable over a socket.

Deliberately separate from `app.py` so the assembly stays testable: a test builds
`create_app` with doubles, and this file builds it with the real thing. A module that did
both would make "the app under test" and "the app that ships" different objects assembled
by different code.
"""

from __future__ import annotations

import os

from adapters.anthropic_answering import build_ask_provider
from adapters.anthropic_relevance import build_relevance_judge
from core.answering.conversations.postgres import PostgresConversationStore
from core.audit.destination_postgres import build_destination
from core.audit.local_store import run_connection_factory
from core.audit.postgres_query import PostgresEvidenceQuery
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.reconcile_service import PostgresReconciler
from core.authority.ask_binding import AskAuthority
from core.authority.model_credential import BrokeredModelCredential
from core.authority.vault_fabric import VaultIdentityFabric
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.postgres import PostgresDurabilityProvider
from core.identity.mappings_store import VaultClaimMappings
from core.identity.types import SubjectKind
from core.runs.changes import PostgresChangeRequestStore, VaultChangeStatus
from core.runs.index import PostgresRunIndex
from core.threads.postgres import PostgresThreadStore
from surfaces.api.app import create_app
from surfaces.api.authority_submit import VaultAuthoritySubmitter
from surfaces.api.verification import (
    DEFAULT_TENANT_CLAIM,
    FederatedVerifier,
    TokenVerifier,
)
from surfaces.dispatch.nomad import NomadDispatcher
from surfaces.toolset import build_registry, known_actions, known_tools

#: What the platform can do, as the ceiling records name it — **derived from what actually
#: registered**, not declared here.
#:
#: This was a literal `frozenset` until 013, and it had to agree with three other copies. A
#: pack declaring `vault_read` would have made a correct ceiling record refuse
#: `unknown_ceiling_entry`, and that error names the ceiling — sending whoever reads it to
#: the ceiling and the trust fabric, both of which are fine, and not to the stale constant
#: in this module, which is not.
#: The Vault role this surface authenticates as — its own, matching its job id.
#:
#: Named rather than left to the `harness` default, which is what shipped: the default
#: role's bound claim is a different job, so every login was refused and the process died
#: before serving anything. The mcp service names its role for the same reason, one module
#: over.
VAULT_ROLE = "api"

_REGISTRY = build_registry()[0]
KNOWN_TOOLS = known_tools(_REGISTRY)
KNOWN_ACTIONS = known_actions(_REGISTRY)


def build() -> object:
    """Assemble the production API. Raises if the environment is incomplete.

    **Raises rather than defaults.** A surface that started with a missing issuer would be
    a surface verifying tokens against nothing, and it would look healthy — which is the
    fail-open shape every principle here exists to prevent.
    """
    issuer = _required("OIDC_ISSUER")
    jwks_uri = _required("OIDC_JWKS_URI")
    audience = os.environ.get("OIDC_AUDIENCE", "harness-api")

    credentials = VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role=VAULT_ROLE)
    fabric = VaultIdentityFabric(
        credentials=credentials, known_tools=KNOWN_TOOLS, known_actions=KNOWN_ACTIONS
    )

    audit_sink = PostgresAuditSink(credentials=credentials)
    run_index = PostgresRunIndex(credentials=credentials)
    thread_store = PostgresThreadStore(credentials=credentials)
    # 035. Under the same brokered credential as every other store here.
    ask_conversations = PostgresConversationStore(credentials=credentials)

    # WHICH model `ask` may call here — the same variable and the same meaning as the served MCP
    # surface's. Unset means no model is configured and every ask answers 503.
    #
    # **This assembly is why the fourth analysis pass existed.** 026 wired an ask authority into
    # `served.py` and not here, and 027 was about to wire a credential the same way — which would
    # have shipped the feature's own headline claim, *a person asks and gets an answer*, true on
    # one transport and false on the other. The parity rows would have stayed green throughout,
    # because they compare two surfaces built from ONE set of collaborators in a fixture; the
    # divergence lives in the assemblies, which no row constructs. ADR-0033 is about what a
    # deployment does, so the collaborators are wired in both places or the guarantee is a claim
    # about a test harness.
    ask_model = os.environ.get("ASK_MODEL", "").strip()

    # WHICH model this surface can build a relevance JUDGE for (043). Separate from
    # `ASK_MODEL` and required to be so: ADR-0067 forbids a model judging its own output, so the
    # two are never the same value, and one variable serving both would make the forbidden
    # configuration the easy one to write. Unset means every ask refuses `relevance_unbound`.
    relevance_model = os.environ.get("RELEVANCE_MODEL", "").strip()

    #: The vendor whose credential the judge is brokered against, named once rather than split
    #: out of a model identifier in two assemblies that could drift.
    _RELEVANCE_VENDOR = "anthropic"
    # Idempotent, and run at start rather than by a migration step: every one of these is
    # IF NOT EXISTS, and a surface that cannot create its own tables cannot serve anyway.
    audit_sink.migrate()
    run_index.migrate()
    thread_store.migrate()
    ask_conversations.migrate()

    # The approved claim-to-role mappings, read back from the same gated path the submit
    # endpoint writes to. Without this the verifier holds no mappings, `resolve_roles`
    # returns empty for every token, and the surface refuses every authenticated request
    # — which it did, for any identity provider, until the read end of the loop existed.
    claim_mappings = VaultClaimMappings(
        credentials=credentials, data_path=_required("AUTHORITY_CONTROLLED_PATH")
    )

    def verifier_for(kind: SubjectKind, *, iss: str, jwks: str) -> TokenVerifier:
        return TokenVerifier(
            issuer=iss,
            audience=audience,
            jwks_uri=jwks,
            mappings_source=claim_mappings,
            # Auth0, Okta and Ping all namespace custom claims, so the tenant does not
            # arrive under a bare name. Configurable rather than assumed: the default is
            # right for a provider that emits `tenant` and wrong for every provider that
            # cannot, and getting it wrong refuses every token with `no_tenant`.
            tenant_claim=os.environ.get("OIDC_TENANT_CLAIM", DEFAULT_TENANT_CLAIM),
            subject_kind=kind,
        )

    verifiers = [verifier_for(SubjectKind.HUMAN, iss=issuer, jwks=jwks_uri)]

    # Machines, only where a deployment says so. Absent this the surface accepts people
    # and refuses everything else, which is the fail-closed default — and a change from
    # what shipped, where a `client_credentials` token was admitted as a person because
    # nothing checked. A leaked client secret was a working operator login.
    #
    # Usually the SAME issuer: Auth0, Okta, Ping and Entra all serve both grants from one.
    # It is still named rather than assumed, because "this surface accepts machine
    # credentials" is a posture somebody decides, not one they discover.
    workload_issuer = os.environ.get("OIDC_WORKLOAD_ISSUER", "").strip()
    if workload_issuer:
        verifiers.append(
            verifier_for(
                SubjectKind.WORKLOAD,
                iss=workload_issuer,
                jwks=os.environ.get("OIDC_WORKLOAD_JWKS_URI", "").strip() or jwks_uri,
            )
        )

    return create_app(
        # One verifier or two, always through the federated wrapper — so the branch that
        # accepts a second kind is the same code path in both cases rather than one that
        # only runs where somebody enabled it.
        token_verifier=FederatedVerifier(verifiers),
        run_dispatcher=NomadDispatcher(run_index=run_index),
        evidence_query=PostgresEvidenceQuery(
            credentials=VaultDatabaseCredentials(
                identity=NomadWorkloadIdentity(),
                role=VAULT_ROLE,
                creds_path="database/creds/evidence",
            )
        ),
        audit_sink=audit_sink,
        authority_submitter=VaultAuthoritySubmitter(
            # The gated path claim-mapping changes are written to. Required rather than
            # defaulted: a submitter pointed at the wrong path writes an ungated change
            # that looks approved, which is the one failure mode this whole mechanism
            # exists to prevent.
            controlled_path=_required("AUTHORITY_CONTROLLED_PATH"),
        ),
        run_index=run_index,
        durability=PostgresDurabilityProvider(credentials=credentials),
        change_requests=PostgresChangeRequestStore(credentials=credentials),
        change_status=VaultChangeStatus(),
        definitions=fabric,
        thread_store=thread_store,
        ask_conversations_store=ask_conversations,
        # 015. The comparison runs under the platform's own run-role credential and is
        # authorized by the caller's evidence scope — see `reconcile_evidence_for`. The
        # destination is built from the same config the mcp service reads, and `None`
        # there is the ABSENT posture rather than a broken assembly.
        reconciler=PostgresReconciler(
            connection_factory=run_connection_factory(credentials),
            destination=build_destination(),
        ),
        # 026 + 027, from the fabric this assembly already holds. Governance first: an
        # unqualified model is unreachable here as everywhere, and a configured provider is not
        # a qualification.
        ask_authority=AskAuthority(
            read_binding=fabric.read_ask_binding, read_matrix=fabric.read_matrix
        ),
        # 043's RELEVANCE JUDGE, wired on exactly the ask provider's terms.
        #
        # A FACTORY, not a judge: called once per question, and the credential it holds was
        # brokered for that question and is dropped with it. A judge built at assembly would
        # hold a vendor key for the life of the process, which is the standing credential
        # Principle IV forbids relocated rather than removed.
        #
        # ADR-0067 decides WHICH model this may be, and the trust fabric records it: the
        # binding names a `judge` cell, and `resolve_relevance` refuses one naming the
        # answering model. This assembly supplies the mechanism and decides nothing.
        relevance_model=relevance_model or "unconfigured",
        relevance_judges=(
            (
                lambda cell: build_relevance_judge(
                    cell,
                    BrokeredModelCredential(read=fabric.read_versioned)
                    .obtain(_RELEVANCE_VENDOR)
                    .secret,
                )
            )
            if relevance_model
            else None
        ),
        ask_model=ask_model or "unconfigured",
        # A FACTORY, called once per question with material brokered for that question and
        # dropped with the answer. A provider built here would hold the credential for the life
        # of the process — the standing credential Principle IV forbids, moved rather than
        # removed. The key never appears in this module: it travels inside a `ModelCredential`
        # to `build_ask_provider`, which is what lets the no-static-credentials gate keep
        # asserting, with no exemption, that no surface names one.
        ask_providers=(
            (lambda source, secret: build_ask_provider(source, secret, model=ask_model))
            if ask_model
            else None
        ),
        credential_source=(
            BrokeredModelCredential(read=fabric.read_versioned) if ask_model else None
        ),
    )


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. This surface authenticates humans against the "
            "organization's OIDC provider and will not start without knowing which one."
        )
    return value


def main() -> None:  # pragma: no cover - process entrypoint
    import uvicorn

    bind = os.environ.get("API_BIND", "127.0.0.1:8081")
    host, _, port = bind.rpartition(":")
    uvicorn.run(
        build(),  # type: ignore[arg-type]  # FastAPI is an ASGI app; `build` returns object
        host=host or "127.0.0.1",
        port=int(port or 8081),
        log_level="info",
    )


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    main()
