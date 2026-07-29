# SPDX-License-Identifier: Apache-2.0
"""Accepting a turn: the one decision both transports make.

**The ordering is the contract**, and it is here rather than in a surface so the two
transports cannot answer differently. A surface owns request shape and status codes; this
owns what happens, which is what makes verdict parity structural rather than diligent.

The load-bearing distinction is **pre-acceptance versus accepted**. A message the platform
never accepted — over the rate window, over the size bound — gets a fixed-size
``TURN_REFUSED`` event carrying its size and never its content, and produces no turn. A
message the platform *did* accept gets ``TURN_RECORDED`` carrying the message itself,
written **before** anything else happens, and that includes the ones it then declines or
refuses on scope. Without the split, either refused messages vanish from the record, or
the append-only trail is growable at whatever rate a caller can be refused.

**Nothing here imports a surface.** The dispatcher is typed by a local Protocol: `core`
imports `surfaces` nowhere in this repository, and this module does not get to be the
first.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from core.audit.schema import AuditEventType
from core.audit.sink import AuditSink
from core.identity.types import AuthenticatedSubject
from core.runs.refusals import OperationRefused
from core.threads.records import (
    CONTEXT_TURNS,
    MAX_MESSAGE_BYTES,
    RATE_LIMIT_ACTS,
    RATE_LIMIT_WINDOW_SECONDS,
    RunInput,
    ThreadRecord,
    TurnDisposition,
    TurnRecord,
    message_size_bytes,
    title_from,
)
from core.threads.store import ThreadStore, new_turn_id


class TurnDispatcher(Protocol):
    """What a turn needs from a dispatcher, and nothing more.

    A **local** Protocol rather than an import of `surfaces.dispatch.types`: the direction
    of that import is the layering, and structural typing gets the same safety without
    reversing it. It also keeps this module testable with a double that has no scheduler
    anywhere near it.
    """

    def dispatch(
        self,
        *,
        correlation_id: str,
        subject_user_id: str,
        tenant_id: str,
        agent_definition_id: str,
        requested_tools: frozenset[str],
        subject_roles: frozenset[str] = frozenset(),
    ) -> Any: ...


class TurnStorageUnavailable(OperationRefused):
    """The turn could not be recorded, so it must not happen.

    A subclass rather than a bare error because the fail-closed direction has to be "no
    run", never "run anyway": if the sink is missing or the store is unreachable, the
    platform cannot produce the evidence that a dispatch requires, and dispatching without
    it would be a run nobody can explain. Refusing is the honest answer.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, reason_code="not_permitted")


def _resolved_results(durability: Any, run_id: str) -> bool:
    """Whether this run has a result to carry forward.

    Deliberately tolerant: a durability provider that cannot answer is treated as "no
    result", so a transient read failure narrows the context rather than refusing the
    turn. Losing context is visible to the person (it shows as dropped); refusing their
    message because an unrelated read blinked is not.
    """
    if durability is None:
        return False
    try:
        blob = durability.load(run_id)
    except Exception:  # noqa: BLE001 — see docstring: narrow the context, never refuse
        return False
    return bool(blob is not None and (blob.payload or {}))


