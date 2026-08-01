# SPDX-License-Identifier: Apache-2.0
"""The MCP surface, served — 019, closing ROADMAP gap 0f.

`McpTransport` has executed every operation against the governed core for four features and
been reachable by nobody: constructed nowhere in `src/`, its only caller a test fixture, with
no protocol framing anywhere in the tree. The surface-parity gate passed the whole time
because it compares the transport *class*, and the class is correct.

This module is the three things that had no coverage: **framing**, **session identity**, and
**assembly**. It adds no operation and changes no behaviour of the transport it serves.

**Assembly is why this cannot be tested by constructing an object.** It is the one path no
unit test touches — the reason ROADMAP gap 0d exists and the reason 017 was built — so the
rows for this module drive a running process over a real socket.
"""

from __future__ import annotations

import os
import sys
from typing import Any
from weakref import WeakKeyDictionary

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import Context, FastMCP
from pydantic import AnyHttpUrl

from core.audit.destination_postgres import build_destination
from core.audit.local_store import run_connection_factory
from core.audit.postgres_query import PostgresEvidenceQuery
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.reconcile_service import PostgresReconciler
from core.authority.vault_fabric import VaultIdentityFabric
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.postgres import PostgresDurabilityProvider
from core.identity.mappings_store import VaultClaimMappings
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.runs.changes import PostgresChangeRequestStore, VaultChangeStatus
from core.runs.index import PostgresRunIndex
from core.threads.postgres import PostgresThreadStore
from surfaces.api.authority_submit import VaultAuthoritySubmitter
from surfaces.api.verification import (
    AuthenticationRefused,
    FederatedVerifier,
    TokenVerifier,
)
from surfaces.dispatch.nomad import NomadDispatcher
from surfaces.mcp.operations import governance_sentence, operations
from surfaces.mcp.transport import McpResult, McpTransport
from surfaces.toolset import build_registry, known_actions, known_tools

#: The workload identity this surface presents. Its own role, not the API's — a role bound to
#: a different job id is a service that starts and authenticates as nothing, which the API
#: paid for once already.
VAULT_ROLE = "mcp-surface"

#: Where the database answers, AS SEEN FROM THIS PROCESS.
#:
#: **This is passed at construction, and no `src/core/` module changes to make that possible.**
#: Every collaborator below already accepts `host` as a keyword; `surfaces/api/service.py`
#: already passes one. An earlier plan proposed adding an environment-driven host to four core
#: modules, which would have made the Principle V verdict ("the core is untouched") false —
#: Principle V names *audit schema* and *durability* as sealed core requiring security-maintainer
#: review. The seam existed and was merely unused from an assembly.
#:
#: The default stays loopback so nothing outside an allocation changes.
DB_HOST_ENV = "HARNESS_DB_HOST"

_REGISTRY = build_registry()[0]
KNOWN_TOOLS = known_tools(_REGISTRY)
KNOWN_ACTIONS = known_actions(_REGISTRY)


