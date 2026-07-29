# SPDX-License-Identifier: Apache-2.0
"""Where threads live, and the in-memory implementation every hermetic row builds.

**A seam, not a table** — the same shape 011 drew for the run index, for the same reason:
`InProcessDispatcher` is what every hermetic surface row constructs, so a store that
unconditionally reached Postgres would put a database inside the fork-safe lane.

The semantics that matter are defined *here*, in the protocol's docstrings, so the two
implementations agree by construction rather than by inspection: the tenant collapse in
:meth:`get_thread`, the keyset listing with no totals, `seq` assigned per-thread without
gaps, and the rate window as a **sum of two counts**.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from core.errors import CoreError
from core.threads.records import (
    RATE_LIMIT_WINDOW_SECONDS,
    RunInput,
    ThreadRecord,
    TurnRecord,
)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

#: How many threads one page carries unless a caller asks for fewer. 011's numbers, and
#: deliberately the same ones: a person reading a list does not care which list it is.
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200


class ThreadStoreError(CoreError):
    """The store could not be read or written.

    **Never collapsed into "no threads".** An empty list means this person has started
    nothing; a failed read means the platform does not know. Telling someone their
    conversations are gone when the database is merely unreachable is the worse of the two
    lies, and it is the one a bare `except` produces.
    """


@dataclass(frozen=True)
class ThreadPage:
    """A bounded slice of a subject's threads, and how to ask for the next.

    **No total**, for the reason 011 recorded: a count of what was withheld is exactly the
    disclosure the tenant boundary exists to prevent.
    """

    threads: list[ThreadRecord]
    cursor: str | None


def new_thread_id() -> str:
    return f"th-{uuid.uuid4().hex[:16]}"


def new_turn_id() -> str:
    return f"tn-{uuid.uuid4().hex[:16]}"


def encode_cursor(thread: ThreadRecord) -> str:
    """Keyset: where to resume, and nothing else. No offset, no count."""
    return f"{thread.created_at.isoformat()}|{thread.thread_id}"


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Parse a cursor, or refuse. A malformed cursor is not an empty page."""
    stamp, _, thread_id = cursor.partition("|")
    if not stamp or not thread_id:
        raise ThreadStoreError(f"malformed cursor {cursor!r}")
    try:
        return datetime.fromisoformat(stamp), thread_id
    except ValueError as exc:
        raise ThreadStoreError(f"malformed cursor {cursor!r}") from exc


def bounded(limit: int) -> int:
    return max(1, min(limit, MAX_PAGE_SIZE))


def window_start(now: datetime | None = None) -> datetime:
    return (now or datetime.now(UTC)) - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)


