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

    def known_products(self) -> list[str]:
        def _read(conn: Any) -> list[str]:
            cur = conn.cursor()
            cur.execute("SELECT product FROM dependency_health ORDER BY product")
            return [str(r[0]) for r in cur.fetchall()]

        result = self._run(_read)
        assert isinstance(result, list)
        return result


__all__ = [
    "DEFAULT_RECOVERY_THRESHOLD",
    "DEFAULT_STALE_AFTER",
    "SCHEMA_PATH",
    "DependencyStoreError",
    "PostgresDependencyStore",
]
