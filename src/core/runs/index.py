# SPDX-License-Identifier: Apache-2.0
"""The run index — what a person has started.

`checkpoints` answers "where did this run get to". It carries no subject and no tenant,
because resume never needed them and 005 built it for resume. So "what have I started" was
unanswerable from durable state: the only places a subject appeared were the audit trail —
the forensic path US3 exists to stop using as a product path — and a per-process dict that
died with the surface.

**A seam, not a table.** The protocol has an in-memory implementation and a Postgres one,
and the shape is load-bearing rather than stylistic: `InProcessDispatcher` is what every
hermetic row builds, so a dispatcher that unconditionally wrote to Postgres would put a
database inside the fast lane. The in-memory index then serves the hermetic halves of the
list and stop rows for free.

**Insert-only.** State lives on the checkpoint, which stays authoritative; a listing joins
it in at read time. An index that carried state would be a second writer of the fact the
checkpoint's row lock exists to serialise — and two records of one run's state will
eventually disagree about which is current.

**Never backfilled.** It starts empty and lists runs dispatched after this feature. A
backfill from audit would launder the forensic path through a migration script, which is
the dependency US3 removes, one step removed. The empty first page is correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from core.errors import CoreError

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

#: How many runs one page carries unless a caller asks for fewer.
#:
#: Bounded because FR-005 requires it, and modest because the consumer is a person looking
#: at a list. A caller wanting everything pages; a caller wanting one page gets one.
DEFAULT_PAGE_SIZE = 50

#: The ceiling on what a caller may request, so a page size cannot become an unbounded read
#: by being asked for politely.
MAX_PAGE_SIZE = 200


class RunIndexError(CoreError):
    """The index could not be read or written. Never swallowed into an empty list.

    An empty list is a legitimate answer meaning "you have started nothing"; a failed read
    is the platform not knowing. Collapsing them would tell a person their work is gone.
    """


@dataclass(frozen=True)
class RunIndexEntry:
    """One dispatched run, as the index remembers it.

    Everything here is known at dispatch time and never changes. What *does* change — the
    run's state — is deliberately absent, and joined from the checkpoint by whoever reads.
    """

    run_id: str
    correlation_id: str
    subject_user_id: str
    tenant_id: str
    agent_definition_id: str
    created_at: datetime


@dataclass(frozen=True)
class RunPage:
    """A bounded slice of a subject's runs, and how to ask for the next.

    ``cursor`` is ``None`` when there is nothing further. **It carries no total**, and that
    is FR-004 rather than an omission: a count of what was withheld is exactly the
    disclosure the tenant boundary exists to prevent.
    """

    entries: list[RunIndexEntry]
    cursor: str | None


class RunIndex(Protocol):
    """Where dispatched runs are recorded so their starter can find them again."""

    def record(self, entry: RunIndexEntry) -> None:
        """Note a dispatched run. Called in the same motion as the dispatch."""
        ...

    def list_for(
        self,
        *,
        tenant_id: str,
        subject_user_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> RunPage:
        """One page of this subject's runs in this tenant, newest first."""
        ...

    def get(self, *, run_id: str, tenant_id: str) -> RunIndexEntry | None:
        """One entry, tenant-scoped. ``None`` covers both absent and another tenant's.

        The collapse is deliberate and belongs here rather than at each call site: a
        reader that could tell the two apart would let anyone probe for identifiers in
        other tenants. Which it was is recorded by the caller in the trail.
        """
        ...


def encode_cursor(entry: RunIndexEntry) -> str:
    """A keyset cursor: where to resume, and nothing else.

    ``(created_at, run_id)`` of the last row returned — enough to continue, and carrying no
    offset and no count. An `OFFSET`-shaped cursor reads identically in the happy path and
    leaks the size of what a caller cannot see.
    """
    return f"{entry.created_at.isoformat()}|{entry.run_id}"


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    """Parse a cursor, or refuse. A malformed cursor is not an empty page."""
    stamp, _, run_id = cursor.partition("|")
    if not stamp or not run_id:
        raise RunIndexError(f"malformed cursor {cursor!r}")
    try:
        return datetime.fromisoformat(stamp), run_id
    except ValueError as exc:
        raise RunIndexError(f"malformed cursor {cursor!r}") from exc


def _bounded(limit: int) -> int:
    return max(1, min(limit, MAX_PAGE_SIZE))


