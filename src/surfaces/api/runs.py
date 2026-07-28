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

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from core.correlation import validate_correlation_id
from core.errors import CorrelationRequiredError
from core.identity.types import AuthenticatedSubject
from core.run import RunState
from core.runs.index import DEFAULT_PAGE_SIZE, RunIndexError
from surfaces.api.dependencies import DispatcherDep, DurabilityDep, RunIndexDep, SubjectDep
from surfaces.dispatch.types import RunHandle


class StartRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_definition_id: str = Field(min_length=1)
    requested_tools: frozenset[str] = Field(default_factory=frozenset)
    correlation_id: str | None = None


class RunSummary(BaseModel):
    """One run, as a listing shows it.

    Deliberately smaller than a run's detail: enough to identify and choose, and nothing
    a caller would have to page past. `state` is joined from the durable record at read
    time — the index never carries it, because an index that did would be a second writer
    of a fact the checkpoint already owns.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    correlation_id: str
    agent_definition_id: str
    state: RunState | None
    created_at: datetime


class RunListResponse(BaseModel):
    """A page of runs, and how to ask for the next.

    **No total.** `cursor` is absent when there is nothing further, and a count of what was
    withheld is exactly the disclosure the tenant boundary exists to prevent — a response
    saying "3 of 7" has leaked the 7.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    runs: list[RunSummary]
    cursor: str | None = None


def list_runs_for(
    *,
    subject: AuthenticatedSubject,
    index: Any,
    durability: Any = None,
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> RunListResponse:
    """One page of this subject's runs, newest first.

    Transport-independent so MCP reaches this rather than reimplementing it — the same
    reason the evidence read and the collect were extracted. Tenant and subject come from
    the authenticated subject and are not parameters: a tenant argument would be a request
    to widen scope, which is not a thing this surface offers.
    """
    page = index.list_for(
        tenant_id=subject.tenant_id,
        subject_user_id=subject.subject_user_id,
        limit=limit,
        cursor=cursor,
    )
    return RunListResponse(
        runs=[
            RunSummary(
                run_id=e.run_id,
                correlation_id=e.correlation_id,
                agent_definition_id=e.agent_definition_id,
                state=_state_of(e.run_id, durability),
                created_at=e.created_at,
            )
            for e in page.entries
        ],
        cursor=page.cursor,
    )


def _state_of(run_id: str, durability: Any) -> RunState | None:
    """The run's state from the durable record, or ``None`` when it cannot be read.

    ``None`` means "not known from here" rather than any particular state, and the listing
    still returns the run — a person asking what they started should learn that it exists
    even when its current state is momentarily unavailable. Guessing a state would be
    worse than admitting the gap, and omitting the run would be worse still.
    """
    if durability is None:
        return None
    try:
        blob = durability.load(run_id)
    except Exception:  # noqa: BLE001 — a listing must not fail on one unreadable state
        return None
    if blob is None or blob.outcome is None:
        return None
    try:
        return RunState(blob.outcome.state)
    except ValueError:  # pragma: no cover - defensive against an unfamiliar state
        return None


def build_router() -> APIRouter:
    router = APIRouter(tags=["runs"])

    @router.get("/runs", response_model=RunListResponse)
    def list_runs(
        subject: SubjectDep,
        index: RunIndexDep,
        durability: DurabilityDep,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> RunListResponse:
        """The runs this subject started, newest first.

        Registered **before** `/runs/{run_id}` matters not at all to FastAPI's matcher
        here — the paths differ in shape — but the ordering reads the way the catalogue
        does, which is worth more than it costs.
        """
        try:
            return list_runs_for(
                subject=subject, index=index, durability=durability, limit=limit, cursor=cursor
            )
        except RunIndexError as exc:
            # A failed read is not an empty list. Telling a person they have started
            # nothing, when the truth is that we could not look, is the one answer here
            # that is actively misleading.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "run index unavailable"
            ) from exc

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
            # The roles this surface already resolved from the caller's verified claims.
            # The run resolves what they mean; passing them saves it from deriving identity
            # a second time, and two derivations would disagree exactly when it mattered.
            subject_roles=frozenset(subject.roles),
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
