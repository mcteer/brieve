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
from core.audit.sink import AuditSink
from surfaces.api import runs
from surfaces.api.verification import TokenVerifier
from surfaces.dispatch.types import RunDispatcher

TITLE = "Enterprise Agent Harness API"


def create_app(
    *,
    token_verifier: TokenVerifier,
    run_dispatcher: RunDispatcher,
    evidence_query: EvidenceQuery | None = None,
    audit_sink: AuditSink | None = None,
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

    app.include_router(runs.build_router())
    return app


def registered_routes(app: FastAPI) -> list[dict[str, Any]]:
    """Every route this application serves, for the FR-007 and FR-012 checks."""
    described: list[dict[str, Any]] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        endpoint = getattr(route, "endpoint", None)
        if path is None or methods is None:
            continue
        described.append(
            {
                "path": path,
                "methods": sorted(m for m in methods if m not in {"HEAD", "OPTIONS"}),
                "endpoint": endpoint,
                "name": getattr(route, "name", ""),
            }
        )
    return described


__all__ = ["TITLE", "create_app", "registered_routes"]