@dataclass
class InMemoryRunIndex:
    """The index for anything that is not a real deployment.

    Used by `InProcessDispatcher` — which is what every hermetic surface row builds — and
    by the hermetic halves of the list and stop rows. Same semantics as the Postgres one,
    including the tenant collapse in :meth:`get`, so a row proven here is proven about the
    behaviour rather than about the storage.
    """

    entries: dict[str, RunIndexEntry] = field(default_factory=dict)

    def record(self, entry: RunIndexEntry) -> None:
        self.entries[entry.run_id] = entry

    def list_for(
        self,
        *,
        tenant_id: str,
        subject_user_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> RunPage:
        # Tenant first, subject second — the same order the Postgres index is built in, so
        # the two implementations cannot diverge on which filter is the access path.
        owned = [
            e
            for e in self.entries.values()
            if e.tenant_id == tenant_id and e.subject_user_id == subject_user_id
        ]
        owned.sort(key=lambda e: (e.created_at, e.run_id), reverse=True)

        if cursor is not None:
            after_stamp, after_id = decode_cursor(cursor)
            owned = [e for e in owned if (e.created_at, e.run_id) < (after_stamp, after_id)]

        size = _bounded(limit)
        page, remainder = owned[:size], owned[size:]
        return RunPage(entries=page, cursor=encode_cursor(page[-1]) if page and remainder else None)

    def get(self, *, run_id: str, tenant_id: str) -> RunIndexEntry | None:
        entry = self.entries.get(run_id)
        if entry is None or entry.tenant_id != tenant_id:
            return None
        return entry


class PostgresRunIndex:
    """The index for a real deployment, under the credentials the workload already holds."""

    def __init__(
        self,
        *,
        credentials: Any,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "brieve",
    ) -> None:
        self._credentials = credentials
        self._host = host
        self._port = port
        self._dbname = dbname

    def _connect(self) -> Any:
        import pg8000.dbapi

        cred = self._credentials.fetch()
        return pg8000.dbapi.connect(
            host=self._host,
            port=self._port,
            database=self._dbname,
            user=cred.username,
            password=cred.password,
        )

    def _run(self, work: Any) -> Any:
        conn = None
        try:
            conn = self._connect()
            return work(conn)
        except Exception as exc:
            raise RunIndexError(f"run index unavailable: {type(exc).__name__}: {exc}") from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001 — a close failure must not mask the real one
                    pass

    def migrate(self) -> None:
        """Apply the schema. Idempotent — every statement is IF NOT EXISTS."""

        def work(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(SCHEMA_PATH.read_text())
            conn.commit()

        self._run(work)

    def record(self, entry: RunIndexEntry) -> None:
        def work(conn: Any) -> None:
            cur = conn.cursor()
            # ON CONFLICT DO NOTHING rather than an upsert: the index is insert-only, and a
            # re-dispatch under an existing run id is a resume, whose facts are unchanged.
            cur.execute(
                "INSERT INTO run_index (run_id, correlation_id, subject_user_id, "
                "tenant_id, agent_definition_id, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (run_id) DO NOTHING",
                (
                    entry.run_id,
                    entry.correlation_id,
                    entry.subject_user_id,
                    entry.tenant_id,
                    entry.agent_definition_id,
                    entry.created_at,
                ),
            )
            conn.commit()

        self._run(work)

    def list_for(
        self,
        *,
        tenant_id: str,
        subject_user_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> RunPage:
        size = _bounded(limit)

        def work(conn: Any) -> RunPage:
            cur = conn.cursor()
            # One extra row, to learn whether there is a next page without counting what
            # remains. A COUNT here would be the withholding disclosure FR-004 forbids,
            # arrived at by way of a convenience.
            if cursor is None:
                cur.execute(
                    "SELECT run_id, correlation_id, subject_user_id, tenant_id, "
                    "       agent_definition_id, created_at "
                    "FROM run_index WHERE tenant_id = %s AND subject_user_id = %s "
                    "ORDER BY created_at DESC, run_id DESC LIMIT %s",
                    (tenant_id, subject_user_id, size + 1),
                )
            else:
                after_stamp, after_id = decode_cursor(cursor)
                cur.execute(
                    "SELECT run_id, correlation_id, subject_user_id, tenant_id, "
                    "       agent_definition_id, created_at "
                    "FROM run_index WHERE tenant_id = %s AND subject_user_id = %s "
                    "  AND (created_at, run_id) < (%s, %s) "
                    "ORDER BY created_at DESC, run_id DESC LIMIT %s",
                    (tenant_id, subject_user_id, after_stamp, after_id, size + 1),
                )
            rows = cur.fetchall()
            has_more = len(rows) > size
            entries = [_entry(r) for r in rows[:size]]
            return RunPage(
                entries=entries,
                cursor=encode_cursor(entries[-1]) if entries and has_more else None,
            )

        page: RunPage = self._run(work)
        return page

    def get(self, *, run_id: str, tenant_id: str) -> RunIndexEntry | None:
        def work(conn: Any) -> RunIndexEntry | None:
            cur = conn.cursor()
            # The tenant filter is in the WHERE clause rather than applied after: a row
            # from another tenant is never read, so it cannot be leaked by a later mistake.
            cur.execute(
                "SELECT run_id, correlation_id, subject_user_id, tenant_id, "
                "       agent_definition_id, created_at "
                "FROM run_index WHERE run_id = %s AND tenant_id = %s",
                (run_id, tenant_id),
            )
            row = cur.fetchone()
            return _entry(row) if row else None

        entry: RunIndexEntry | None = self._run(work)
        return entry


def _entry(row: Any) -> RunIndexEntry:
    created = row[5]
    return RunIndexEntry(
        run_id=str(row[0]),
        correlation_id=str(row[1]),
        subject_user_id=str(row[2]),
        tenant_id=str(row[3]),
        agent_definition_id=str(row[4]),
        created_at=created if created.tzinfo else created.replace(tzinfo=UTC),
    )


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "InMemoryRunIndex",
    "PostgresRunIndex",
    "RunIndex",
    "RunIndexEntry",
    "RunIndexError",
    "RunPage",
    "decode_cursor",
    "encode_cursor",
]
