# SPDX-License-Identifier: Apache-2.0
"""Thread routes — the conversational shape over the same authorization core.

**These routes own transport, not decisions.** Sending a turn is `accept_turn` in
`core.threads.turns`, called with what this surface established: who is asking, and
whether they may start the definition they chose. That split is what makes verdict parity
structural — MCP calls these same handlers, so the two transports cannot answer
differently without one of them failing to compile.

**No route reaches a tool**, exactly as 008 and 011 left it. A thread starts runs; runs
reach tools. A caller reaching a tool through this surface would be acting beside the
agent rather than through it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from core.identity.types import AuthenticatedSubject
from core.runs.refusals import OperationRefused
from core.threads.records import (
    ThreadRecord,
    TurnDisposition,
    TurnRecord,
)
from core.threads.store import (
    DEFAULT_PAGE_SIZE,
    ThreadStoreError,
    new_thread_id,
)
from core.threads.turns import accept_turn
from surfaces.api.definitions import definition_views
from surfaces.api.dependencies import (
    AuditDep,
    DefinitionsDep,
    DispatcherDep,
    DurabilityDep,
    SubjectDep,
    ThreadStoreDep,
)


class ThreadView(BaseModel):
    """A thread as a listing shows it. No turn content — that is `get_thread`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    thread_id: str
    correlation_id: str
    title: str | None
    created_at: datetime


class ThreadListResponse(BaseModel):
    """A page of threads, and how to ask for the next.

    **No total**, for the reason 011 recorded: a count of what was withheld is exactly the
    disclosure the tenant boundary exists to prevent.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    threads: list[ThreadView]
    cursor: str | None = None


class TurnView(BaseModel):
    """One exchange, as any transport reports it.

    `disposition` is the answer, and a decline is a *200 with a disposition* rather than an
    error: the platform considered the message and answered. Only a refusal — this person
    may not, or the platform will not accept the message at all — is an error status.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: str
    seq: int
    message: str
    disposition: TurnDisposition
    created_at: datetime
    reason: str | None = None
    run_id: str | None = None
    agent_definition_id: str | None = None
    context_run_ids: list[str] = Field(default_factory=list)
    context_dropped: list[str] = Field(default_factory=list)


class ThreadDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    thread: ThreadView
    turns: list[TurnView]


class SendTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: **Deliberately not bounded here.** The size bound lives in core, alone.
    #:
    #: A `max_length` on this field looked like defence in depth and was the opposite: it
    #: rejects the request inside request validation, *before* `accept_turn` runs — so the
    #: `TURN_REFUSED` event that records an oversized attempt is never written, and the one
    #: kind of message someone might send maliciously becomes the one kind that leaves no
    #: trace. Found by the parity row, which caught the two transports answering
    #: differently, and the divergence was the smaller half of the problem.
    message: str = Field(min_length=1)
    agent_definition_id: str | None = None
    requested_tools: frozenset[str] = Field(default_factory=frozenset)


def _thread_view(record: ThreadRecord) -> ThreadView:
    return ThreadView(
        thread_id=record.thread_id,
        correlation_id=record.correlation_id,
        title=record.title,
        created_at=record.created_at,
    )


def _turn_view(record: TurnRecord) -> TurnView:
    return TurnView(
        turn_id=record.turn_id,
        seq=record.seq,
        message=record.message,
        disposition=record.disposition,
        created_at=record.created_at,
        reason=record.reason,
        run_id=record.run_id,
        agent_definition_id=record.agent_definition_id,
        context_run_ids=list(record.context_run_ids),
        context_dropped=list(record.context_dropped),
    )


def _refuse(refused: OperationRefused) -> HTTPException:
    """One refusal shape for every thread operation.

    `is_visible_to_caller` decides between 403 and 404, so "absent" and "another tenant's"
    are indistinguishable on the wire while the trail keeps the distinction. Written once
    here rather than at five call sites, because five copies of a security-relevant
    branch is five chances to get one wrong.
    """
    code = status.HTTP_403_FORBIDDEN if refused.is_visible_to_caller else status.HTTP_404_NOT_FOUND
    return HTTPException(code, str(refused))


