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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pg8000.dbapi

from core.authority.grant import DelegationGrant
from core.authority.types import AuthorityScope
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
                     written_by, run_state, stop_reason, resume_count)
                VALUES (%s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (blob_id) DO UPDATE SET
                    payload = EXCLUDED.payload,
                    correlation_id = EXCLUDED.correlation_id,
                    grant_id = EXCLUDED.grant_id,
                    step_index = EXCLUDED.step_index,
                    written_by = EXCLUDED.written_by,
                    -- MONOTONIC, on the same reasoning as the terminal-once guard below.
                    --
                    -- The revival count is a safety bound, and `save()` overwrites the
                    -- whole row — so a per-step checkpoint constructed without the count
                    -- would reset it to zero, making the cap a bound that clears itself
                    -- whenever any work happens and a flapping run immortal. The resumed
                    -- run's caller threads the count into every blob it writes, and a row
                    -- asserts that; this makes forgetting structurally survivable rather
                    -- than merely tested, which is what Principle III asks of a bound.
                    --
                    -- Nothing legitimately lowers it: a run's revival count only ever
                    -- rises, and a superseded zombie holding a stale lower count must not
                    -- be able to hand the successor a fresh budget. Same blob-ids-are-not-
                    -- reused assumption the terminal-once guard already rests on.
                    resume_count = GREATEST(checkpoints.resume_count, EXCLUDED.resume_count),
                    -- TERMINAL-ONCE. A terminal state, once written, is never cleared and
                    -- never replaced; the FIRST terminal write wins.
                    --
                    -- This used to be `run_state = EXCLUDED.run_state`, unconditional,
                    -- which reads as obviously correct and passed every durability row
                    -- for three features. It is not: a mid-flight checkpoint carries no
                    -- outcome, so the running allocation's next ROUTINE save wrote NULL
                    -- over a terminal state — silently resurrecting a stopped run, whose
                    -- stop then held only until the run next checkpointed.
                    --
                    -- Nothing legitimate overwrites a terminal state: resume refuses
                    -- terminal runs, and suspension carries a non-terminal state. So the
                    -- guard forbids exactly the write that was always a defect.
                    --
                    -- It assumes blob ids are not reused across runs, which dispatch
                    -- guarantees by minting fresh ones — a fresh run under a stopped
                    -- blob id could never record its own completion.
                    run_state = COALESCE(checkpoints.run_state, EXCLUDED.run_state),
                    stop_reason = COALESCE(checkpoints.stop_reason, EXCLUDED.stop_reason),
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
                    blob.resume_count,
                ),
            )

        self._execute(work)

    def load(self, blob_id: str) -> CheckpointBlob | None:
        def work(conn: Any) -> CheckpointBlob | None:
            row = _one(
                conn,
                """
                SELECT payload, correlation_id, grant_id, step_index, written_by,
                       run_state, stop_reason, resume_count
                FROM checkpoints WHERE blob_id = %s
                """,
                (blob_id,),
            )
            if row is None:
                return None
            payload, correlation_id, grant_id, step_index, written_by, state, reason, resumes = row
            return CheckpointBlob(
                blob_id=blob_id,
                payload=payload or {},
                correlation_id=correlation_id,
                grant_id=grant_id,
                step_index=step_index,
                written_by=written_by,
                outcome=RunOutcome(state=state, stop_reason=reason) if state else None,
                resume_count=resumes,
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
                INSERT INTO intents
                    (run_id, idempotency_key, step_index, tool_name, arguments, recorded_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id, idempotency_key) DO NOTHING
                """,
                (
                    record.run_id,
                    record.idempotency_key,
                    record.step_index,
                    record.tool_name,
                    # NULL when the record carries none, which is what a pre-040 intent
                    # reads back as — and `{}` serialises to "{}", never to NULL, so the
                    # two stay distinguishable through a round trip (040, research R4).
                    None if record.arguments is None else json.dumps(record.arguments),
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

    def scrub_closed_arguments(self, run_id: str) -> int:
        """Clear arguments on this run's closed brackets. See the protocol for why closed only.

        **The Postgres leg is the one that counts.** The in-memory provider round-trips a
        cleared field for free, so a scrub proven only against it would pass whether or not
        this SQL was ever written — which is 040's M7 shape, one column over.
        """

        def work(conn: Any) -> int:
            # `_exec` discards the cursor, and this is the one caller that needs its
            # rowcount — the count is what a row asserts, because "scrubbed nothing" and
            # "scrubbed everything" are otherwise the same silent success.
            cursor = conn.cursor()
            try:
                _run(
                    cursor,
                    """
                    UPDATE intents SET arguments = NULL
                     WHERE run_id = %s
                       AND arguments IS NOT NULL
                       AND idempotency_key IN (
                           SELECT idempotency_key FROM results WHERE run_id = %s
                       )
                    """,
                    (run_id, run_id),
                )
                return int(getattr(cursor, "rowcount", 0) or 0)
            finally:
                cursor.close()

        return int(self._execute(work))

    def open_intents(self, run_id: str) -> list[IntentRecord]:
        def work(conn: Any) -> list[IntentRecord]:
            rows = _all(
                conn,
                """
                SELECT i.run_id, i.step_index, i.tool_name, i.idempotency_key,
                       i.arguments, i.recorded_at
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
                    # NULL stays None — "recorded before this column existed", which the
                    # revival path reads as "run with the pre-040 constant" (research R4).
                    arguments=None if row[4] is None else json.loads(row[4]),
                    recorded_at=row[5],
                )
                for row in rows
            ]

        result = self._execute(work)
        return list(result)

    def closed_intents(self, run_id: str) -> list[IntentRecord]:
        """The same walk as `open_intents`, with the join condition inverted."""

        def work(conn: Any) -> list[IntentRecord]:
            rows = _all(
                conn,
                """
                SELECT i.run_id, i.step_index, i.tool_name, i.idempotency_key,
                       i.arguments, i.recorded_at
                FROM intents i
                JOIN results r
                  ON r.run_id = i.run_id AND r.idempotency_key = i.idempotency_key
                WHERE i.run_id = %s
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
                    # NULL stays None — "recorded before this column existed", which the
                    # revival path reads as "run with the pre-040 constant" (research R4).
                    arguments=None if row[4] is None else json.loads(row[4]),
                    recorded_at=row[5],
                )
                for row in rows
            ]

        result = self._execute(work)
        return list(result)

    # ---------------------------------------------------------------------- consent

    def save_grant(self, grant: DelegationGrant) -> None:
        """Persist consent once. A second save of the same grant changes nothing."""

        def work(conn: Any) -> None:
            _exec(
                conn,
                """
                INSERT INTO grants
                    (grant_id, subject_user_id, agent_definition_id, requested_scope,
                     issued_at, expires_at)
                VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                -- DO NOTHING, not DO UPDATE. A grant's terms do not change; a new consent
                -- is a new grant with a new id. An update path here would make consent
                -- mutable after the fact, which is the one thing an audit trail cannot
                -- tolerate about it — the run would have executed under terms the record
                -- no longer shows.
                ON CONFLICT (grant_id) DO NOTHING
                """,
                (
                    grant.grant_id,
                    grant.subject_user_id,
                    grant.agent_definition_id,
                    json.dumps(_scope_to_json(grant.requested_scope)),
                    grant.issued_at,
                    grant.expires_at,
                ),
            )

        self._execute(work)

    def load_grant(self, grant_id: str) -> DelegationGrant | None:
        def work(conn: Any) -> DelegationGrant | None:
            row = _one(
                conn,
                """
                SELECT subject_user_id, agent_definition_id, requested_scope,
                       issued_at, expires_at
                FROM grants WHERE grant_id = %s
                """,
                (grant_id,),
            )
            if row is None:
                return None
            subject, definition, scope, issued_at, expires_at = row
            return DelegationGrant(
                grant_id=grant_id,
                subject_user_id=subject,
                agent_definition_id=definition,
                requested_scope=_scope_from_json(scope or {}),
                issued_at=_as_utc(issued_at),
                expires_at=_as_utc(expires_at),
            )

        grant: DelegationGrant | None = self._execute(work)
        return grant


def _scope_to_json(scope: AuthorityScope) -> dict[str, list[str]]:
    """Serialize a scope **deterministically**, which is a decision rather than a detail.

    ``AuthorityScope`` holds frozensets, and a frozenset has no order — so writing one
    straight to jsonb produces whichever order the set happened to iterate in, and two
    saves of one unchanged grant differ byte for byte. That breaks nothing today and
    breaks two things later: the no-secret sweep reads these bytes and would have no
    stable value to compare, and anyone diffing consent records would see churn that
    means nothing. Sorted lists in, frozensets out, once, here.
    """
    return {
        "tool_names": sorted(scope.tool_names),
        "product_actions": sorted(scope.product_actions),
    }


def _scope_from_json(raw: Any) -> AuthorityScope:
    data = raw if isinstance(raw, dict) else {}
    return AuthorityScope(
        tool_names=frozenset(data.get("tool_names") or ()),
        product_actions=frozenset(data.get("product_actions") or ()),
    )


def _as_utc(value: datetime) -> datetime:
    """Guarantee an aware datetime coming out of the store.

    The columns are ``TIMESTAMPTZ`` and the driver returns aware values, so this is
    normally a no-op. It exists because of what the alternative costs: ``assert_live``
    compares this against ``clock.now()``, and comparing a naive datetime to an aware one
    raises ``TypeError``. That would surface as a crashed resume rather than as lapsed
    consent — the one failure mode US4 exists to make orderly — and it would surface only
    against the real store, where the trail is hardest to read.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


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
