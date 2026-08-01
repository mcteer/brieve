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

from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink
from core.correlation import validate_correlation_id
from core.durability.types import CheckpointBlob, RunOutcome
from core.errors import CorrelationRequiredError
from core.identity.types import AuthenticatedSubject
from core.run import RunState
from core.runs.index import DEFAULT_PAGE_SIZE, RunIndexError
from core.runs.refusals import OperationRefused
from surfaces.api.dependencies import (
    AuditDep,
    DispatcherDep,
    DurabilityDep,
    RunIndexDep,
    SubjectDep,
)
from surfaces.api.record_access import (
    RecordAccessUnavailable,
    record_access,
    record_access_refused,
)
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
    audit: AuditSink,
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
    # Recorded before the page is returned, never after: a listing that answered first and
    # recorded second would produce an unrecorded answer on any failure between the two, and
    # an empty page still discloses that the caller asked (FR-007b).
    record_access(
        audit=audit,
        subject=subject,
        operation="list_runs",
        result_count=len(page.entries),
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


#: Where a run's output lives on its terminal checkpoint.
#:
#: A reserved key in the existing payload rather than a new column or a new table: the
#: terminal checkpoint is the one place a run's ending is already recorded, and two records
#: of one ending will eventually disagree about which is true.
RESULT_KEY = "__run_result__"

#: How much of a result the operation will return.
#:
#: Past this it refuses rather than truncating, because the spec is explicit that a partial
#: result presented as complete is worse than a refusal — someone acts on it. The bound is
#: generous enough that no ordinary result meets it and small enough that a runaway one
#: cannot be handed to a browser.
MAX_RESULT_BYTES = 256 * 1024


class RunResultResponse(BaseModel):
    """What a run produced, or why there is nothing to show.

    Three dispositions, and a single empty response would conflate all of them (FR-007):
    a run still working, a run that finished with something, and a run that ended without
    one. Only the second has a `result`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    disposition: str
    result: Any | None = None
    stop_reason: str | None = None


def run_result_for(
    *,
    run_id: str,
    subject: AuthenticatedSubject,
    index: Any,
    durability: Any,
    audit: AuditSink,
) -> RunResultResponse:
    """A run's output, without the caller reading a single audit entry.

    The index supplies the tenant check — a run in another tenant is answered exactly as a
    run that does not exist — and the checkpoint supplies the outcome. **Never the raw
    payload**: checkpoint contents are resume state, and returning them wholesale would
    make their shape a compatibility surface, which is the argument against reconstructing
    results from the audit trail, one layer down.
    """
    # THE SHARPEST CASE IN 022. 021 kept the run's result out of `RunReport` so a tenant-scoped
    # report could not route around the subject-only restriction below — and this operation, the
    # one that actually serves the result, recorded nothing about who read it. The artifact that
    # could not leak it was audited; the one that served it was not.
    entry = index.get(run_id=run_id, tenant_id=subject.tenant_id)
    if entry is None:
        record_access_refused(
            audit=audit,
            subject=subject,
            operation="get_run_result",
            reason_code="no_such_record",
            target_id=run_id,
        )
        raise OperationRefused("no such run", reason_code="no_such_record")
    if entry.subject_user_id != subject.subject_user_id:
        record_access_refused(
            audit=audit,
            subject=subject,
            operation="get_run_result",
            reason_code="not_permitted",
            target_correlation_id=entry.correlation_id,
            target_id=run_id,
        )
        raise OperationRefused("this run belongs to someone else", reason_code="not_permitted")

    record_access(
        audit=audit,
        subject=subject,
        operation="get_run_result",
        target_correlation_id=entry.correlation_id,
        target_id=run_id,
        result_count=1,
    )
    blob = durability.load(run_id) if durability is not None else None
    if blob is None or blob.outcome is None:
        return RunResultResponse(run_id=run_id, disposition="running")

    payload = blob.payload or {}
    if RESULT_KEY not in payload:
        # Terminal with nothing to show — stopped, refused, or simply produced nothing.
        # The reason is what makes this actionable: a run that failed is not a run that
        # returned nothing, and an empty response would say the second about the first.
        return RunResultResponse(
            run_id=run_id,
            disposition="ended_without_result",
            stop_reason=blob.outcome.stop_reason,
        )

    result = payload[RESULT_KEY]
    if _too_large(result):
        raise OperationRefused("result too large to return", reason_code="not_permitted")

    return RunResultResponse(run_id=run_id, disposition="complete", result=result)


def _too_large(result: Any) -> bool:
    """Whether returning this would exceed the bound.

    Measured on the serialised form, because that is what a caller receives — a structure
    that is small in objects and enormous in bytes is exactly the case a naive length check
    would wave through.
    """
    import json

    try:
        return len(json.dumps(result).encode()) > MAX_RESULT_BYTES
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return True


class StopRunResponse(BaseModel):
    """The run's state after a stop. Terminal, and never a promise to stop later."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    state: RunState
    stop_reason: str | None = None
    already_terminal: bool = False


def stop_run_for(
    *,
    run_id: str,
    subject: AuthenticatedSubject,
    index: Any,
    durability: Any,
    audit: AuditSink,
) -> StopRunResponse:
    """Withdraw a run this subject started.

    **Withdrawal, not pausing**, and the distinction is what keeps this compatible with
    ADR-0049. That decision forbids a run *waiting* on a human; it says nothing about a
    person ending their own request. The state written here is terminal — unresumable by
    `is_terminal()`, invisible to the sweeper by `_is_suspended` — so nothing waits, and
    no recovering dependency can bring it back. A stop a dependency could undo would be a
    pause wearing another name.

    The caller returns immediately. The running allocation notices at its next step
    boundary and ends after bracketing the step in flight, which is why a stop is not
    instant: buying promptness by killing the allocation would leave an open intent on a
    run that is terminal and will therefore never resume to re-observe it — permanent,
    which is the one outcome 005's bracketing exists to prevent.
    """
    entry = index.get(run_id=run_id, tenant_id=subject.tenant_id)
    if entry is None:
        record_access_refused(
            audit=audit,
            subject=subject,
            operation="stop_run",
            reason_code="no_such_record",
            target_id=run_id,
        )
        raise OperationRefused("no such run", reason_code="no_such_record")
    if entry.subject_user_id != subject.subject_user_id:
        # Only the person who gave consent may withdraw it.
        record_access_refused(
            audit=audit,
            subject=subject,
            operation="stop_run",
            reason_code="not_permitted",
            target_correlation_id=entry.correlation_id,
            target_id=run_id,
        )
        raise OperationRefused("this run belongs to someone else", reason_code="not_permitted")

    blob = durability.load(run_id)
    if blob is not None and blob.outcome is not None:
        # Asking twice is not an error (FR-011). The terminal-once guard means a second
        # stop could not change this even if it tried, so reporting the existing state is
        # both the honest answer and the only possible one.
        return StopRunResponse(
            run_id=run_id,
            state=RunState(blob.outcome.state),
            stop_reason=blob.outcome.stop_reason,
            already_terminal=True,
        )

    reason = f"stopped_by:{subject.subject_user_id}"
    # WRITTEN BEFORE THE TERMINAL SAVE, and to the RUN'S OWN stream rather than the reader
    # stream — this is an act performed on the run, not a read of it, so it belongs where
    # `THREAD_DELETED` belongs. A stop that cannot be recorded does not happen: silently
    # terminating a run with no record is strictly worse than refusing, because the caller
    # believes it worked.
    #
    # Before 022 this wrote nothing at all. The only attribution was `written_by` on the blob
    # below — not hash-chained, and not reachable through the governed evidence path. A person
    # withdrawing consent and ending a run left nothing a reviewer could find.
    try:
        audit.append_event(
            correlation_id=entry.correlation_id,
            tenant_id=subject.tenant_id,
            event_type=AuditEventType.RUN_STOPPED,
            payload={
                "subject_user_id": subject.subject_user_id,
                "run_id": run_id,
                "stop_reason": reason,
            },
        )
    except Exception as exc:  # noqa: BLE001 — an unrecordable stop must not stop the run
        raise RecordAccessUnavailable(
            "the stop could not be recorded; the run is still running"
        ) from exc

    durability.save(
        CheckpointBlob(
            blob_id=run_id,
            payload=(blob.payload if blob is not None else {}),
            correlation_id=(blob.correlation_id if blob is not None else entry.correlation_id),
            grant_id=(blob.grant_id if blob is not None else ""),
            step_index=(blob.step_index if blob is not None else 0),
            written_by=f"stop:{subject.subject_user_id}",
            outcome=RunOutcome(state=RunState.STOPPED.value, stop_reason=reason),
        )
    )
    return StopRunResponse(run_id=run_id, state=RunState.STOPPED, stop_reason=reason)


def run_state_for(
    *,
    run_id: str,
    subject: AuthenticatedSubject,
    dispatcher: Any,
    audit: AuditSink,
) -> RunHandle | None:
    """A run's current state, recorded as read.

    **Extracted by 022 so there is one place to record.** Both transports previously called
    `dispatcher.state_of` directly, which meant recording would have had to be written twice
    and kept in agreement by inspection — the property ADR-0033 exists to make structural
    rather than careful.

    Authorization is unchanged (FR-015): this reads the dispatcher exactly as both callers did.
    """
    handle = dispatcher.state_of(run_id)
    if handle is None:
        record_access_refused(
            audit=audit,
            subject=subject,
            operation="get_run",
            reason_code="no_such_record",
            target_id=run_id,
        )
        return None
    record_access(
        audit=audit,
        subject=subject,
        operation="get_run",
        target_correlation_id=getattr(handle, "correlation_id", None),
        target_id=run_id,
        result_count=1,
    )
    return handle


def build_router() -> APIRouter:
    router = APIRouter(tags=["runs"])

    @router.post("/runs/{run_id}/stop", response_model=StopRunResponse)
    def stop_run(
        run_id: str,
        subject: SubjectDep,
        index: RunIndexDep,
        durability: DurabilityDep,
        audit: AuditDep,
    ) -> StopRunResponse:
        """End a run you started."""
        try:
            return stop_run_for(
                run_id=run_id,
                subject=subject,
                index=index,
                durability=durability,
                audit=audit,
            )
        except RecordAccessUnavailable as unrecordable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unrecordable)
            ) from unrecordable
        except OperationRefused as refused:
            code = (
                status.HTTP_403_FORBIDDEN
                if refused.is_visible_to_caller
                else status.HTTP_404_NOT_FOUND
            )
            raise HTTPException(code, str(refused)) from refused

    @router.get("/runs/{run_id}/result", response_model=RunResultResponse)
    def get_run_result(
        run_id: str,
        subject: SubjectDep,
        index: RunIndexDep,
        durability: DurabilityDep,
        audit: AuditDep,
    ) -> RunResultResponse:
        """What this run produced."""
        try:
            return run_result_for(
                run_id=run_id,
                subject=subject,
                index=index,
                durability=durability,
                audit=audit,
            )
        except RecordAccessUnavailable as unrecordable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unrecordable)
            ) from unrecordable
        except OperationRefused as refused:
            code = (
                status.HTTP_403_FORBIDDEN
                if refused.is_visible_to_caller
                else status.HTTP_404_NOT_FOUND
            )
            raise HTTPException(code, str(refused)) from refused

    @router.get("/runs", response_model=RunListResponse)
    def list_runs(
        subject: SubjectDep,
        index: RunIndexDep,
        durability: DurabilityDep,
        audit: AuditDep,
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
                subject=subject,
                index=index,
                durability=durability,
                audit=audit,
                limit=limit,
                cursor=cursor,
            )
        except RecordAccessUnavailable as unrecordable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unrecordable)
            ) from unrecordable
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
        audit: AuditDep,
    ) -> RunHandle:
        """Return the run's current state through its handle."""
        try:
            handle = run_state_for(
                run_id=run_id, subject=subject, dispatcher=dispatcher, audit=audit
            )
        except RecordAccessUnavailable as unrecordable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unrecordable)
            ) from unrecordable
        if handle is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such run")
        return handle

    return router


def _mint(subject: AuthenticatedSubject) -> str:
    import uuid

    return f"api-{subject.tenant_id}-{uuid.uuid4().hex[:16]}"


__all__ = ["StartRunRequest", "build_router"]