def _required(name: str) -> str:
    """FR-003 in one function.

    A surface that started with a missing issuer would verify tokens against nothing and look
    healthy — the fail-open shape every principle here exists to prevent. It refuses to start
    and names what was missing.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(
            f"{name} is not set. This surface acts as the CALLING USER and will not start "
            f"without knowing which identity provider to verify them against. Starting "
            f"anyway would serve a surface that authenticates nobody while answering."
        )
    return value


def _db_host() -> str:
    return os.environ.get(DB_HOST_ENV, "").strip() or "127.0.0.1"


def build_transport() -> McpTransport:
    """Assemble the transport from the collaborators the API uses. **No substitutes** (FR-002).

    `McpTransport` defaults several collaborators to in-memory implementations, which is right
    for the class rows and wrong here: an in-memory thread store would serve a client happily
    and lose everything, and every existing row would still pass. So each is passed explicitly,
    and the ones that are not are the ones the transport genuinely does not take.
    """
    host = _db_host()
    credentials = VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role=VAULT_ROLE)

    audit_sink = PostgresAuditSink(credentials=credentials, host=host)
    run_index = PostgresRunIndex(credentials=credentials, host=host)
    thread_store = PostgresThreadStore(credentials=credentials, host=host)
    audit_sink.migrate()
    run_index.migrate()
    thread_store.migrate()

    return McpTransport(
        # THE SCHEDULER'S ADDRESS IS CONFIGURATION, and leaving it defaulted is a defect
        # this repository has now made twice.
        #
        # `NomadDispatcher()` defaults to `http://127.0.0.1:4646` — correct for a host
        # process and wrong for an allocation, and doubly wrong for a BRIDGE one, where
        # loopback is the container itself. 014 found the same omission in the sweeper,
        # where every resume failed `Connection refused` on a path nobody was watching for
        # five features. Here the jobspec sets NOMAD_ADDR and the first version of this
        # assembly ignored it — caught by US3's rows on their first run, because starting a
        # run is the only operation that dispatches.
        run_dispatcher=NomadDispatcher(
            run_index=run_index,
            nomad_addr=os.environ.get("NOMAD_ADDR") or "http://127.0.0.1:4646",
        ),
        audit_sink=audit_sink,
        evidence_query=PostgresEvidenceQuery(
            credentials=VaultDatabaseCredentials(
                identity=NomadWorkloadIdentity(),
                role=VAULT_ROLE,
                creds_path="database/creds/evidence",
            ),
            host=host,
        ),
        authority_submitter=VaultAuthoritySubmitter(
            controlled_path=_required("AUTHORITY_CONTROLLED_PATH"),
        ),
        run_index=run_index,
        durability=PostgresDurabilityProvider(credentials=credentials, host=host),
        change_requests=PostgresChangeRequestStore(credentials=credentials, host=host),
        change_status=VaultChangeStatus(),
        definitions=VaultIdentityFabric(
            credentials=credentials, known_tools=KNOWN_TOOLS, known_actions=KNOWN_ACTIONS
        ),
        thread_store=thread_store,
        reconciler=PostgresReconciler(
            connection_factory=run_connection_factory(credentials),
            destination=build_destination(),
        ),
    )


def build_verifier() -> FederatedVerifier:
    """The caller's credential, verified the way the other surface verifies it.

    **Reused, never rebuilt** (FR-009). A second path to a subject is a second place for the
    subject to be wrong, and that failure is silent by construction: a server that resolved
    subjects its own way would answer every call correctly and quietly collapse the delegation
    chain into whatever it decided.
    """
    issuer = _required("OIDC_ISSUER")
    jwks_uri = _required("OIDC_JWKS_URI")
    audience = os.environ.get("OIDC_AUDIENCE", "harness-api")

    credentials = VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role=VAULT_ROLE)
    # No `host` here, and the asymmetry is correct rather than an oversight: this reads claim
    # mappings from the TRUST STORE, not the database. Its address comes from VAULT_ADDR the
    # way every Vault client's does. Six of the seven collaborators in this module take a
    # database host; this is the seventh and it would have no use for one.
    claim_mappings = VaultClaimMappings(
        credentials=credentials,
        data_path=_required("AUTHORITY_CONTROLLED_PATH"),
    )

    def verifier_for(kind: SubjectKind, *, iss: str, jwks: str) -> TokenVerifier:
        return TokenVerifier(
            issuer=iss,
            audience=audience,
            jwks_uri=jwks,
            mappings_source=claim_mappings,
            tenant_claim=os.environ.get("OIDC_TENANT_CLAIM", "tenant"),
            subject_kind=kind,
        )

    verifiers = [verifier_for(SubjectKind.HUMAN, iss=issuer, jwks=jwks_uri)]

    workload_issuer = os.environ.get("OIDC_WORKLOAD_ISSUER", "").strip()
    workload_jwks = os.environ.get("OIDC_WORKLOAD_JWKS_URI", "").strip()
    if workload_issuer and workload_jwks:
        verifiers.append(
            verifier_for(SubjectKind.WORKLOAD, iss=workload_issuer, jwks=workload_jwks)
        )

    return FederatedVerifier(verifiers)


class SessionSubjects:
    """One subject per session, fixed at the handshake (FR-013a) — and re-checked (FR-013).

    **These two are not in tension and the distinction is the whole of it.** *Who* the session
    belongs to is settled once and never revisited. *Whether they may still act* is settled on
    every operation. Reading "fixed at the handshake" as "verified at the handshake" produces a
    session that outlives the credential that opened it, which is what FR-013 forbids and what
    Principle IV forbids generally — a standing authority is one nobody re-checks.

    A lapsed credential therefore moves the OPERATION to refused. It does not change, reassign,
    or clear the session's subject.

    **Keyed on the live session object**, held weakly so a disconnect releases the binding
    without anything having to remember to. An earlier draft keyed on the bearer token, which
    silently made every distinct credential its own "session" — the requirement would have been
    unfalsifiable, because two callers could never have collided by construction.
    """

    def __init__(self) -> None:
        self._bound: WeakKeyDictionary[object, str] = WeakKeyDictionary()

    def claim(self, session: object, subject_id: str) -> None:
        """Bind, or refuse if this session already belongs to somebody else."""
        held = self._bound.get(session)
        if held is None:
            self._bound[session] = subject_id
            return
        if held != subject_id:
            raise AuthenticationRefused(
                "this session is bound to a different subject",
                reason_code="session_subject_changed",
            )

    def subject_of(self, session: object) -> str | None:
        return self._bound.get(session)


def result_payload(result: McpResult) -> dict[str, Any]:
    """What a client receives, shaped so four outcomes stay distinguishable (FR-007).

    Refused, unknown operation, malformed request, and transport failure call for four
    different responses from a client. Collapsing them would make every denial look like a
    broken platform and every outage look like a policy decision — and it would tell a caller
    which operations exist by which error they received.
    """
    return {"ok": result.ok, "status": result.status, **result.payload}


__all__ = [
    "DB_HOST_ENV",
    "VAULT_ROLE",
    "SessionSubjects",
    "build_transport",
    "build_verifier",
    "result_payload",
]


class HarnessTokenVerifier:
    """The SDK's `TokenVerifier` protocol, answered by the platform's own verification.

    **Called on every request by the SDK's bearer middleware**, which is FR-013 for free: a
    session established with a valid credential stops authorizing the moment that credential
    stops verifying. Nothing here caches a verdict.

    Returning `None` means refuse, and every refusal path returns `None` rather than raising
    past the middleware — a surface that leaked an exception here would answer a bad
    credential with a stack trace instead of a denial.
    """

    def __init__(self, verifier: FederatedVerifier) -> None:
        self._verifier = verifier
        #: Verified subjects by token, so a tool handler can recover the full subject the
        #: platform resolved rather than reconstructing one from the SDK's flattened view.
        self._subjects: dict[str, AuthenticatedSubject] = {}

    async def verify_token(self, token: str) -> Any:
        try:
            subject = self._verifier.verify(token)
        except AuthenticationRefused as refused:
            # THE REASON, NEVER THE CREDENTIAL. A refusal with no diagnostic is a support
            # ticket that cannot be answered — and printing the token to make it answerable
            # would put a live bearer credential in an allocation log every operator can read.
            # The reason code names the decision; the token is not written anywhere.
            print(
                f"::mcp-surface:: refused a caller — {refused.reason_code}",
                file=sys.stderr,
                flush=True,
            )
            return None
        except Exception as exc:  # noqa: BLE001 — an unverifiable credential is a refusal
            print(
                f"::mcp-surface:: could not verify a caller — {type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None

        self._subjects[token] = subject
        return AccessToken(
            token=token,
            client_id=subject.subject_user_id,
            scopes=sorted(subject.roles),
            subject=subject.subject_user_id,
        )

    def subject_for(self, token: str) -> AuthenticatedSubject | None:
        return self._subjects.get(token)


def build_server(
    transport: McpTransport, verifier: HarnessTokenVerifier, sessions: SessionSubjects
) -> Any:
    """Frame the transport's operations as MCP tools.

    **Every tool routes through `McpTransport.call`** (FR-005). There is no protocol-layer path
    to any capability: this module holds no business logic, only the translation between a
    protocol frame and a governed call, and the refusal a client receives is always one the
    core authored (FR-006).
    """
    server = FastMCP(
        name="brieve",
        # WHAT A CLIENT IS TOLD, and it must not undersell the platform any more than it
        # oversells it. This text said "it does not put a model in the run loop — a dispatched
        # run still selects tools by a scripted sequence" until 021 noticed, which stopped
        # being true when 020 landed: a model now chooses each step's tool and the choice goes
        # through the same governed entry. A surface describing itself as less capable than it
        # is, to every client that connects, is a defect nobody inside the tree can see.
        # THE RECORDING CLAIM IS GENERATED, not written here. It read "every operation ... is
        # recorded in a tamper-evident trail" while nine of seventeen wrote nothing — the third
        # self-description in two days measured against the running service and found false, and
        # the first where the overclaim was about governance rather than capability. A test
        # comparing this text to a second hand-written copy would have passed every one of those
        # days, so the text is derived from the catalogue's dispositions instead.
        instructions=(
            "The governed agent runtime. "
            + governance_sentence()
            + " A dispatched run consults the model its definition binds, and every tool that "
            "model chooses passes the same governed entry a scripted one would — refused when "
            "it must be, recorded either way. `get_run_report` compiles what a run did from "
            "those records; it composes nothing, and states what it could not verify rather "
            "than smoothing it over."
        ),
        token_verifier=verifier,
        # THE SDK REFUSES A VERIFIER WITHOUT THESE, and the refusal is correct: a token
        # verifier with no declared issuer or resource would accept tokens minted for
        # somewhere else entirely. `issuer_url` is who we trust to have minted the caller's
        # credential; `resource_server_url` is what the token must have been minted FOR.
        #
        # Both come from the same environment the API reads, so the two surfaces cannot
        # drift into trusting different issuers — which would make ADR-0033's parity
        # guarantee a claim about two differently-trusting services.
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(_required("OIDC_ISSUER")),
            resource_server_url=AnyHttpUrl(
                os.environ.get("MCP_SURFACE_RESOURCE_URL")
                or f"http://127.0.0.1:{os.environ.get('MCP_SURFACE_PORT', '8083')}"
            ),
        ),
        host=os.environ.get("MCP_SURFACE_HOST", "0.0.0.0"),  # noqa: S104 — a served surface
        port=int(os.environ.get("MCP_SURFACE_PORT", "8083")),
    )

    # What each operation cannot do without, taken from the operation's own schema rather
    # than a second list here — a list would drift from the schema silently.
    required_fields = {
        op.tool_name: tuple(op.input_schema.get("required", ())) for op in operations()
    }

    def make_handler(tool_name: str) -> Any:
        # ANNOTATIONS THE SDK CAN ACTUALLY EVALUATE, which is why they are bare.
        #
        # `func_metadata` calls `get_type_hints` on this handler to build the tool's input
        # schema. Under `from __future__ import annotations` every annotation is a string,
        # so each name must be resolvable in the MODULE's globals — which is why the SDK
        # imports moved to the top of this file rather than staying inside `build_server`,
        # where they were locals and the server died with "Unable to evaluate type
        # annotations for callable 'start_run'".
        #
        # `Context` and `dict` are left unsubscripted because mypy's preferred
        # `Context[Any, Any]` and `dict[str, Any]` are what the SDK must evaluate, and the
        # generics resolve differently there. The `type: ignore` is narrow and deliberate:
        # this signature answers to the SDK first.
        async def handler(ctx: Context, arguments: dict | None = None) -> dict:  # type: ignore[type-arg]
            access = get_access_token()
            if access is None:
                # FR-012: refused BEFORE the governed operation is entered.
                return {"ok": False, "status": 401, "reason": "no acceptable credential"}

            subject = verifier.subject_for(access.token)
            if subject is None:
                return {"ok": False, "status": 401, "reason": "credential is no longer valid"}

            try:
                sessions.claim(ctx.session, subject.subject_user_id)
            except AuthenticationRefused as refused:
                return {"ok": False, "status": 403, "reason": refused.reason_code}

            # MALFORMED INPUT IS REFUSED AT THE BOUNDARY, NAMING WHAT WAS WRONG (FR-007).
            #
            # Without this the transport raises `KeyError('run_id')` and the SDK reports
            # "Error executing tool get_run: 'run_id'" — a bare key repr, indistinguishable
            # from a platform fault, telling the caller nothing about what to fix. Observed
            # against the running surface before this existed.
            supplied = arguments or {}
            missing = [
                field for field in required_fields.get(tool_name, ()) if field not in supplied
            ]
            if missing:
                return {
                    "ok": False,
                    "status": 400,
                    "reason": "malformed request",
                    "missing": missing,
                }

            return result_payload(transport.call(tool_name, supplied, subject=subject))

        handler.__name__ = tool_name
        return handler

    for operation in operations():
        server.add_tool(
            make_handler(operation.tool_name),
            name=operation.tool_name,
            description=operation.description,
        )

    return server


def main() -> int:  # pragma: no cover - process entrypoint
    """Start the served surface, or refuse to start and say why (FR-003)."""
    import sys

    try:
        sessions = SessionSubjects()
        verifier = HarnessTokenVerifier(build_verifier())
        transport = build_transport()
    except Exception as exc:  # noqa: BLE001 — refusing to start is the whole point
        print(f"the MCP surface will not start: {exc}", file=sys.stderr, flush=True)
        return 2

    server = build_server(transport, verifier, sessions)
    print(
        f"mcp surface ready — role={VAULT_ROLE} operations={len(operations())} db={_db_host()}",
        flush=True,
    )
    server.run(transport="streamable-http")
    return 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    raise SystemExit(main())
