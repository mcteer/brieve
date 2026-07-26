# SPDX-License-Identifier: Apache-2.0
"""Postgres durability provider — the real one.

Backed by a long-lived database, because a checkpoint written to storage that
disappears with the process is not durability, it is a variable with extra steps.

Credentials come from :mod:`core.durability.credentials`; there is no code path here
that accepts a DSN carrying a password. An authentication failure triggers **one**
credential refresh and retry (FR-017b) — see :meth:`_execute` for why the bound
matters.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pg8000.dbapi

from core.durability.credentials import (
    CredentialUnavailableError,
    DatabaseCredential,
    VaultDatabaseCredentials,
)
from core.durability.types import CheckpointBlob, IntentRecord, ResultRecord, RunOutcome
from core.errors import CoreError

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


class DurabilityStoreError(CoreError):
    """The store could not be read or written. Never swallowed — see FR-003's rationale."""


class PostgresDurabilityProvider:
    """Checkpoints, leases, and intent/result records in Postgres."""

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
        conn.autocommit = True
        if self._owner:
            # Every credential is a distinct role, so objects created under one are not
            # owned by the next — migrations then fail with "must be owner of table" the
            # first time a lease rolls over. Acting as the shared parent role keeps a
            # single owner across the whole credential lifecycle.
            _exec(conn, f'SET ROLE "{self._owner}"')
        return conn

    def _execute(self, work: Callable[[Any], Any]) -> Any:
        """Run ``work``, refreshing the credential once on an authentication failure.

        The retry is bounded deliberately, and only on authentication errors. An
        unbounded retry would spin against a genuine misconfiguration — and one is
        reachable in the dev enclave: destroy the Postgres volume and the database
        reverts to its bootstrap password while Vault holds the rotated one, so *every*
        credential fails auth. That must read as a failure, not a hang.
        """
        for attempt in (0, 1):
            conn = None
            try:
                conn = self._open(refresh=attempt == 1)
                return work(conn)
            except CredentialUnavailableError:
                raise
            except Exception as exc:
                if attempt == 0 and _is_auth_failure(exc):
                    continue
                raise DurabilityStoreError(f"durability store error: {exc}") from exc
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:  # noqa: BLE001 - close failures must not mask the real error
                        pass
        raise DurabilityStoreError("durability store unreachable after credential refresh")

    def migrate(self) -> None:
        """Apply the schema. Idempotent — every statement is IF NOT EXISTS."""
        sql = SCHEMA_PATH.read_text()
        self._execute(lambda conn: _exec(conn, sql))

    # ------------------------------------------------------------------ checkpoints

    def save(self, blob: CheckpointBlob) -> None:
        def work(conn: Any) -> None:
            _exec(
                conn,
                """
                INSERT INTO checkpoints
                    (blob_id, payload, correlation_id, grant_id, step_index,
                     written_by, run_state, stop_reason)
                VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (blob_id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    correlation_id = EXCLUDED.correlation_id,
                    grant_id = EXCLUDED.grant_id,
                    step_index = EXCLUDED.step_index,
                    written_by = EXCLUDED.written_by,
                    run_state = EXCLUDED.run_state,
                    stop_reason = EXCLUDED.stop_reason,
                    written_at = now()
                """,
                (
                    blob.blob_id,
                    json.dumps(blob.payload),
                    blob.correlation_id,
                    blob.grant_id,
                    blob.step_index,
                    blob.written_by,
                    blob.outcome.state if blob.outcome else None,
                    blob.outcome.stop_reason if blob.outcome else None,
                ),
            )

        self._execute(work)

    def load(self, blob_id: str) -> CheckpointBlob | None:
        def work(conn: Any) -> CheckpointBlob | None:
            row = _one(
                conn,
                """
                SELECT payload, correlation_id, grant_id, step_index, written_by,
                       run_state, stop_reason
                FROM checkpoints WHERE blob_id = %s
                """,
                (blob_id,),
            )
            if row is None:
                return None
            payload, correlation_id, grant_id, step_index, written_by, state, reason = row
            return CheckpointBlob(
                blob_id=blob_id,
                payload=payload or {},
                correlation_id=correlation_id,
                grant_id=grant_id,
                step_index=step_index,
                written_by=written_by,
                outcome=RunOutcome(state=state, stop_reason=reason) if state else None,
            )

        blob: CheckpointBlob | None = self._execute(work)
        return blob

    # ----------------------------------------------------------------------- lease

    def acquire_lease(self, run_id: str, holder_identity: str) -> None:
        def work(conn: Any) -> None:
            _exec(
                conn,
                """
                INSERT INTO run_leases (run_id, holder_identity)
                VALUES (%s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    holder_identity = EXCLUDED.holder_identity,
                    acquired_at = now()
                """,
                (run_id, holder_identity),
            )

        self._execute(work)

    def check_lease(self, run_id: str, holder_identity: str) -> bool:
        def work(conn: Any) -> bool:
            row = _one(conn, "SELECT holder_identity FROM run_leases WHERE run_id = %s", (run_id,))
            return row is not None and row[0] == holder_identity

        return bool(self._execute(work))

    # --------------------------------------------------------------------- bracket

    def record_intent(self, record: IntentRecord) -> None:
        def work(conn: Any) -> None:
            _exec(
                conn,
                """
                INSERT INTO intents (run_id, idempotency_key, step_index, tool_name, recorded_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_id, idempotency_key) DO NOTHING
                """,
                (
                    record.run_id,
                    record.idempotency_key,
                    record.step_index,
                    record.tool_name,
                    record.recorded_at,
                ),
            )

        self._execute(work)

    def record_result(self, record: ResultRecord) -> None:
        def work(conn: Any) -> None:
            _exec(
                conn,
                """
                INSERT INTO results (run_id, idempotency_key, step_index, recorded_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (run_id, idempotency_key) DO NOTHING
                """,
                (
                    record.run_id,
                    record.idempotency_key,
                    record.step_index,
                    record.recorded_at,
                ),
            )

        self._execute(work)

    def open_intents(self, run_id: str) -> list[IntentRecord]:
        def work(conn: Any) -> list[IntentRecord]:
            rows = _all(
                conn,
                """
                SELECT i.run_id, i.step_index, i.tool_name, i.idempotency_key, i.recorded_at
                FROM intents i
                LEFT JOIN results r
                  ON r.run_id = i.run_id AND r.idempotency_key = i.idempotency_key
                WHERE i.run_id = %s AND r.run_id IS NULL
                ORDER BY i.step_index
                """,
                (run_id,),
            )
            return [
                IntentRecord(
                    run_id=row[0],
                    step_index=row[1],
                    tool_name=row[2],
                    idempotency_key=row[3],
                    recorded_at=row[4],
                )
                for row in rows
            ]

        result = self._execute(work)
        return list(result)


