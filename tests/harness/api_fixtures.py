# SPDX-License-Identifier: Apache-2.0
"""Assembly for surface tests.

The application is built with its collaborators supplied, so a test exercises the same
wiring production does rather than a parallel arrangement with different properties.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi import FastAPI

from core.audit.sink import InMemoryAuditSink
from core.authority.changes import BlockedPendingApprovalError, ChangeDisposition
from core.identity.claims import ClaimMapping
from core.registry.memory import ToolRegistry
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


DEFAULT_MAPPINGS = [
    ClaimMapping(claim_name="groups", claim_value="platform", role="operator"),
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
    dispatcher: InProcessDispatcher
    submitter: ScriptedSubmitter

    #: The subject the identity fabric knows about. Tests naming anyone else are testing
    #: refusal, which is a different assertion.
    subject_name: str = "alice"

    def subject(self) -> AuthenticatedSubject:
        """The same identity `bearer()` produces, as the core sees it.

        Built here rather than by verifying a token, because MCP's parity claim is about
        what happens *after* authentication — and constructing it directly keeps a token
        problem from presenting as a parity failure.
        """
        from core.identity.types import AuthenticatedSubject, SubjectKind

        return AuthenticatedSubject(
            subject_user_id=self.subject_name,
            tenant_id="tenant-test",
            roles=frozenset({"operator"}),
            subject_kind=SubjectKind.HUMAN,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )

    def bearer(self, **kwargs: object) -> dict[str, str]:
        kwargs.setdefault("subject", self.subject_name)
        kwargs.setdefault("claims", {"groups": ["platform"]})
        return {"Authorization": f"Bearer {self.idp.token(**kwargs)}"}  # type: ignore[arg-type]


def surface_under_test(
    registry: ToolRegistry | None = None,
    *,
    subject: str = "alice",
    submit_outcome: str = "pending",
) -> SurfaceUnderTest:
    idp = FakeOIDCProvider()
    audit = InMemoryAuditSink()
    dispatcher = InProcessDispatcher(
        identity_fabric=fake_identity_fabric(subject_user_id=subject),
        registry=registry or ToolRegistry(),
        audit_sink=audit,
    )
    verifier = TokenVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        mappings=DEFAULT_MAPPINGS,
        key_loader=lambda: {idp.key_id: idp.jwks_public_key()},
    )
    submitter = ScriptedSubmitter(submit_outcome)
    app = create_app(
        token_verifier=verifier,
        run_dispatcher=dispatcher,
        evidence_query=InMemoryEvidenceQuery(audit),
        audit_sink=audit,
        authority_submitter=submitter,
    )
    mcp = McpTransport(
        run_dispatcher=dispatcher,
        audit_sink=audit,
        evidence_query=InMemoryEvidenceQuery(audit),
        authority_submitter=submitter,
    )
    return SurfaceUnderTest(
        app=app,
        mcp=mcp,
        idp=idp,
        audit=audit,
        dispatcher=dispatcher,
        subject_name=subject,
        submitter=submitter,
    )