def compute_context(
    store: ThreadStore,
    *,
    thread_id: str,
    durability: Any = None,
    limit: int = CONTEXT_TURNS,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """What this turn carries forward, and what fell outside the bound.

    Newest first, dispatched turns only, and only those whose runs produced something.
    Declined and refused turns never enter context — they have no run, so there is nothing
    of theirs to carry.

    Returns ``(carried, dropped)``. `dropped` exists so the bound's effect is inspectable
    after the fact and renderable to the person (FR-009b): someone who does not know the
    platform forgot something reads a worse answer as a worse platform.
    """
    candidates = [
        t.run_id
        for t in reversed(store.turns_of(thread_id=thread_id))
        if t.disposition is TurnDisposition.DISPATCHED and t.run_id
    ]
    with_results = [rid for rid in candidates if _resolved_results(durability, rid)]
    return tuple(with_results[:limit]), tuple(with_results[limit:])


def accept_turn(
    *,
    subject: AuthenticatedSubject,
    thread_id: str,
    message: str,
    store: ThreadStore,
    audit_sink: AuditSink | None,
    dispatcher: TurnDispatcher | None = None,
    agent_definition_id: str | None = None,
    requested_tools: frozenset[str] = frozenset(),
    startable: bool | None = None,
    durability: Any = None,
    now: datetime | None = None,
) -> TurnRecord:
    """Accept a message into a thread, or refuse it. The contract's ordered semantics.

    ``startable`` is the caller's resolution of 011's ``may_start`` intersection for the
    selected definition — resolved by the surface, which already holds the fabric, and
    passed in so this module needs no identity fabric of its own. ``None`` means the
    caller could not determine it, which fails closed: unresolved is not permitted.
    """
    stamp = now or datetime.now(UTC)

    # 0. Evidence-first is only possible with somewhere to write. No sink, no turn.
    if audit_sink is None:
        raise TurnStorageUnavailable(
            "this surface is assembled without an audit sink, so a turn cannot be recorded"
        )

    # 1. Resolve the thread. Absent and another tenant's are indistinguishable here, as
    #    they are everywhere else — the collapse lives in the store.
    thread = store.get_thread(thread_id=thread_id, tenant_id=subject.tenant_id)
    if thread is None:
        raise OperationRefused("no such thread", reason_code="no_such_record")
    if thread.subject_user_id != subject.subject_user_id:
        raise OperationRefused("this thread belongs to someone else", reason_code="not_permitted")

    # 2. Pre-acceptance checks. Each writes a fixed-size TURN_REFUSED — the attempt is
    #    visible, its content is not, and per-attempt trail growth stays bounded.
    size = message_size_bytes(message)
    if size > MAX_MESSAGE_BYTES:
        _record_refusal(audit_sink, thread, subject, reason="message_too_large", size=size)
        raise OperationRefused(
            f"message is {size} bytes; the bound is {MAX_MESSAGE_BYTES}",
            reason_code="message_too_large",
        )
    if store.recent_act_count(
        tenant_id=subject.tenant_id, subject_user_id=subject.subject_user_id
    ) >= (RATE_LIMIT_ACTS):
        _record_refusal(audit_sink, thread, subject, reason="rate_limited", size=size)
        raise OperationRefused(
            f"more than {RATE_LIMIT_ACTS} acts in {RATE_LIMIT_WINDOW_SECONDS} seconds",
            reason_code="rate_limited",
        )

    # 3. What carries forward, and what does not.
    carried, dropped = compute_context(store, thread_id=thread_id, durability=durability)

    # 4. Decide the disposition — but write the evidence before acting on it.
    disposition, reason = _decide(
        agent_definition_id=agent_definition_id, startable=startable, dispatcher=dispatcher
    )

    turn_id = new_turn_id()
    run_id = (
        f"{thread.correlation_id}-t{turn_id[-8:]}"
        if disposition is (TurnDisposition.DISPATCHED)
        else None
    )

    audit_sink.append_event(
        correlation_id=thread.correlation_id,
        tenant_id=subject.tenant_id,
        event_type=AuditEventType.TURN_RECORDED,
        payload={
            "thread_id": thread.thread_id,
            "turn_id": turn_id,
            "subject_user_id": subject.subject_user_id,
            "message": message,
            "disposition": str(disposition),
            "reason": reason,
            "agent_definition_id": agent_definition_id,
            "run_id": run_id,
            "context_run_ids": list(carried),
            "context_dropped": list(dropped),
        },
        timestamp=stamp,
    )

    # 5. Act. Everything above this line is recorded whether or not this succeeds.
    if disposition is TurnDisposition.DISPATCHED:
        assert run_id is not None and agent_definition_id is not None and dispatcher is not None
        store.put_run_input(
            RunInput(run_id=run_id, message=message, context_run_ids=carried, created_at=stamp)
        )
        dispatcher.dispatch(
            correlation_id=run_id,
            subject_user_id=subject.subject_user_id,
            tenant_id=subject.tenant_id,
            agent_definition_id=agent_definition_id,
            requested_tools=requested_tools,
            subject_roles=subject.roles,
        )

    stored = store.append_turn(
        TurnRecord(
            turn_id=turn_id,
            thread_id=thread.thread_id,
            tenant_id=subject.tenant_id,
            subject_user_id=subject.subject_user_id,
            seq=-1,  # the store assigns it
            message=message,
            disposition=disposition,
            created_at=stamp,
            reason=reason,
            run_id=run_id,
            agent_definition_id=agent_definition_id,
            context_run_ids=carried,
            context_dropped=dropped,
        )
    )
    if thread.title is None:
        store.set_title(thread_id=thread.thread_id, title=title_from(message))
    return stored


def _decide(
    *,
    agent_definition_id: str | None,
    startable: bool | None,
    dispatcher: TurnDispatcher | None,
) -> tuple[TurnDisposition, str | None]:
    """Declined, refused, or dispatched — and the difference between the first two matters.

    `nothing_to_dispatch` says the platform cannot do this; `not_permitted` says this
    person may not. Conflating them tells someone their access is fine when it is not.
    """
    if not agent_definition_id or dispatcher is None:
        return TurnDisposition.DECLINED, "nothing_to_dispatch"
    if startable is not True:
        # None (unresolved) lands here with False: fail closed. A scope the platform could
        # not establish is not a scope that permits.
        return TurnDisposition.REFUSED, "not_permitted"
    return TurnDisposition.DISPATCHED, None


def _record_refusal(
    audit_sink: AuditSink,
    thread: ThreadRecord,
    subject: AuthenticatedSubject,
    *,
    reason: str,
    size: int,
) -> None:
    """The pre-acceptance record: the size, never the content."""
    audit_sink.append_event(
        correlation_id=thread.correlation_id,
        tenant_id=subject.tenant_id,
        event_type=AuditEventType.TURN_REFUSED,
        payload={
            "thread_id": thread.thread_id,
            "subject_user_id": subject.subject_user_id,
            "reason": reason,
            "message_bytes": size,
        },
    )


__all__ = [
    "TurnDispatcher",
    "TurnStorageUnavailable",
    "accept_turn",
    "compute_context",
]
