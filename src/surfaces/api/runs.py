# SPDX-License-Identifier: Apache-2.0
"""Run lifecycle routes.

Start a run, ask what happened. That is the whole surface for runs, and the omission is
the design: **there is no route that invokes a tool.** A caller reaching a tool through the
API would be acting *beside* the agent rather than through it — a second path to the
governed core, which is the shape Principle II exists to prevent. Tools are reached by an
agent within a run.

Starting a run returns a handle rather than blocking (FR-007a). Runs are durable and long
by design, so an API that held a connection open for a run's duration would contradict the
feature that exists to let work outlive a process. It also keeps the surface honest about
what it is: a way to start and observe work, not a way to perform it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from core.correlation import validate_correlation_id
from core.errors import CorrelationRequiredError
from core.identity.types import AuthenticatedSubject
from surfaces.api.dependencies import DispatcherDep, SubjectDep
from surfaces.dispatch.types import RunHandle


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_definition_id: str = Field(min_length=1)
    requested_tools: frozenset[str] = Field(default_factory=frozenset)
    correlation_id: str | None = None


def build_router() -> APIRouter:
    router = APIRouter(tags=["runs"])

    @router.post("/runs", status_code=status.HTTP_202_ACCEPTED, response_model=RunHandle)
    def start_run(
        body: StartRunRequest,
        subject: SubjectDep,
        dispatcher: DispatcherDep,
    ) -> RunHandle:
        """Start a governed run and return its handle.

        202, not 200: the work has been accepted, not completed. A 200 here would imply
        the run finished, which is the misconception FR-007a exists to prevent.

        The subject is threaded through **unchanged and untranslated** — the authenticated
        identity becomes the subject of authority manufacture and of every audit record
        for this correlation ID. Anything that rewrote it here would make every downstream
        guarantee about a different person.
        """
        try:
            correlation_id = validate_correlation_id(body.correlation_id or _mint(subject))
        except CorrelationRequiredError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "correlation id required") from exc

        return dispatcher.dispatch(
            correlation_id=correlation_id,
            subject_user_id=subject.subject_user_id,
            tenant_id=subject.tenant_id,
            agent_definition_id=body.agent_definition_id,
            requested_tools=body.requested_tools,
        )

    @router.get("/runs/{run_id}", response_model=RunHandle)
    def get_run(
        run_id: str,
        subject: SubjectDep,
        dispatcher: DispatcherDep,
    ) -> RunHandle:
        """Return the run's current state through its handle."""
        handle = dispatcher.state_of(run_id)
        if handle is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such run")
        return handle

    return router


def _mint(subject: AuthenticatedSubject) -> str:
    import uuid

    return f"api-{subject.tenant_id}-{uuid.uuid4().hex[:16]}"


__all__ = ["StartRunRequest", "build_router"]