class ThreadStore(Protocol):
    """Threads, turns, and run inputs. One store because they share a transaction."""

    def create_thread(self, thread: ThreadRecord) -> None: ...

    def get_thread(self, *, thread_id: str, tenant_id: str) -> ThreadRecord | None:
        """Tenant-scoped. ``None`` covers absent **and** another tenant's, deliberately.

        The collapse lives here rather than at each call site so no reader can accidentally
        tell them apart — a reader that could would let anyone probe for identifiers in
        other tenants. Which it was is the caller's to record, not to reveal.
        """
        ...

    def list_threads(
        self,
        *,
        tenant_id: str,
        subject_user_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> ThreadPage:
        """One page of this subject's threads in this tenant, newest first."""
        ...

    def delete_thread(self, *, thread_id: str, tenant_id: str) -> bool:
        """Remove the thread and its turns. ``run_inputs`` and runs are untouched."""
        ...

    def set_title(self, *, thread_id: str, title: str) -> None:
        """Set the title if it has none. Idempotent; never overwrites."""
        ...

    def append_turn(self, turn: TurnRecord) -> TurnRecord:
        """Append with the next ``seq`` for its thread, assigned atomically.

        Returns the stored record, whose ``seq`` is authoritative — the caller's is
        ignored. Two concurrent sends must not receive the same number.
        """
        ...

    def turns_of(self, *, thread_id: str) -> list[TurnRecord]:
        """Every turn of a thread, in ``seq`` order."""
        ...

    def recent_act_count(self, *, tenant_id: str, subject_user_id: str) -> int:
        """Turns **plus** thread creations in the rate window.

        The sum is the requirement, not an optimization: `create_thread` writes no turn
        row, so a count over turns alone reads zero while a subject creates ten thousand
        empty threads.
        """
        ...

    def put_run_input(self, run_input: RunInput) -> None: ...

    def get_run_input(self, *, run_id: str) -> RunInput | None: ...


@dataclass
class InMemoryThreadStore:
    """The store for anything that is not a real deployment.

    Same semantics as the Postgres one — including the tenant collapse and the two-count
    rate window — so a row proven here is proven about the behaviour rather than about the
    storage.
    """

    threads: dict[str, ThreadRecord] = field(default_factory=dict)
    turns: dict[str, list[TurnRecord]] = field(default_factory=dict)
    run_inputs: dict[str, RunInput] = field(default_factory=dict)

    def create_thread(self, thread: ThreadRecord) -> None:
        self.threads[thread.thread_id] = thread
        self.turns.setdefault(thread.thread_id, [])

    def get_thread(self, *, thread_id: str, tenant_id: str) -> ThreadRecord | None:
        found = self.threads.get(thread_id)
        if found is None or found.tenant_id != tenant_id:
            return None
        return found

    def list_threads(
        self,
        *,
        tenant_id: str,
        subject_user_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> ThreadPage:
        # Tenant first, subject second — the same order the Postgres index is built in, so
        # the two cannot diverge on which filter is the access path.
        owned = [
            t
            for t in self.threads.values()
            if t.tenant_id == tenant_id and t.subject_user_id == subject_user_id
        ]
        owned.sort(key=lambda t: (t.created_at, t.thread_id), reverse=True)

        if cursor is not None:
            after_stamp, after_id = decode_cursor(cursor)
            owned = [t for t in owned if (t.created_at, t.thread_id) < (after_stamp, after_id)]

        size = bounded(limit)
        page, remainder = owned[:size], owned[size:]
        return ThreadPage(
            threads=page, cursor=encode_cursor(page[-1]) if page and remainder else None
        )

    def delete_thread(self, *, thread_id: str, tenant_id: str) -> bool:
        found = self.get_thread(thread_id=thread_id, tenant_id=tenant_id)
        if found is None:
            return False
        del self.threads[thread_id]
        self.turns.pop(thread_id, None)
        return True

    def set_title(self, *, thread_id: str, title: str) -> None:
        found = self.threads.get(thread_id)
        if found is not None and found.title is None:
            self.threads[thread_id] = ThreadRecord(
                thread_id=found.thread_id,
                correlation_id=found.correlation_id,
                subject_user_id=found.subject_user_id,
                tenant_id=found.tenant_id,
                created_at=found.created_at,
                title=title,
            )

    def append_turn(self, turn: TurnRecord) -> TurnRecord:
        existing = self.turns.setdefault(turn.thread_id, [])
        stored = TurnRecord(
            turn_id=turn.turn_id,
            thread_id=turn.thread_id,
            tenant_id=turn.tenant_id,
            subject_user_id=turn.subject_user_id,
            seq=len(existing),
            message=turn.message,
            disposition=turn.disposition,
            created_at=turn.created_at,
            reason=turn.reason,
            run_id=turn.run_id,
            agent_definition_id=turn.agent_definition_id,
            context_run_ids=turn.context_run_ids,
            context_dropped=turn.context_dropped,
        )
        existing.append(stored)
        return stored

    def turns_of(self, *, thread_id: str) -> list[TurnRecord]:
        return list(self.turns.get(thread_id, []))

    def recent_act_count(self, *, tenant_id: str, subject_user_id: str) -> int:
        since = window_start()
        turns = sum(
            1
            for rows in self.turns.values()
            for t in rows
            if t.tenant_id == tenant_id
            and t.subject_user_id == subject_user_id
            and t.created_at > since
        )
        creations = sum(
            1
            for t in self.threads.values()
            if t.tenant_id == tenant_id
            and t.subject_user_id == subject_user_id
            and t.created_at > since
        )
        return turns + creations

    def put_run_input(self, run_input: RunInput) -> None:
        # Insert-only, matching the Postgres ON CONFLICT DO NOTHING: a re-dispatch under an
        # existing run id is a resume, whose input is unchanged.
        self.run_inputs.setdefault(run_input.run_id, run_input)

    def get_run_input(self, *, run_id: str) -> RunInput | None:
        return self.run_inputs.get(run_id)


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "SCHEMA_PATH",
    "InMemoryThreadStore",
    "ThreadPage",
    "ThreadStore",
    "ThreadStoreError",
    "bounded",
    "decode_cursor",
    "encode_cursor",
    "new_thread_id",
    "new_turn_id",
    "window_start",
]
