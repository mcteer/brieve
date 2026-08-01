# SPDX-License-Identifier: Apache-2.0
"""Application assembly.

**Routes are registered here and nowhere else.** That is not tidiness — it is what makes
FR-007's assertion possible. The check that no route reaches a tool has to enumerate the
application's routes, and it can only do that if there is one place they all come from. A
router registered somewhere else would be invisible to the check and still served by the
app, which is precisely the "just this one endpoint" failure Principle II exists to catch.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from core.audit.query import EvidenceQuery
from core.audit.reconcile import ReconcileReport
from core.audit.sink import AuditSink
from core.runs.changes import ChangeRequestStore, InMemoryChangeRequestStore
from core.runs.index import InMemoryRunIndex, RunIndex
from core.threads.store import InMemoryThreadStore, ThreadStore
from surfaces.api import ask, evidence, mappings, reports, runs, threads
from surfaces.api import definitions as definitions_routes
from surfaces.api.verification import IdentityVerifier
from surfaces.dispatch.types import RunDispatcher

TITLE = "Enterprise Agent Harness API"


class _AbsentReconciler:
    """No destination configured: every stream reports ABSENT, and nothing raises.

    Not a null object smoothing over a misassembly. FR-009 makes "there is no second copy"
    a posture the platform must state plainly, and this is where an unconfigured estate
    states it.
    """

    def reconcile_stream(self, correlation_id: str) -> ReconcileReport:
        return ReconcileReport()


def create_app(
    *,
    token_verifier: IdentityVerifier,
    run_dispatcher: RunDispatcher,
    evidence_query: EvidenceQuery | None = None,
    audit_sink: AuditSink | None = None,
    authority_submitter: Any | None = None,
    run_index: RunIndex | None = None,
    durability: Any | None = None,
    change_requests: ChangeRequestStore | None = None,
    change_status: Any | None = None,
    definitions: Any | None = None,
    thread_store: ThreadStore | None = None,
    reconciler: Any | None = None,
    # 024. Absent by default, and the route is mounted regardless: a surface with no model
    # answers 503 rather than answering from the corpus alone, which FR-011a forbids.
    ask_provider: Any | None = None,
    ask_model: str = "unconfigured",
) -> FastAPI:
    """Build the application with its collaborators supplied rather than imported.

    Nothing is constructed from ambient configuration here. A surface that reached for its
    own database handle or built its own verifier would be a surface that could be stood
    up in a test with different security properties than it has in production.
    """
    app = FastAPI(title=TITLE, version="0.1.0")
    app.state.token_verifier = token_verifier
    app.state.run_dispatcher = run_dispatcher
    app.state.evidence_query = evidence_query
    app.state.audit_sink = audit_sink
    app.state.authority_submitter = authority_submitter
    # 011's collaborators. Constructed once here from what the environment supplies, for
    # the same reason the five above are: an operation that reached for its own database
    # handle could be stood up in a test with different security properties than it has in
    # production. Five operations improvising five wirings of one concern is how an app
    # builder rots, and each improvisation would be individually reasonable.
    #
    # In-memory defaults keep every existing caller — and every hermetic row — working
    # without a database, which is the same reason the run index is a seam at all.
    app.state.run_index = run_index if run_index is not None else InMemoryRunIndex()
    app.state.durability = durability
    app.state.change_requests = (
        change_requests if change_requests is not None else InMemoryChangeRequestStore()
    )
    app.state.change_status = change_status
    app.state.definitions = definitions
    # 012's collaborator, defaulted like `run_index` above and deliberately NOT like
    # `definitions` below. The thread router registers unconditionally, because a router
    # whose presence depends on assembly makes the operation snapshot assembly-dependent —
    # and a snapshot that says fifteen in one wiring and ten in another is the shape 011's
    # snapshot defect had. What varies by assembly is what the operations can *do*, never
    # whether they exist.
    app.state.thread_store = thread_store if thread_store is not None else InMemoryThreadStore()
    # 015's collaborator. `None` is an estate with no second copy, which the reconcile
    # operation reports as the ABSENT posture rather than as a failure — the route exists
    # either way, because whether tamper-evidence is in force is exactly the question it
    # answers, and a route that vanished when the answer was 'no' would answer it wrong.
    app.state.reconciler = reconciler if reconciler is not None else _AbsentReconciler()

    app.include_router(runs.build_router())
    # 024. Mounted unconditionally: the operation exists on this surface whether or not a model is
    # configured, and answers 503 when one is not. A route whose PRESENCE varied by configuration
    # would make the operation snapshot depend on assembly — which 011 already paid for once.
    app.include_router(ask.build_router(provider=ask_provider, model=ask_model))
    app.include_router(threads.build_router())
    if authority_submitter is not None:
        app.include_router(mappings.build_router())
    if evidence_query is not None:
        app.include_router(evidence.build_router())
        # 021's report, registered on the same condition as the evidence read it compiles
        # from. A route whose presence varied independently would make the operation snapshot
        # depend on assembly, which 011 already paid for once — and a report without the
        # governed read behind it would have to reach the query directly, which is the second
        # answer to "who may see this" that FR-007 forbids.
        app.include_router(reports.build_router())
    if definitions is not None:
        app.include_router(definitions_routes.build_router())
    return app


def registered_routes(app: FastAPI) -> list[dict[str, Any]]:
    """Every route this application serves, for the FR-007 and FR-012 checks.

    **Recurses into included routers.** ``app.routes`` does not hold a flat list: including
    a router leaves a wrapper object in it whose own ``.routes`` holds the real endpoints.
    A version of this that only looked one level deep returned the four framework defaults
    and none of ours — so the FR-007 check would have reported "no route reaches a tool"
    while never having seen a single route of this application. That is worse than no
    check, because it is believed.

    The guard test in the conformance row (`test_the_walk_actually_visits_routes`) exists
    for exactly that failure and is what caught it.
    """
    described: list[dict[str, Any]] = []

    def _walk(routes: Any) -> None:
        for route in routes:
            # Including a router leaves a wrapper in `app.routes` that exposes neither a
            # path nor a `.routes` list — the real endpoints hang off `original_router`.
            # Both attribute names are tried so this keeps working if the internal shape
            # changes again; what must never happen is silently finding nothing.
            nested = getattr(route, "routes", None)
            if nested is None:
                inner = getattr(route, "original_router", None)
                nested = getattr(inner, "routes", None) if inner is not None else None
            if nested:
                _walk(nested)
                continue
            path = getattr(route, "path", None)
            methods = getattr(route, "methods", None)
            if path is None or methods is None:
                continue
            described.append(
                {
                    "path": path,
                    "methods": sorted(m for m in methods if m not in {"HEAD", "OPTIONS"}),
                    "endpoint": getattr(route, "endpoint", None),
                    "name": getattr(route, "name", ""),
                }
            )

    _walk(app.routes)
    return described


__all__ = ["TITLE", "create_app", "registered_routes"]
