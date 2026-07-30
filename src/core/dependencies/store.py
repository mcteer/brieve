# SPDX-License-Identifier: Apache-2.0
"""Dependency health in Postgres, and the suspension index beside it.

**Persisted, never in memory.** A restart must not silently mean "everything is reachable
again". In-memory health starts empty, and empty resolves to `UNKNOWN`, which is treated
as unhealthy — so it would technically fail closed, which sounds fine until the service
restarts during an incident and every run suspends at once. A persisted record degrades
honestly instead: it says when it was last checked, and a stale record reads as unknown
rather than as either extreme.

Credentials come from :mod:`core.durability.credentials`, as everything else's do. No code
path here accepts a DSN carrying a password.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pg8000.dbapi

from core.dependencies.types import DependencyHealth, HealthState
from core.durability.credentials import DatabaseCredential, VaultDatabaseCredentials
from core.durability.sweeper import SuspendedRunRecord
from core.errors import CoreError

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

#: How long a health record is worth trusting. Past this it reads as UNKNOWN, which is
#: treated as unhealthy — a checker that stopped running must not leave the platform
#: believing everything was fine at the moment it died.
DEFAULT_STALE_AFTER = timedelta(minutes=5)

#: Consecutive successes before a product is called healthy again. Recovery is hysteretic
#: and failure is not: one failure is enough to stop calling a product, because the cost
#: is a suspension the sweeper resolves. Restoring too eagerly resumes every waiting run
#: into a product that fails again, and each cycle spends real budget against the run's
#: maximum duration.
DEFAULT_RECOVERY_THRESHOLD = 3


class DependencyStoreError(CoreError):
    """The dependency store could not be read or written. Never swallowed."""


class PostgresDependencyStore:
    """Health records and the suspension index.

    Implements :class:`~core.dependencies.types.DependencyHealthReader` by having a
    ``state_of``, and nothing a run holds can reach the writing methods — a run gets this
    object typed as the reader protocol, which names none of them.
    """

    def __init__(
        self,
        *,
        credentials: VaultDatabaseCredentials,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "brieve",
        owner_role: str | None = "brieve",
        stale_after: timedelta = DEFAULT_STALE_AFTER,
        recovery_threshold: int = DEFAULT_RECOVERY_THRESHOLD,
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self._credentials = credentials
        self._host = host
        self._port = port
        self._dbname = dbname
        self._owner = owner_role
        self._stale_after = stale_after
        self._recovery_threshold = recovery_threshold
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
            # Every dynamic credential is a distinct role, so a table created under one is
            # owned by an ephemeral user and the next credential fails DDL — including on
            # `CREATE INDEX IF NOT EXISTS`, which checks ownership before existence. 005
            # paid for this once; it is reachable from every new store.
            cur = conn.cursor()
            cur.execute(f'SET ROLE "{self._owner}"')
            conn.commit()
        return conn

    def _run(self, fn: Callable[[Any], Any]) -> Any:
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
            raise DependencyStoreError(f"dependency store operation failed: {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def migrate(self) -> None:
        """Apply the schema. Idempotent."""
        sql = SCHEMA_PATH.read_text()

        def _apply(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(sql)
            conn.commit()

        self._run(_apply)

    # ------------------------------------------------------------------ reading

    def state_of(self, product: str, *, now: datetime | None = None) -> HealthState:
        """What the platform believes, with staleness folded in.

        The reader half of the protocol, and the only thing a run ever calls.
        """
        record = self.health_of(product, now=now)
        return record.state if record is not None else HealthState.UNKNOWN

    def health_of(self, product: str, *, now: datetime | None = None) -> DependencyHealth | None:
        moment = now or datetime.now(UTC)

        def _read(conn: Any) -> DependencyHealth | None:
            cur = conn.cursor()
            cur.execute(
                "SELECT product, state, checked_at, consecutive_successes, detail "
                "FROM dependency_health WHERE product = %s",
                (product,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            checked_at = row[2]
            if checked_at.tzinfo is None:
                checked_at = checked_at.replace(tzinfo=UTC)
            state = HealthState(row[1])
            if moment - checked_at > self._stale_after:
                # Not "still healthy because nobody said otherwise". A checker that
                # stopped running must not leave the platform confident.
                state = HealthState.UNKNOWN
            return DependencyHealth(
                product=row[0],
                state=state,
                checked_at=checked_at,
                consecutive_successes=int(row[3]),
                detail=row[4],
            )

        result = self._run(_read)
        assert result is None or isinstance(result, DependencyHealth)
        return result

    # ------------------------------------------------------------------ writing

    def record_probe(
        self,
        *,
        product: str,
        reachable: bool,
        detail: str = "",
        now: datetime | None = None,
    ) -> DependencyHealth:
        """Record one probe result, applying recovery hysteresis.

        The asymmetry lives here rather than in the checker, so every caller gets it: one
        failure is enough to mark unhealthy; healthy requires consecutive successes.
        """
        moment = now or datetime.now(UTC)

        def _write(conn: Any) -> DependencyHealth:
            cur = conn.cursor()
            cur.execute(
                "SELECT consecutive_successes FROM dependency_health WHERE product = %s FOR UPDATE",
                (product,),
            )
            row = cur.fetchone()
            previous = int(row[0]) if row is not None else 0

            if not reachable:
                successes = 0
                state = HealthState.UNHEALTHY
            else:
                successes = previous + 1
                state = (
                    HealthState.HEALTHY
                    if successes >= self._recovery_threshold
                    else HealthState.UNHEALTHY
                )

            cur.execute(
                "INSERT INTO dependency_health "
                "(product, state, checked_at, consecutive_successes, detail) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (product) DO UPDATE SET "
                "  state = EXCLUDED.state, checked_at = EXCLUDED.checked_at, "
                "  consecutive_successes = EXCLUDED.consecutive_successes, "
                "  detail = EXCLUDED.detail",
                (product, str(state), moment, successes, detail),
            )
            conn.commit()
            return DependencyHealth(
                product=product,
                state=state,
                checked_at=moment,
                consecutive_successes=successes,
                detail=detail,
            )

        result = self._run(_write)
        assert isinstance(result, DependencyHealth)
        return result

    # ------------------------------------------------------------- suspension index

    def record_suspension(
        self,
        *,
        run_id: str,
        correlation_id: str,
        awaiting: str,
        step_index: int,
        subject_user_id: str = "",
        tenant_id: str = "",
        agent_definition_id: str = "",
        subject_roles: frozenset[str] | None = None,
        packs: frozenset[str] | None = None,
        steps: int | None = None,
        invoke_tools: bool = False,
        now: datetime | None = None,
    ) -> None:
        """Index a suspended run so the sweeper can find it.

        **An index over the checkpoint, not a second record of state.** The checkpoint's
        `run_state` is authoritative and says SUSPENDED too; this exists so the sweeper's
        question — "what is waiting on this product" — is an indexed lookup rather than a
        scan of every run. The sweeper re-reads the checkpoint before acting on anything
        it finds here.

        The roles, packs, steps, and invoke flag are what the run needs to be **itself**
        again rather than a fresh run under its identity (014, T010a). All four are
        claims-derived metadata or configuration and none of them grants anything — see
        `SuspendedRunRecord` for the four distinct ways a resume fails without them.

        **This method had zero callers until 014** — in `src/` and in `tests/` alike. The
        index was a store with a reader and no writer, which is `resume_run`'s own defect
        one layer earlier in the lifecycle: the sweeper swept an index nothing filled, so
        every property downstream of it was structurally unreachable while looking wired.
        """
        moment = now or datetime.now(UTC)

        def _write(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO suspended_runs "
                "(run_id, correlation_id, awaiting, suspended_at, step_index, "
                " subject_user_id, tenant_id, agent_definition_id, "
                " subject_roles, packs, steps, invoke_tools) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (run_id) DO UPDATE SET "
                "  correlation_id = EXCLUDED.correlation_id, awaiting = EXCLUDED.awaiting, "
                "  suspended_at = EXCLUDED.suspended_at, step_index = EXCLUDED.step_index, "
                "  subject_user_id = EXCLUDED.subject_user_id, "
                "  tenant_id = EXCLUDED.tenant_id, "
                "  agent_definition_id = EXCLUDED.agent_definition_id, "
                "  subject_roles = EXCLUDED.subject_roles, "
                "  packs = EXCLUDED.packs, "
                "  steps = EXCLUDED.steps, "
                "  invoke_tools = EXCLUDED.invoke_tools",
                (
                    run_id,
                    correlation_id,
                    awaiting,
                    moment,
                    step_index,
                    subject_user_id,
                    tenant_id,
                    agent_definition_id,
                    # Sorted, so a re-suspension of an unchanged run writes identical bytes
                    # — the same reasoning as the grant store's scope serialization.
                    ",".join(sorted(subject_roles or ())),
                    ",".join(sorted(packs or ())),
                    steps,
                    invoke_tools,
                ),
            )
            conn.commit()

        self._run(_write)

    def awaited_products(self) -> list[str]:
        """The distinct products something is currently suspended on.

        What the sweeper iterates. Deriving it from the **index** rather than from the
        registry is deliberate: a run can be suspended on a product whose tools have since
        been deregistered, and that run still has to come back. Sweeping the registry
        instead would strand it silently — the one outcome ADR-0049 removed a human to
        avoid, arrived at by a different route.

        It is also the cheap direction. An estate with nothing suspended returns an empty
        list and the sweep costs one query, rather than a health lookup per registered
        product every interval forever.
        """

        def _read(conn: Any) -> list[str]:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT awaiting FROM suspended_runs")
            return [str(r[0]) for r in cur.fetchall()]

        result = self._run(_read)
        assert isinstance(result, list)
        return result

    def awaiting(self, product: str) -> list[SuspendedRunRecord]:
        def _read(conn: Any) -> list[SuspendedRunRecord]:
            cur = conn.cursor()
            cur.execute(
                "SELECT run_id, correlation_id, awaiting, suspended_at, step_index, "
                "       subject_user_id, tenant_id, agent_definition_id, "
                "       subject_roles, packs, steps, invoke_tools "
                "FROM suspended_runs WHERE awaiting = %s ORDER BY suspended_at",
                (product,),
            )
            rows = cur.fetchall()
            return [
                SuspendedRunRecord(
                    run_id=str(r[0]),
                    correlation_id=str(r[1]),
                    awaiting=str(r[2]),
                    suspended_at=r[3] if r[3].tzinfo else r[3].replace(tzinfo=UTC),
                    step_index=int(r[4]),
                    subject_user_id=str(r[5]),
                    tenant_id=str(r[6]),
                    agent_definition_id=str(r[7]),
                    subject_roles=_split(r[8]),
                    packs=_split(r[9]),
                    steps=int(r[10]) if r[10] is not None else None,
                    invoke_tools=bool(r[11]),
                )
                for r in rows
            ]

        result = self._run(_read)
        assert isinstance(result, list)
        return result

    def forget(self, run_id: str) -> None:
        """Drop a run from the index — resumed, or found terminal."""

        def _write(conn: Any) -> None:
            cur = conn.cursor()
            cur.execute("DELETE FROM suspended_runs WHERE run_id = %s", (run_id,))
            conn.commit()

        self._run(_write)

    def known_products(self) -> list[str]:
        def _read(conn: Any) -> list[str]:
            cur = conn.cursor()
            cur.execute("SELECT product FROM dependency_health ORDER BY product")
            return [str(r[0]) for r in cur.fetchall()]

        result = self._run(_read)
        assert isinstance(result, list)
        return result


def _split(raw: Any) -> frozenset[str]:
    """Comma-separated text back to a set, dropping empties.

    Empty string means "none", not "one nameless member" — which is the bug a bare
    ``split(",")`` produces, and it would arrive as a role or pack named ``""`` that the
    trust fabric then refuses to resolve.
    """
    return frozenset(part for part in str(raw or "").split(",") if part)


__all__ = [
    "DEFAULT_RECOVERY_THRESHOLD",
    "DEFAULT_STALE_AFTER",
    "SCHEMA_PATH",
    "DependencyStoreError",
    "PostgresDependencyStore",
]