def create_thread_for(*, subject: AuthenticatedSubject, store: Any) -> ThreadRecord:
    """Create an empty thread, counting the creation against the rate window.

    Transport-independent so MCP reaches this rather than reimplementing it — and so the
    rate check cannot be present on one surface and absent on the other. Creations are in
    the window because `create_thread` writes no turn row: a window counting only turns
    reads zero while a subject creates ten thousand empty threads.
    """
    from datetime import UTC

    from core.threads.records import RATE_LIMIT_ACTS, RATE_LIMIT_WINDOW_SECONDS

    if (
        store.recent_act_count(tenant_id=subject.tenant_id, subject_user_id=subject.subject_user_id)
        >= RATE_LIMIT_ACTS
    ):
        raise OperationRefused(
            f"more than {RATE_LIMIT_ACTS} acts in {RATE_LIMIT_WINDOW_SECONDS} seconds",
            reason_code="rate_limited",
        )
    thread_id = new_thread_id()
    record = ThreadRecord(
        thread_id=thread_id,
        # One correlation id per thread: every turn event, and every run it starts, chains
        # under this or references it. It is the join an investigator walks.
        correlation_id=f"thread-{thread_id}",
        subject_user_id=subject.subject_user_id,
        tenant_id=subject.tenant_id,
        created_at=datetime.now(UTC),
    )
    store.create_thread(record)
    return record


def thread_detail_for(
    *, subject: AuthenticatedSubject, store: Any, thread_id: str
) -> ThreadDetailResponse:
    """One thread with its turns, or refuse. Tenant collapse lives in the store."""
    record = store.get_thread(thread_id=thread_id, tenant_id=subject.tenant_id)
    if record is None:
        raise OperationRefused("no such thread", reason_code="no_such_record")
    if record.subject_user_id != subject.subject_user_id:
        raise OperationRefused("this thread belongs to someone else", reason_code="not_permitted")
    return ThreadDetailResponse(
        thread=_thread_view(record),
        turns=[_turn_view(t) for t in store.turns_of(thread_id=thread_id)],
    )


def delete_thread_for(
    *, subject: AuthenticatedSubject, store: Any, audit_sink: Any, thread_id: str
) -> None:
    """Record the deletion, then remove the view. Runs are untouched.

    The event goes first for the same reason a turn's does: a view removed with no record
    of its removal is exactly the masking this design forbids, and the ordering is what
    makes "deletion is not a masking primitive" checkable.
    """
    from core.audit.schema import AuditEventType

    record = store.get_thread(thread_id=thread_id, tenant_id=subject.tenant_id)
    if record is None:
        raise OperationRefused("no such thread", reason_code="no_such_record")
    if record.subject_user_id != subject.subject_user_id:
        raise OperationRefused("this thread belongs to someone else", reason_code="not_permitted")

    turns = store.turns_of(thread_id=thread_id)
    audit_sink.append_event(
        correlation_id=record.correlation_id,
        tenant_id=subject.tenant_id,
        event_type=AuditEventType.THREAD_DELETED,
        payload={
            "thread_id": record.thread_id,
            "subject_user_id": subject.subject_user_id,
            "turn_count": len(turns),
            "run_ids": [t.run_id for t in turns if t.run_id],
        },
    )
    store.delete_thread(thread_id=thread_id, tenant_id=subject.tenant_id)


def list_threads_for(
    *,
    subject: AuthenticatedSubject,
    store: Any,
    limit: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
) -> ThreadListResponse:
    page = store.list_threads(
        tenant_id=subject.tenant_id,
        subject_user_id=subject.subject_user_id,
        limit=limit,
        cursor=cursor,
    )
    return ThreadListResponse(threads=[_thread_view(t) for t in page.threads], cursor=page.cursor)


def send_turn_for(
    *,
    subject: AuthenticatedSubject,
    store: Any,
    audit_sink: Any,
    dispatcher: Any,
    fabric: Any,
    durability: Any,
    thread_id: str,
    body: SendTurnRequest,
) -> TurnView:
    """Resolve whether the chosen definition is startable, then let core decide.

    The `may_start` resolution happens here because this surface holds the fabric; the
    *decision* happens in core because both transports must make the same one. An
    unresolvable scope passes ``None``, which core treats as not-permitted — fail closed.
    """
    startable: bool | None = None
    if body.agent_definition_id:
        startable = _startable(fabric, subject, body.agent_definition_id)

    record = accept_turn(
        subject=subject,
        thread_id=thread_id,
        message=body.message,
        store=store,
        audit_sink=audit_sink,
        dispatcher=dispatcher,
        agent_definition_id=body.agent_definition_id,
        requested_tools=body.requested_tools,
        startable=startable,
        durability=durability,
    )
    return _turn_view(record)


