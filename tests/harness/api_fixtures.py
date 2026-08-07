# SPDX-License-Identifier: Apache-2.0
"""Assembly for surface tests.

The application is built with its collaborators supplied, so a test exercises the same
wiring production does rather than a parallel arrangement with different properties.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from core.answering.conversations.store import MemoryConversationStore
from core.audit.sink import InMemoryAuditSink
from core.authority.ask_binding import AskAuthority
from core.authority.changes import BlockedPendingApprovalError, ChangeDisposition
from core.durability.memory import InMemoryDurabilityProvider
from core.identity.claims import ClaimMapping
from core.registry.memory import ToolRegistry
from core.runs.changes import InMemoryChangeRequestStore
from core.runs.index import InMemoryRunIndex
from core.threads.store import InMemoryThreadStore
from surfaces.api.app import create_app
from surfaces.api.authority_submit import AuthorityChangeRefused, AuthoritySubmitUnavailable
from surfaces.api.verification import TokenVerifier
from surfaces.dispatch.inprocess import InProcessDispatcher
from surfaces.mcp.transport import McpTransport
from tests.harness.fake_identity_fabric import fake_identity_fabric
from tests.harness.fake_oidc_provider import AUDIENCE, ISSUER, FakeOIDCProvider
from tests.harness.memory_evidence import InMemoryEvidenceQuery

if TYPE_CHECKING:
    from core.identity.types import AuthenticatedSubject


class ScriptedSubmitter:
    """Returns a chosen disposition, for testing how the SURFACE reports one.

    Not a stand-in for the gate. Whether Vault actually queues a write is proven in
    `tests/conformance/api/test_claim_mapping_gated.py` against a real Control Group —
    a fake that always says "pending" would prove the caller can handle pending and
    nothing whatever about gating.
    """

    def __init__(self, outcome: str = "pending") -> None:
        self.outcome = outcome
        self.submitted: list[ClaimMapping] = []

    def submit(self, *, requester: str, mapping: ClaimMapping) -> ChangeDisposition:
        self.submitted.append(mapping)
        if self.outcome == "pending":
            raise BlockedPendingApprovalError(
                f"{mapping.role} requested by {requester}", accessor="acc-test"
            )
        if self.outcome == "denied":
            raise AuthorityChangeRefused("denied by policy")
        if self.outcome == "unavailable":
            raise AuthoritySubmitUnavailable("vault unreachable")
        return ChangeDisposition.APPROVED


#: The model the fixture authority binds for RELEVANCE. **Deliberately not `model`** (043): the
#: gate exists to judge an answer, and a judge that is the same model as the generator is
#: grading its own work. The fixtures encode the separation so a row cannot pass by accident
#: with a self-judging binding.
#:
#: **A fixture identifier, not a vendor one, and that is the second fix.** It was
#: `anthropic/claude-sonnet@5`, which collided the moment a row passed `model=` that same
#: vendor string — and ADR-0067's runtime check then refused the row for a reason the row was
#: not about. A name no answering cell will ever carry cannot collide by accident, which is
#: what a shared fixture constant is for.
FIXTURE_RELEVANCE_MODEL = "fixture/relevance-judge@1"


def _default_relevance_judges() -> object:
    """A judge that affirms, so rows about other properties keep asserting those properties.

    Scaffolding, and the contract says so: the gate's REFUSING branches are driven by rows that
    construct their own verdicts, and its presence on the production path is proven by R8
    against `ask.py`. This default makes neither of those weaker.
    """
    from tests.harness.fixture_relevance import FixtureRelevanceJudge

    return lambda cell: FixtureRelevanceJudge()


DEFAULT_MAPPINGS = [
    ClaimMapping(claim_name="groups", claim_value="platform", role="operator"),
    # 044. A SEPARATE claim value, so a row must ask for the admin role to get it — the
    # default subject is an operator and stays one. A mapping that granted both from one
    # claim would make every existing row an administrator and quietly turn C13's "a
    # non-admin is refused" into a row that could not fail.
    ClaimMapping(claim_name="groups", claim_value="platform-admin", role="admin"),
]


@dataclass
class SurfaceUnderTest:
    app: FastAPI
    #: The MCP transport over the SAME collaborators the app resolves. Sharing them is
    #: what makes the parity row a comparison of one core through two front doors, rather
    #: than of two implementations that happen to agree.
    mcp: McpTransport
    idp: FakeOIDCProvider
    audit: InMemoryAuditSink
    #: ONE evidence query, shared by both surfaces. They previously built one each — same
    #: behaviour, since both wrap this sink, but two objects a parity row could not prove were
    #: the same collaborator. 025's estate path reads through this, so sharing it is what makes
    #: "both surfaces read the same records" a fact rather than an inference.
    evidence: InMemoryEvidenceQuery
    dispatcher: InProcessDispatcher
    #: Widened for 044: a row may supply its own submitter, and the console's speaks
    #: `submit_change` rather than `ScriptedSubmitter`'s `submit`. Rows that inspect the
    #: scripted one still get it by default.
    submitter: Any
    thread_store: InMemoryThreadStore

    #: The fake identity fabric the dispatcher resolves through. Exposed so a row can grant a
    #: SECOND subject the same scope — the accessibility lane runs each theme as its own person
    #: so they do not share one rate window, and it has to tell the fabric about them.
    identity_fabric: Any = None

    #: The subject the identity fabric knows about. Tests naming anyone else are testing
    #: refusal, which is a different assertion.
    subject_name: str = "alice"

    def subject(self, name: str | None = None) -> AuthenticatedSubject:
        """The same identity `bearer()` produces, as the core sees it.

        Built here rather than by verifying a token, because MCP's parity claim is about
        what happens *after* authentication — and constructing it directly keeps a token
        problem from presenting as a parity failure.

        `name` names a DIFFERENT person in the same tenant, mirroring `bearer(subject=…)`.
        Ownership rows need two people, and a parity row needs both transports to disagree
        with the same second person rather than with two different ones.
        """
        from core.identity.types import AuthenticatedSubject, SubjectKind

        return AuthenticatedSubject(
            subject_user_id=name or self.subject_name,
            tenant_id="tenant-test",
            roles=frozenset({"operator"}),
            subject_kind=SubjectKind.HUMAN,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

    def bearer(self, **kwargs: object) -> dict[str, str]:
        kwargs.setdefault("subject", self.subject_name)
        kwargs.setdefault("claims", {"groups": ["platform"]})
        return {"Authorization": f"Bearer {self.idp.token(**kwargs)}"}  # type: ignore[arg-type]


class FixedCredential:
    """A credential source over a mutable backing value, for rows that need one (027).

    **Counts its reads**, because "two asks are two fetches" is a property no single-ask row can
    see: a surface that fetched once and reused the key across asks would pass every other row
    here and hold a credential for the life of the process — the standing credential the feature
    exists to remove, one layer above the reader that refuses to cache.

    **Revocable in place**: `revoke()` empties the backing store, so the *next* ask refuses without
    anything being reconstructed. That is what revocation without a restart means (SC-003).
    """

    def __init__(self, *, secret: str = "brokered-for-this-task", version: int = 1) -> None:
        self.secret: str | None = secret
        self.version = version
        self.reads: list[str] = []

    def revoke(self) -> None:
        self.secret = None

    def rotate(self, secret: str) -> None:
        self.secret = secret
        self.version += 1

    def obtain(self, vendor: str) -> Any:
        from core.authority.errors import ResolutionRefused
        from core.authority.model_credential import ModelCredential

        self.reads.append(vendor)
        if self.secret is None:
            raise ResolutionRefused(
                f"no model credential is stored for {vendor!r}",
                reason_code="credential_unavailable",
            )
        return ModelCredential(
            secret=self.secret,
            reference=f"vault:model-credentials/{vendor}@v{self.version}",
        )


def available_credential(**kwargs: Any) -> FixedCredential:
    """The explicit opt-in a row makes when it expects an ask to reach a model."""
    return FixedCredential(**kwargs)


def _providers_of(provider: object | None) -> Any:
    """Wrap a built provider as the per-ask factory both surfaces now take (027).

    Production builds a provider per ask from material brokered for that ask; a row that already
    has a fake provider does not need to model the construction, only the seam. The wrapper
    ignores the secret and returns the same instance, which is exactly what a row asserting
    *routing* wants — and exactly why the credential rows use a counting source instead of
    counting provider constructions.
    """
    if provider is None:
        return None
    return lambda source, secret: provider


def surface_under_test(
    registry: ToolRegistry | None = None,
    *,
    subject: str = "alice",
    submit_outcome: str = "pending",
    reconciler: object | None = None,
    # 024's collaborator, shared like the seven below. `None` leaves both surfaces with no
    # model, which is what an unconfigured deployment actually has — the parity rows then
    # compare two surfaces giving that same 503.
    ask_provider: object | None = None,
    ask_model: str = "unconfigured",
    # 027's collaborator, shared like the nine before it. **`None` means every ask refuses
    # `credential_unavailable`**, and that default is deliberate for the same reason
    # `ask_authority`'s is: a fixture that auto-supplied a credential would rebuild "a provider is
    # configured, therefore it may be called" one level below where 026 broke it. Rows that answer
    # call `available_credential()` explicitly.
    credential_source: object | None = None,
    # 026's collaborator, shared like the eight before it. **`None` means every ask refuses
    # `unbound`**, and that default is deliberate: a fixture that auto-qualified whatever
    # provider was injected would rebuild "configured = qualified" inside the harness — the
    # exact equation this feature exists to break. Rows that answer call
    # `qualified_ask_authority()` explicitly.
    ask_authority: object | None = None,
    # 044's console reader. `None` leaves the surface with no console at all — which is what
    # a deployment that has not configured one has, and keeps every pre-044 row's operation
    # snapshot unchanged. Rows that read configuration supply one.
    console_config: object | None = None,
    #: An explicit submitter, for rows about what the fabric decided. `None` keeps
    #: `ScriptedSubmitter`, which is what the mappings rows have always driven.
    authority_submitter: object | None = None,
    # 043's collaborator, and the ONE that defaults to present rather than absent — which
    # breaks the pattern of the eleven before it, so here is why.
    #
    # Those defaults are absent because each grants something: a credential, a qualification, a
    # provider. A harness that supplied one by default would rebuild "configured = permitted"
    # inside the tests, which is the equation 026 exists to break.
    #
    # A relevance judge grants NOTHING. It only narrows what ships. Defaulting it absent would
    # make forty-six rows about routing, records and parity fail for a reason none of them is
    # about — and the useful assertion is not "this row remembered to pass a judge" but "the
    # PRODUCTION surface constructs one", which is R8's job and is driven against `ask.py`
    # itself. The guard belongs there, not in every row's setup.
    relevance_judges: object | None = None,
    relevance_model: str = FIXTURE_RELEVANCE_MODEL,
    # 035's collaborator, shared like the ten before it. A REAL memory store by default rather
    # than `None`, because unlike a credential or a qualification a conversation store grants
    # nothing — it groups a person's own questions. Defaulting it absent would leave every
    # parity row comparing two surfaces that both forget, which is not the behaviour either
    # deployment has.
    ask_conversations: object | None = None,
) -> SurfaceUnderTest:
    idp = FakeOIDCProvider()
    audit = InMemoryAuditSink()
    # 011's collaborators, shared by BOTH surfaces. Sharing is the point rather than a
    # convenience: parity compares what the two surfaces do, and two surfaces reading
    # different stores would diverge in ways no catalogue comparison could see.
    index = InMemoryRunIndex()
    durability = InMemoryDurabilityProvider()
    changes = InMemoryChangeRequestStore()
    # 012's collaborator, shared for the same reason as the four above: two surfaces
    # reading different thread stores would diverge in ways no catalogue comparison sees.
    thread_store = InMemoryThreadStore()
    evidence = InMemoryEvidenceQuery(audit)
    definitions_fabric = fake_definitions_fabric(subject)
    #: Named rather than inlined so a row can reach it — the accessibility lane runs each
    #: theme as its own subject (a shared rate window makes the second theme's rows fail far
    #: from the cause) and has to grant those subjects a scope. Exposed on the returned
    #: object below.
    identity_fabric = fake_identity_fabric(subject_user_id=subject)
    # ONE conversation store for BOTH surfaces (035). Two `MemoryConversationStore()`
    # expressions would build two, and the parity rows would compare a surface that
    # remembered against one that did not — which is precisely the asymmetry this fixture
    # exists to prevent, and which it caught on the first run.
    conversation_store = (
        ask_conversations if ask_conversations is not None else MemoryConversationStore()
    )
    dispatcher = InProcessDispatcher(
        identity_fabric=identity_fabric,
        registry=registry or ToolRegistry(),
        audit_sink=audit,
        run_index=index,
    )
    verifier = TokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        mappings=DEFAULT_MAPPINGS,
        key_loader=lambda: {idp.key_id: idp.jwks_public_key()},
    )
    # 044: a row may supply its own, because the console needs `submit_change`'s three
    # outcomes as data and `ScriptedSubmitter` speaks the older `submit` shape. Defaulted, so
    # every pre-044 row keeps the scripted one it was written against.
    submitter: Any = authority_submitter or ScriptedSubmitter(submit_outcome)
    app = create_app(
        console_config=console_config,
        token_verifier=verifier,
        run_dispatcher=dispatcher,
        evidence_query=evidence,
        audit_sink=audit,
        authority_submitter=submitter,
        run_index=index,
        durability=durability,
        change_requests=changes,
        change_status=ScriptedChangeStatus(),
        definitions=definitions_fabric,
        thread_store=thread_store,
        # 015's collaborator, shared like the six above. `None` leaves both surfaces on
        # the ABSENT reconciler, which is what an estate with no second copy actually
        # has — the parity rows then compare two surfaces giving that same answer.
        reconciler=reconciler,
        ask_conversations_store=conversation_store,
        ask_providers=_providers_of(ask_provider),
        ask_model=ask_model,
        ask_authority=ask_authority,
        credential_source=credential_source,
        relevance_judges=(
            relevance_judges if relevance_judges is not None else _default_relevance_judges()
        ),
        relevance_model=relevance_model,
    )
    mcp = McpTransport(
        run_dispatcher=dispatcher,
        audit_sink=audit,
        evidence_query=evidence,
        authority_submitter=submitter,
        run_index=index,
        durability=durability,
        change_requests=changes,
        change_status=ScriptedChangeStatus(),
        definitions=definitions_fabric,
        thread_store=thread_store,
        reconciler=reconciler,
        ask_conversations=conversation_store,
        ask_providers=_providers_of(ask_provider),
        ask_model=ask_model,
        ask_authority=ask_authority,
        credential_source=credential_source,
        relevance_judges=(
            relevance_judges if relevance_judges is not None else _default_relevance_judges()
        ),
        relevance_model=relevance_model,
    )
    return SurfaceUnderTest(
        app=app,
        mcp=mcp,
        idp=idp,
        audit=audit,
        evidence=evidence,
        dispatcher=dispatcher,
        subject_name=subject,
        submitter=submitter,
        thread_store=thread_store,
        identity_fabric=identity_fabric,
    )


class ScriptedChangeStatus:
    """A change-status source that answers without a trust fabric."""

    def __init__(self, disposition: str = "pending") -> None:
        self.disposition = disposition

    def status_of(self, accessor: str) -> Any:
        from core.runs.changes import CollectedDisposition

        return CollectedDisposition(accessor=accessor, disposition=self.disposition, approvals=0)


def fake_definitions_fabric(subject: str) -> Any:
    """A fabric that knows two definitions and one subject's scope.

    Enough for the parity rows to compare verdicts on the enumeration operations, which is
    what they are for — the disclosure RULES have their own rows in
    `tests/component/test_list_definitions.py`.
    """
    from core.authority.types import AuthorityScope

    class _Fabric:
        def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
            return AuthorityScope(tool_names=frozenset({"echo"}))

        def list_definitions(self) -> list[str]:
            return ["planner", "applier"]

        def resolve_ceiling(self, agent_definition_id: str) -> AuthorityScope:
            allowed = {"planner": {"echo"}, "applier": {"apply"}}
            return AuthorityScope(tool_names=frozenset(allowed.get(agent_definition_id, set())))

    return _Fabric()


def qualified_ask_authority(
    *,
    model: str = "anthropic/claude-opus@5",
    packs: tuple[str, str] = ("vault", "terraform"),
    relevance_model: str = FIXTURE_RELEVANCE_MODEL,
) -> AskAuthority:
    """An in-memory binding + matrix qualifying `model` for both sources.

    **Called explicitly by rows that answer**, never applied by default. The default is refusal,
    because a harness that qualified whatever provider a test injected would make every refusal
    row test an override rather than the behaviour — and "a configured provider is a
    qualification" is precisely the equation 026 exists to break.
    """
    guidance, estate = packs
    return AskAuthority(
        read_binding=lambda: {
            "schema_version": 1,
            "guidance_cell": f"{guidance}:{model}:ask",
            "estate_cell": f"{estate}:{model}:ask",
            "relevance_cell": f"{guidance}:{relevance_model}:judge",
        },
        read_matrix=lambda: {
            "schema_version": 1,
            "cells": [
                {
                    "pack": pack,
                    "model": model,
                    "role": "ask",
                    "qualified_by": "fixture",
                    "judge": "seed",
                }
                for pack in (guidance, estate)
            ]
            + [
                {
                    "pack": guidance,
                    "model": relevance_model,
                    "role": "judge",
                    "qualified_by": "fixture",
                    "judge": "seed",
                }
            ],
        },
    )
