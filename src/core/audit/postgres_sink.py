# SPDX-License-Identifier: Apache-2.0
"""Durable audit sink — the real one.

**Position, linkage, entry insert, and head update happen in one transaction, under a row
lock.** That is the whole design, and the reason is worth stating where the code is.

The obvious implementation reads the chain, computes the next position, and inserts. It is
also wrong for any stream with more than one writer: two callers read the same last row,
both compute position N, and one loses. Run chains never hit this because 005's
single-writer lease guarantees one writer per correlation ID. The evidence-access stream
has one writer per *reader*, so it hits it immediately.

Splitting the head update from the insert would be the same mistake in a second place —
the head would drift from the chain it describes, and a drifted head is worse than none
because it reports tampering that did not happen.

Credentials come from :mod:`core.durability.credentials`, as the durability provider's do.
No code path here accepts a DSN carrying a password.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pg8000.dbapi

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash
from core.audit.schema import AuditEntry, AuditEventType
from core.durability.credentials import (
    DatabaseCredential,
    VaultDatabaseCredentials,
)
from core.errors import CoreError

EVIDENCE_SCHEMA_PATH = Path(__file__).with_name("evidence_schema.sql")


class AuditStoreError(CoreError):
    """The evidence store could not be read or written. Never swallowed."""


class PostgresAuditSink:
    """Append-only, hash-chained audit entries in Postgres."""

    def __init__(
        self,
        *,
        credentials: VaultDatabaseCredentials,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "brieve",
        owner_role: str | None = "brieve",
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self._credentials = credentials
        self._host = host
        self._port = port
        self._dbname = dbname
        self._owner = owner_role
        self._connect = connect or pg8000.dbapi.connect
        self._credential: DatabaseCredential | None = None

    # ------------------------------------------------------------------ connection

    def _open(self, *, refresh: bool) -> Any:
        if refresh or self._credential is None:
            self._credential = self._credentials.fetch()
        cred = self._credential
        conn = self._connect(
            host=self._host,
            port=self._port,
            database=self._dbname,
            user=cred.username,
            password=cred.password,
        )
        if self._owner:
            # The same trap 005 paid for, in a second place. Every dynamic credential is a
            # distinct role, so a table created under one is not owned by the next and DDL
            # fails with "must be owner of table" the first time a lease rolls over —
            # including `CREATE INDEX IF NOT EXISTS`, which checks ownership before it
            # checks existence. Acting as the shared parent role keeps one owner across the
            # whole credential lifecycle.
            cur = conn.cursor()
            cur.execute(f'SET ROLE "{self._owner}"')
            conn.commit()
        return conn

    def _with_connection(self, fn: Callable[[Any], Any]) -> Any:
        """Run ``fn`` against a connection, refreshing credentials once on auth failure.

        Once, not repeatedly: an unbounded retry spins against a genuine misconfiguration,
        and the database's rejection is the signal rather than a clock.
        """
        try:
            conn = self._open(refresh=False)
        except Exception:
            conn = self._open(refresh=True)
        try:
            return fn(conn)
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            if _is_auth_failure(exc):
                conn2 = self._open(refresh=True)
                try:
                    return fn(conn2)
                finally:
                    _close(conn2)
            raise AuditStoreError(f"audit store operation failed: {exc}") from exc
        finally:
            _close(conn)

    def migrate(self) -> None:
        """Apply the evidence schema. Idempotent."""
        sql = EVIDENCE_SCHEMA_PATH.read_text()

        def _run(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()

        self._with_connection(_run)

    # ------------------------------------------------------------------ write seam

    def append_event(
        self,
        *,
        correlation_id: str,
        tenant_id: str,
        event_type: AuditEventType,
        payload: dict[str, Any],
        timestamp: datetime | None = None,
    ) -> AuditEntry:
        ts = timestamp if timestamp is not None else datetime.now(UTC)

        def _run(conn: Any) -> AuditEntry:
            cur = conn.cursor()
            # Seed the head before locking it, because **`FOR UPDATE` on a row that does
            # not exist locks nothing.** The lock below serialises appends to a stream that
            # already has one — but the FIRST append to a stream had no row to take, so two
            # writers starting a stream together both read nothing, both computed seq 0,
            # and one lost on the primary key.
            #
            # It is a narrow window and it stayed hidden accordingly: the row that drives
            # concurrent writers passed locally many times and in CI, and only failed once
            # a persistent service was sharing the machine. A race that reproduces under
            # load and not otherwise is the kind that reaches production.
            #
            # `ON CONFLICT DO NOTHING` is what makes this safe rather than a second race.
            # Postgres blocks the losing inserter until the winner commits or aborts, so by
            # the time either reaches the `SELECT ... FOR UPDATE` there is exactly one row
            # to lock and they take it in turn.
            #
            # The sentinel is `-1` with the genesis hash, so the read below needs no
            # special case: seq becomes 0 and prev_hash the genesis, by the same
            # arithmetic every later append uses. A branch here would be a second place for
            # the first entry's shape to be decided.
            cur.execute(
                "INSERT INTO audit_stream_heads (correlation_id, highest_seq, head_hash) "
                "VALUES (%s, -1, %s) ON CONFLICT (correlation_id) DO NOTHING",
                (correlation_id, GENESIS_PREV_HASH),
            )
            # The row lock is what makes this safe for a stream with many writers. Taking
            # the head row FOR UPDATE serialises concurrent appends to the same stream;
            # readers of other streams are unaffected.
            cur.execute(
                "SELECT highest_seq, head_hash FROM audit_stream_heads "
                "WHERE correlation_id = %s FOR UPDATE",
                (correlation_id,),
            )
            row = cur.fetchone()
            # Never None now — the seed above guarantees a row — but a sink that crashed
            # here would be reporting the wrong thing entirely.
            if row is None:  # pragma: no cover — defensive; the seed makes it unreachable
                raise RuntimeError(f"stream head vanished between seed and lock: {correlation_id}")
            seq = int(row[0]) + 1
            prev_hash = str(row[1])

            entry_hash = compute_entry_hash(
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                seq=seq,
                event_type=str(event_type),
                timestamp=ts,
                payload=payload,
                prev_hash=prev_hash,
            )
            cur.execute(
                "INSERT INTO audit_entries "
                "(tenant_id, correlation_id, seq, event_type, timestamp, payload, "
                " prev_hash, entry_hash) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    tenant_id,
                    correlation_id,
                    seq,
                    str(event_type),
                    ts,
                    json.dumps(payload, sort_keys=True),
                    prev_hash,
                    entry_hash,
                ),
            )
            # Same transaction as the insert. A head written separately can drift from the
            # chain it describes, and a drifted head reports tampering that never happened.
            cur.execute(
                "INSERT INTO audit_stream_heads (correlation_id, highest_seq, head_hash) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (correlation_id) DO UPDATE "
                "SET highest_seq = EXCLUDED.highest_seq, "
                "    head_hash = EXCLUDED.head_hash, "
                "    updated_at = now()",
                (correlation_id, seq, entry_hash),
            )
            conn.commit()
            return AuditEntry(
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                seq=seq,
                event_type=event_type,
                timestamp=ts,
                payload=payload,
                prev_hash=prev_hash,
                entry_hash=entry_hash,
            )

        result = self._with_connection(_run)
        assert isinstance(result, AuditEntry)
        return result

    # ------------------------------------------------------------------ reads

    def list_by_correlation_id(self, correlation_id: str) -> list[AuditEntry]:
        def _run(conn: Any) -> list[AuditEntry]:
            cur = conn.cursor()
            cur.execute(
                "SELECT tenant_id, correlation_id, seq, event_type, timestamp, payload, "
                "       prev_hash, entry_hash "
                "FROM audit_entries WHERE correlation_id = %s ORDER BY seq",
                (correlation_id,),
            )
            return [_row_to_entry(r) for r in cur.fetchall()]

        result = self._with_connection(_run)
        assert isinstance(result, list)
        return result


def _row_to_entry(row: Any) -> AuditEntry:
    payload = row[5]
    if isinstance(payload, str):
        payload = json.loads(payload)
    ts = row[4]
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return AuditEntry(
        tenant_id=row[0],
        correlation_id=row[1],
        seq=int(row[2]),
        event_type=AuditEventType(row[3]),
        timestamp=ts,
        payload=payload,
        prev_hash=row[6],
        entry_hash=row[7],
    )


def _is_auth_failure(exc: Exception) -> bool:
    """SQLSTATE 28xxx — invalid authorization. pg8000 carries it in args[0]['C']."""
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], dict):
        code = args[0].get("C", "")
        return isinstance(code, str) and code.startswith("28")
    return False


def _close(conn: Any) -> None:
    try:
        conn.close()
    except Exception:
        pass


__all__ = ["AuditStoreError", "EVIDENCE_SCHEMA_PATH", "PostgresAuditSink"]
