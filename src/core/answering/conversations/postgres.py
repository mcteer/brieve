# SPDX-License-Identifier: Apache-2.0
"""Ask conversations in the enclave database.

Mirrors `core.threads.postgres` in discipline — brokered credential per connection, one
`_run` wrapper that turns any driver failure into one named error, idempotent migrate — and
shares no code, table or vocabulary with it (ADR-0039; see `schema.sql`).

**`seq` is assigned under the conversation's row lock**, the same first-writer-wins rule
`thread_turns` uses. Two tabs asking at once must not compute the same next value: without
the lock both readers see the same MAX and both write it, and the transcript grows an
ambiguity nobody can resolve afterwards.
"""

from __future__ import annotations

import json
import pathlib
from datetime import UTC, datetime
from typing import Any

from core.answering.conversations.records import (
    ConversationRecord,
    ExchangeDisposition,
    ExchangeRecord,
    title_from,
)

SCHEMA_PATH = pathlib.Path(__file__).with_name("schema.sql")


class ConversationStoreError(RuntimeError):
    """The store could not be reached or read.

    Raised rather than returning empty: a surface that cannot read a person's conversations
    must say so, because an empty list is a claim that they have none.
    """


def _aware(stamp: Any) -> datetime:
    """Postgres timestamps come back naive under some drivers; the record wants UTC."""
    if isinstance(stamp, datetime):
        return stamp if stamp.tzinfo else stamp.replace(tzinfo=UTC)
    return datetime.now(UTC)


