# SPDX-License-Identifier: Apache-2.0
"""The thread store for a real deployment, under the credentials the workload holds.

Follows 011's store pattern exactly — connect per operation from a `fetch()`ed dynamic
credential, wrap every failure in the package's own error so a driver exception never
surfaces as "no threads". The one thing this store does that 011's did not is assign a
sequence number under a row lock, which is the whole reason turns and threads live in one
store rather than two.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.threads.records import RunInput, ThreadRecord, TurnDisposition, TurnRecord
from core.threads.store import (
    DEFAULT_PAGE_SIZE,
    SCHEMA_PATH,
    ThreadPage,
    ThreadStoreError,
    bounded,
    decode_cursor,
    encode_cursor,
    window_start,
)


def _join(values: tuple[str, ...]) -> str:
    return ",".join(values)


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(v for v in (value or "").split(",") if v)


def _aware(stamp: Any) -> datetime:
    """Timestamps come back from the driver naive; the platform reasons in UTC."""
    parsed: datetime = stamp
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class PostgresThreadStore:
    """Threads, turns, and run inputs in the enclave database."""

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
            raise ThreadStoreError(
                f"thread store unavailable: {type(exc).__name__}: {exc}"
            ) from exc
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

    # ---------------------------------------------------------------- threads

    def create_thread(self, thread: ThreadRecord) -> None:
        def work(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO threads (thread_id, correlation_id, subject_user_id, "
                "tenant_id, title, created_at) VALUES (%s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (thread_id) DO NOTHING",
                (
                    thread.thread_id,
                    thread.correlation_id,
                    thread.subject_user_id,
                    thread.tenant_id,
                    thread.title,
                    thread.created_at,
                ),
            )
            conn.commit()

        self._run(work)

    def get_thread(self, *, thread_id: str, tenant_id: str) -> ThreadRecord | None:
        def work(conn: Any) -> ThreadRecord | None:
            cur = conn.cursor()
            # The tenant filter is in the WHERE clause rather than applied after: another
            # tenant's row is never read, so it cannot be leaked by a later mistake.
            cur.execute(
                "SELECT thread_id, correlation_id, subject_user_id, tenant_id, title, "
                "       created_at FROM threads WHERE thread_id = %s AND tenant_id = %s",
                (thread_id, tenant_id),
            )
            row = cur.fetchone()
            return _thread(row) if row else None

        found: ThreadRecord | None = self._run(work)
        return found

    def list_threads(
        self,
        *,
        tenant_id: str,
        subject_user_id: str,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> ThreadPage:
        size = bounded(limit)

        def work(conn: Any) -> ThreadPage:
            cur = conn.cursor()
            columns = (
                "SELECT thread_id, correlation_id, subject_user_id, tenant_id, title, created_at "
                "FROM threads WHERE tenant_id = %s AND subject_user_id = %s "
            )
            order = "ORDER BY created_at DESC, thread_id DESC LIMIT %s"
            # One extra row, to learn whether there is a next page without counting what
            # remains. A COUNT would be the withholding disclosure the tenant boundary
            # forbids, arrived at by way of a convenience.
            if cursor is None:
                cur.execute(columns + order, (tenant_id, subject_user_id, size + 1))
            else:
                after_stamp, after_id = decode_cursor(cursor)
                cur.execute(
                    columns + "AND (created_at, thread_id) < (%s, %s) " + order,
                    (tenant_id, subject_user_id, after_stamp, after_id, size + 1),
                )
            rows = cur.fetchall()
            has_more = len(rows) > size
            threads = [_thread(r) for r in rows[:size]]
            return ThreadPage(
                threads=threads,
                cursor=encode_cursor(threads[-1]) if threads and has_more else None,
            )

        page: ThreadPage = self._run(work)
        return page

    def delete_thread(self, *, thread_id: str, tenant_id: str) -> bool:
        def work(conn: Any) -> bool:
            cur = conn.cursor()
            # Turns go with it by ON DELETE CASCADE. `run_inputs` is deliberately not
            # referenced: the run outlives the view.
            cur.execute(
                "DELETE FROM threads WHERE thread_id = %s AND tenant_id = %s",
                (thread_id, tenant_id),
            )
            deleted = int(cur.rowcount or 0)
            conn.commit()
            return deleted > 0

        removed: bool = self._run(work)
        return removed

    def set_title(self, *, thread_id: str, title: str) -> None:
        def work(conn: Any) -> None:
            cur = conn.cursor()
            # `IS NULL` rather than a read-then-write: the title is set once, and a
            # check-then-set would race two first turns into overwriting each other.
            cur.execute(
                "UPDATE threads SET title = %s WHERE thread_id = %s AND title IS NULL",
                (title, thread_id),
            )
            conn.commit()

        self._run(work)

    # ------------------------------------------------------------------ turns

    def append_turn(self, turn: TurnRecord) -> TurnRecord:
        def work(conn: Any) -> TurnRecord:
            cur = conn.cursor()
            # Lock the thread row first. `seq` is dense per thread, so two tabs sending at
            # once must not compute the same next value — the same first-writer-wins
            # discipline the audit stream heads use, and for the same reason: without the
            # lock both readers see the same MAX and both write it.
            cur.execute("SELECT 1 FROM threads WHERE thread_id = %s FOR UPDATE", (turn.thread_id,))
            if cur.fetchone() is None:
                raise ThreadStoreError(f"thread {turn.thread_id!r} does not exist")
            cur.execute(
                "SELECT COALESCE(MAX(seq) + 1, 0) FROM thread_turns WHERE thread_id = %s",
                (turn.thread_id,),
            )
            row = cur.fetchone()
            seq = int(row[0]) if row else 0
            cur.execute(
                "INSERT INTO thread_turns (turn_id, thread_id, tenant_id, subject_user_id, "
                "seq, message, disposition, reason, run_id, agent_definition_id, "
                "context_run_ids, context_dropped, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    turn.turn_id,
                    turn.thread_id,
                    turn.tenant_id,
                    turn.subject_user_id,
                    seq,
                    turn.message,
                    str(turn.disposition),
                    turn.reason,
                    turn.run_id,
                    turn.agent_definition_id,
                    _join(turn.context_run_ids),
                    _join(turn.context_dropped),
                    turn.created_at,
                ),
            )
            conn.commit()
            return TurnRecord(
                turn_id=turn.turn_id,
                thread_id=turn.thread_id,
                tenant_id=turn.tenant_id,
                subject_user_id=turn.subject_user_id,
                seq=seq,
                message=turn.message,
                disposition=turn.disposition,
                created_at=turn.created_at,
                reason=turn.reason,
                run_id=turn.run_id,
                agent_definition_id=turn.agent_definition_id,
                context_run_ids=turn.context_run_ids,
                context_dropped=turn.context_dropped,
            )

        stored: TurnRecord = self._run(work)
        return stored

    def turns_of(self, *, thread_id: str) -> list[TurnRecord]:
        def work(conn: Any) -> list[TurnRecord]:
            cur = conn.cursor()
            cur.execute(
                "SELECT turn_id, thread_id, tenant_id, subject_user_id, seq, message, "
                "       disposition, reason, run_id, agent_definition_id, context_run_ids, "
                "       context_dropped, created_at "
                "FROM thread_turns WHERE thread_id = %s ORDER BY seq",
                (thread_id,),
            )
            return [_turn(r) for r in cur.fetchall()]

        rows: list[TurnRecord] = self._run(work)
        return rows

    def recent_act_count(self, *, tenant_id: str, subject_user_id: str) -> int:
        since = window_start()

        def work(conn: Any) -> int:
            cur = conn.cursor()
            # Two counts, summed. Creations are in the sum because `create_thread` writes
            # no turn row — a window over turns alone reads zero while a subject creates
            # ten thousand empty threads. Each leg is served by its table's own
            # (tenant, subject, created_at) index.
            cur.execute(
                "SELECT (SELECT COUNT(*) FROM thread_turns "
                "        WHERE tenant_id = %s AND subject_user_id = %s AND created_at > %s) "
                "     + (SELECT COUNT(*) FROM threads "
                "        WHERE tenant_id = %s AND subject_user_id = %s AND created_at > %s)",
                (tenant_id, subject_user_id, since, tenant_id, subject_user_id, since),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0

        count: int = self._run(work)
        return count

    # ------------------------------------------------------------- run inputs

    def put_run_input(self, run_input: RunInput) -> None:
        def work(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO run_inputs (run_id, message, context_run_ids, created_at) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (run_id) DO NOTHING",
                (
                    run_input.run_id,
                    run_input.message,
                    _join(run_input.context_run_ids),
                    run_input.created_at,
                ),
            )
            conn.commit()

        self._run(work)

    def get_run_input(self, *, run_id: str) -> RunInput | None:
        def work(conn: Any) -> RunInput | None:
            cur = conn.cursor()
            cur.execute(
                "SELECT run_id, message, context_run_ids, created_at FROM run_inputs "
                "WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            return RunInput(
                run_id=str(row[0]),
                message=str(row[1]),
                context_run_ids=_split(row[2]),
                created_at=_aware(row[3]),
            )

        found: RunInput | None = self._run(work)
        return found


def _thread(row: Any) -> ThreadRecord:
    return ThreadRecord(
        thread_id=str(row[0]),
        correlation_id=str(row[1]),
        subject_user_id=str(row[2]),
        tenant_id=str(row[3]),
        title=str(row[4]) if row[4] is not None else None,
        created_at=_aware(row[5]),
    )


def _turn(row: Any) -> TurnRecord:
    return TurnRecord(
        turn_id=str(row[0]),
        thread_id=str(row[1]),
        tenant_id=str(row[2]),
        subject_user_id=str(row[3]),
        seq=int(row[4]),
        message=str(row[5]),
        disposition=TurnDisposition(str(row[6])),
        reason=str(row[7]) if row[7] is not None else None,
        run_id=str(row[8]) if row[8] is not None else None,
        agent_definition_id=str(row[9]) if row[9] is not None else None,
        context_run_ids=_split(row[10]),
        context_dropped=_split(row[11]),
        created_at=_aware(row[12]),
    )


__all__ = ["PostgresThreadStore"]
