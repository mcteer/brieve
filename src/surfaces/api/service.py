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
import sys
from typing import Any

from adapters.anthropic_answering import build_ask_provider
from adapters.anthropic_relevance import build_relevance_judge
from core.answering.conversations.postgres import PostgresConversationStore
from core.answering.endorsed.corpus import resolve_endorsed
from core.answering.endorsed.postgres import PostgresEndorsedStore
from core.audit.destination_postgres import build_destination
from core.audit.local_store import run_connection_factory
from core.audit.postgres_query import PostgresEvidenceQuery
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.reconcile_service import PostgresReconciler
from core.authoring.owned import owned_repositories_from_env
from core.authority.ask_binding import AskAuthority
from core.authority.model_credential import BrokeredModelCredential
from core.authority.vault_fabric import VaultIdentityFabric
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.postgres import PostgresDurabilityProvider
from core.endorsed_sync import git_available, sync_source
from core.identity.mappings_store import VaultClaimMappings
from core.identity.tenant import resolve_tenant
from core.identity.types import SubjectKind
from core.runs.changes import PostgresChangeRequestStore, VaultChangeStatus
from core.runs.index import PostgresRunIndex
from core.threads.postgres import PostgresThreadStore
from surfaces.api.app import create_app
from surfaces.api.authority_submit import VaultAuthoritySubmitter
from surfaces.api.console import ENDORSED_SOURCES_PATH, ConsoleConfig
from surfaces.api.verification import (
    DEFAULT_TENANT_CLAIM,
    FederatedVerifier,
    TokenVerifier,
)
from surfaces.dispatch.nomad import NomadDispatcher
from surfaces.toolset import (
    AUTHORING_VOCABULARY,
    build_registry,
    known_actions,
    known_tools,
)

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
# Role bindings and ceilings may name authoring tools; handlers attach only in the
# authoring tier. Without the union, a correct operator binding refuses
# `unknown_ceiling_entry` on this surface and Build cannot start.
KNOWN_TOOLS = known_tools(_REGISTRY) | AUTHORING_VOCABULARY
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
    # 045's endorsed content, under the same brokered credential. **Wired here and not only in
    # the fixture**, which is the point 026/027's fourth analysis pass made about this file:
    # the parity rows compare two surfaces built from ONE set of collaborators, so a feature
    # present in the harness and absent from an assembly is a feature nobody can use and every
    # row is green about.
    endorsed_store = PostgresEndorsedStore(credentials=credentials)

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
    endorsed_store.migrate()

    # **THE TRANSPORT, STATED AT START RATHER THAN DISCOVERED AT THE CLICK.**
    #
    # This is a Python image and `git` is not a given. Without it the console renders the
    # endorsed-sources section perfectly, and every Review fails — which an administrator reads
    # as a problem with their repository, because that is what a sync failure normally is.
    #
    # It does NOT refuse to start, unlike the authoring tier's identical check. That tier
    # exists to publish, so no git means it can do nothing; this surface answers questions,
    # serves the console and reads evidence, all of which work. Refusing to start over a
    # capability most estates never use would trade a narrow gap for a total outage. So the
    # posture is stated once, loudly, where an operator reads it.
    if not git_available():
        print(
            "::endorsed:: tooling_missing: no `git` in this image, so endorsed sources cannot "
            "be synced or reviewed. Everything else on this surface is unaffected.",
            file=sys.stderr,
            flush=True,
        )

    def _kv_data(record: Any) -> dict[str, Any]:
        """KV v2 nests the body two levels down; anything unreadable is an empty mapping here.

        The parser refuses a malformed record loudly (`parse_endorsed_sources`), so this only
        has to survive the shapes Vault actually returns.
        """
        if not isinstance(record, dict):
            return {}
        data = record.get("data", record)
        inner = data.get("data", data) if isinstance(data, dict) else {}
        return inner if isinstance(inner, dict) else {}

    def endorsed_reader() -> Any:
        """The endorsed corpus in force, resolved once per ask.

        A closure over the fabric and the store rather than a built corpus, for the reason
        every reader in this file is a callable: a corpus built at assembly would be the state
        of the estate when the process started, so an adoption would take effect at the next
        deploy — which is not an adoption.

        `HARNESS_DEFAULT_TENANT` keys it from day one so ADR-0046 finds a boundary rather than
        a rewrite; a single-tenant deployment exercises the key without proving the wall.
        """
        return resolve_endorsed(
            read_sources=lambda: _kv_data(fabric.read_versioned(ENDORSED_SOURCES_PATH)),
            store=endorsed_store,
            tenant_id=resolve_tenant(),
        )

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
        # 047. Fail closed when unset — Propose refuses every repository.
        propose_owned_repositories=owned_repositories_from_env(),
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
            # **HOW IT AUTHENTICATES**, and until this line it did not.
            #
            # 044 granted `authority_submit` on the records the console may write and attached
            # it to this role. Nothing exchanged the workload identity for a token, so every
            # request went to Vault with no `X-Vault-Token` header, Vault answered 403, and the
            # console rendered "the trust fabric denied this change" — a governance decision
            # nobody made. Found by an administrator endorsing a source and asking whether
            # anything had happened.
            #
            # `credentials.login` per submit, not a token held at assembly: the same brokered
            # identity every other collaborator here uses, and nothing standing between calls.
            token_source=credentials.login,
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
        # 044's console, over the SAME fabric this assembly already holds. Callables in,
        # nothing constructed there — the module never learns which fabric it reads.
        #
        # `quorum_configured` is deployment configuration rather than something inferred: the
        # console must disclose an ungated change (FR-007), and inferring the posture from a
        # write's outcome would mean the first change of the day teaches the console what
        # estate it is in. An operator states it.
        console_config=ConsoleConfig(
            read_matrix=fabric.read_matrix,
            read_versioned=fabric.read_versioned,
            quorum_configured=os.environ.get("HARNESS_QUORUM_CONFIGURED", "").strip().lower()
            in {"1", "true", "yes"},
            endorsed_store=endorsed_store,
            sync_source=sync_source,
            tenant_id=resolve_tenant(),
        ),
        endorsed_reader=endorsed_reader,
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