def _outcome(value: Any) -> dict[str, Any]:
    """`jsonb` arrives as a dict on some drivers and a string on others."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        loaded = json.loads(value)
        return loaded if isinstance(loaded, dict) else {}
    return {}


class PostgresConversationStore:
    """Ask conversations and their exchanges."""

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
        except ConversationStoreError:
            raise
        except Exception as exc:
            raise ConversationStoreError(
                f"conversation store unavailable: {type(exc).__name__}: {exc}"
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

    def start(
        self,
        *,
        conversation_id: str,
        tenant_id: str,
        subject_user_id: str,
        question: str,
        source: str,
        disposition: ExchangeDisposition,
        outcome: dict[str, Any],
    ) -> tuple[ConversationRecord, ExchangeRecord]:
        now = datetime.now(UTC)
        title = title_from(question)

        def work(conn: Any) -> tuple[ConversationRecord, ExchangeRecord]:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO ask_conversations (conversation_id, tenant_id, subject_user_id, "
                "title, created_at, last_asked_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (conversation_id, tenant_id, subject_user_id, title, now, now),
            )
            cur.execute(
                "INSERT INTO ask_exchanges (conversation_id, seq, question, source, "
                "disposition, outcome, asked_at) VALUES (%s, 1, %s, %s, %s, %s, %s)",
                (conversation_id, question, source, str(disposition), json.dumps(outcome), now),
            )
            conn.commit()
            return (
                ConversationRecord(
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    subject_user_id=subject_user_id,
                    title=title,
                    created_at=now,
                    last_asked_at=now,
                    exchanges=1,
                ),
                ExchangeRecord(
                    conversation_id=conversation_id,
                    seq=1,
                    question=question,
                    source=source,
                    disposition=disposition,
                    outcome=outcome,
                    asked_at=now,
                ),
            )

        result: tuple[ConversationRecord, ExchangeRecord] = self._run(work)
        return result

    def append(
        self,
        *,
        conversation_id: str,
        tenant_id: str,
        subject_user_id: str,
        question: str,
        source: str,
        disposition: ExchangeDisposition,
        outcome: dict[str, Any],
    ) -> ExchangeRecord | None:
        now = datetime.now(UTC)

        def work(conn: Any) -> ExchangeRecord | None:
            cur = conn.cursor()
            # Owner and tenant are part of the lock predicate, so a conversation belonging to
            # somebody else is not locked, not read, and not appended to — one query, no
            # window between checking and writing.
            cur.execute(
                "SELECT 1 FROM ask_conversations WHERE conversation_id = %s AND tenant_id = %s "
                "AND subject_user_id = %s FOR UPDATE",
                (conversation_id, tenant_id, subject_user_id),
            )
            if cur.fetchone() is None:
                conn.rollback()
                return None
            cur.execute(
                "SELECT COALESCE(MAX(seq) + 1, 1) FROM ask_exchanges WHERE conversation_id = %s",
                (conversation_id,),
            )
            row = cur.fetchone()
            seq = int(row[0]) if row else 1
            cur.execute(
                "INSERT INTO ask_exchanges (conversation_id, seq, question, source, "
                "disposition, outcome, asked_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    conversation_id,
                    seq,
                    question,
                    source,
                    str(disposition),
                    json.dumps(outcome),
                    now,
                ),
            )
            cur.execute(
                "UPDATE ask_conversations SET last_asked_at = %s WHERE conversation_id = %s",
                (now, conversation_id),
            )
            conn.commit()
            return ExchangeRecord(
                conversation_id=conversation_id,
                seq=seq,
                question=question,
                source=source,
                disposition=disposition,
                outcome=outcome,
                asked_at=now,
            )

        appended: ExchangeRecord | None = self._run(work)
        return appended

    def get(
        self, *, conversation_id: str, tenant_id: str, subject_user_id: str
    ) -> tuple[ConversationRecord, tuple[ExchangeRecord, ...]] | None:
        def work(conn: Any) -> tuple[ConversationRecord, tuple[ExchangeRecord, ...]] | None:
            cur = conn.cursor()
            cur.execute(
                "SELECT title, created_at, last_asked_at FROM ask_conversations "
                "WHERE conversation_id = %s AND tenant_id = %s AND subject_user_id = %s",
                (conversation_id, tenant_id, subject_user_id),
            )
            row = cur.fetchone()
            if row is None:
                return None
            cur.execute(
                "SELECT seq, question, source, disposition, outcome, asked_at "
                "FROM ask_exchanges WHERE conversation_id = %s ORDER BY seq",
                (conversation_id,),
            )
            exchanges = tuple(
                ExchangeRecord(
                    conversation_id=conversation_id,
                    seq=int(e[0]),
                    question=e[1],
                    source=e[2],
                    disposition=ExchangeDisposition(e[3]),
                    outcome=_outcome(e[4]),
                    asked_at=_aware(e[5]),
                )
                for e in cur.fetchall()
            )
            return (
                ConversationRecord(
                    conversation_id=conversation_id,
                    tenant_id=tenant_id,
                    subject_user_id=subject_user_id,
                    title=row[0],
                    created_at=_aware(row[1]),
                    last_asked_at=_aware(row[2]),
                    exchanges=len(exchanges),
                ),
                exchanges,
            )

        found: tuple[ConversationRecord, tuple[ExchangeRecord, ...]] | None = self._run(work)
        return found

    def recent(
        self, *, conversation_id: str, tenant_id: str, subject_user_id: str, limit: int
    ) -> tuple[ExchangeRecord, ...]:
        if limit <= 0:
            return ()

        def work(conn: Any) -> tuple[ExchangeRecord, ...]:
            cur = conn.cursor()
            # Ownership is in the join predicate: a conversation that is not this subject's
            # yields no rows, so context can never be built from somebody else's exchanges
            # (FR-019) without a separate check that could be forgotten.
            cur.execute(
                "SELECT e.seq, e.question, e.source, e.disposition, e.outcome, e.asked_at "
                "FROM ask_exchanges e JOIN ask_conversations c "
                "ON c.conversation_id = e.conversation_id "
                "WHERE e.conversation_id = %s AND c.tenant_id = %s AND c.subject_user_id = %s "
                "ORDER BY e.seq DESC LIMIT %s",
                (conversation_id, tenant_id, subject_user_id, limit),
            )
            rows = cur.fetchall()
            return tuple(
                ExchangeRecord(
                    conversation_id=conversation_id,
                    seq=int(r[0]),
                    question=r[1],
                    source=r[2],
                    disposition=ExchangeDisposition(r[3]),
                    outcome=_outcome(r[4]),
                    asked_at=_aware(r[5]),
                )
                for r in reversed(rows)  # newest-first from SQL, oldest-first to the caller
            )

        recent: tuple[ExchangeRecord, ...] = self._run(work)
        return recent

    def list_for(self, *, tenant_id: str, subject_user_id: str) -> tuple[ConversationRecord, ...]:
        def work(conn: Any) -> tuple[ConversationRecord, ...]:
            cur = conn.cursor()
            cur.execute(
                "SELECT c.conversation_id, c.title, c.created_at, c.last_asked_at, "
                "COUNT(e.seq) FROM ask_conversations c "
                "LEFT JOIN ask_exchanges e ON e.conversation_id = c.conversation_id "
                "WHERE c.tenant_id = %s AND c.subject_user_id = %s "
                "GROUP BY c.conversation_id, c.title, c.created_at, c.last_asked_at "
                "ORDER BY c.last_asked_at DESC, c.conversation_id DESC",
                (tenant_id, subject_user_id),
            )
            return tuple(
                ConversationRecord(
                    conversation_id=r[0],
                    tenant_id=tenant_id,
                    subject_user_id=subject_user_id,
                    title=r[1],
                    created_at=_aware(r[2]),
                    last_asked_at=_aware(r[3]),
                    exchanges=int(r[4]),
                )
                for r in cur.fetchall()
            )

        listed: tuple[ConversationRecord, ...] = self._run(work)
        return listed

    def delete(self, *, conversation_id: str, tenant_id: str, subject_user_id: str) -> bool:
        def work(conn: Any) -> bool:
            cur = conn.cursor()
            # Exchanges go with it by cascade. NOTHING here touches `audit_entries` — the
            # trail is a different plane and this store holds no reference to it (FR-023).
            cur.execute(
                "DELETE FROM ask_conversations WHERE conversation_id = %s AND tenant_id = %s "
                "AND subject_user_id = %s",
                (conversation_id, tenant_id, subject_user_id),
            )
            deleted = bool(cur.rowcount and cur.rowcount > 0)
            conn.commit()
            return deleted

        removed: bool = self._run(work)
        return removed


__all__ = ["ConversationStoreError", "PostgresConversationStore"]