def _startable(fabric: Any, subject: AuthenticatedSubject, definition_id: str) -> bool | None:
    """Whether this subject may start this definition, per 011's settled disclosure.

    Reuses `definition_views` rather than resolving scope and ceiling again: that function
    already encodes the intersection rule, the unreadable-ceiling case, and the fact that
    a definition nobody can start is still *visible*. A second resolution here would be a
    second place for `may_start` to mean something slightly different — and the whole point
    of 011 marking definitions was that one answer exists.

    ``None`` means the platform could not establish scope at all, which core treats as not
    permitted. Fail closed: "I could not tell" is never "yes".
    """
    if fabric is None:
        return None
    try:
        views = definition_views(subject=subject, fabric=fabric)
    except Exception:  # noqa: BLE001 — unresolved is not permitted; core fails closed on None
        return None
    for view in views:
        if view.agent_definition_id == definition_id:
            return bool(view.may_start)
    # Named a definition that does not exist. Not startable, and not a lie: there is
    # nothing to start.
    return False


def build_router() -> APIRouter:
    router = APIRouter(tags=["threads"])

    @router.post("/threads", response_model=ThreadView, status_code=status.HTTP_201_CREATED)
    def create_thread(subject: SubjectDep, store: ThreadStoreDep) -> ThreadView:
        """Start a conversation."""
        try:
            return _thread_view(create_thread_for(subject=subject, store=store))
        except OperationRefused as refused:
            raise _refuse(refused) from refused
        except ThreadStoreError as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

    @router.get("/threads", response_model=ThreadListResponse)
    def list_threads(
        subject: SubjectDep,
        store: ThreadStoreDep,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> ThreadListResponse:
        """The conversations this person has started."""
        try:
            return list_threads_for(subject=subject, store=store, limit=limit, cursor=cursor)
        except ThreadStoreError as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

    @router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
    def get_thread(
        thread_id: str, subject: SubjectDep, store: ThreadStoreDep
    ) -> ThreadDetailResponse:
        """One conversation, with its turns in order."""
        try:
            return thread_detail_for(subject=subject, store=store, thread_id=thread_id)
        except OperationRefused as refused:
            raise _refuse(refused) from refused
        except ThreadStoreError as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

    @router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_thread(
        thread_id: str, subject: SubjectDep, store: ThreadStoreDep, audit_sink: AuditDep
    ) -> None:
        """Remove the view. The trail keeps everything it held."""
        try:
            delete_thread_for(
                subject=subject, store=store, audit_sink=audit_sink, thread_id=thread_id
            )
        except OperationRefused as refused:
            raise _refuse(refused) from refused
        except ThreadStoreError as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

    @router.post("/threads/{thread_id}/turns", response_model=TurnView)
    def send_turn(
        thread_id: str,
        body: SendTurnRequest,
        subject: SubjectDep,
        store: ThreadStoreDep,
        audit_sink: AuditDep,
        dispatcher: DispatcherDep,
        fabric: DefinitionsDep,
        durability: DurabilityDep,
    ) -> TurnView:
        """Say something. The platform records it, then answers."""
        try:
            return send_turn_for(
                subject=subject,
                store=store,
                audit_sink=audit_sink,
                dispatcher=dispatcher,
                fabric=fabric,
                durability=durability,
                thread_id=thread_id,
                body=body,
            )
        except OperationRefused as refused:
            raise _refuse(refused) from refused
        except ThreadStoreError as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

    return router


__all__ = [
    "SendTurnRequest",
    "ThreadDetailResponse",
    "ThreadListResponse",
    "ThreadView",
    "TurnView",
    "build_router",
    "create_thread_for",
    "delete_thread_for",
    "list_threads_for",
    "send_turn_for",
    "thread_detail_for",
]