def _run(cursor: Any, sql: str, params: tuple[Any, ...] | None) -> None:
    """pg8000 rejects an explicit ``None`` for parameters, unlike psycopg — it tries to
    take ``len()`` of it. Omit the argument entirely instead."""
    if params is None:
        cursor.execute(sql)
    else:
        cursor.execute(sql, params)


def _exec(conn: Any, sql: str, params: tuple[Any, ...] | None = None) -> None:
    cursor = conn.cursor()
    try:
        _run(cursor, sql, params)
    finally:
        cursor.close()


def _one(conn: Any, sql: str, params: tuple[Any, ...] | None = None) -> Any:
    cursor = conn.cursor()
    try:
        _run(cursor, sql, params)
        return cursor.fetchone()
    finally:
        cursor.close()


def _all(conn: Any, sql: str, params: tuple[Any, ...] | None = None) -> list[Any]:
    cursor = conn.cursor()
    try:
        _run(cursor, sql, params)
        rows: list[Any] = cursor.fetchall()
        return rows
    finally:
        cursor.close()


def _is_auth_failure(exc: Exception) -> bool:
    """SQLSTATE class 28 is authentication.

    Matched on the code rather than the message so a localised or reworded server string
    cannot silently turn a refresh into a hard failure. pg8000 reports the server error
    as a dict in ``args[0]`` keyed by field letter, where ``C`` is the SQLSTATE.
    """
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate is None and exc.args and isinstance(exc.args[0], dict):
        sqlstate = exc.args[0].get("C")
    return bool(sqlstate and str(sqlstate).startswith("28"))
