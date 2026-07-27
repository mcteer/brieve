# SPDX-License-Identifier: Apache-2.0
"""The evidence read path against Postgres.

A **separate module** from :mod:`core.audit.postgres_sink`, importing nothing from it, so
that "the query cannot reach the sink" is a property of the import graph rather than of
everyone in one file being careful.

It holds its own connection drawn from the **evidence** Vault role, which is granted
``SELECT`` on ``audit_entries`` and nothing else — no ``INSERT``, no ``UPDATE``, no
``DELETE``, and no grant at all on ``audit_stream_heads``. So even if a refactor handed
this object a writable code path, Postgres refuses. That is the defence ADR-0035 asks to
be proven rather than asserted.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC
from typing import Any

import pg8000.dbapi

from core.audit.query import EvidenceQueryRequest
from core.audit.schema import AuditEntry, AuditEventType
from core.durability.credentials import DatabaseCredential, VaultDatabaseCredentials
from core.errors import CoreError


class EvidenceReadError(CoreError):
    """The evidence store could not be read."""


class PostgresEvidenceQuery:
    """Read-only, tenant-bounded access to the evidence plane."""

    def __init__(
        self,
        *,
        credentials: VaultDatabaseCredentials,
        host: str = "127.0.0.1",
        port: int = 5432,
        dbname: str = "brieve",
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self._credentials = credentials
        self._host = host
        self._port = port
        self._dbname = dbname
        self._connect = connect or pg8000.dbapi.connect
        self._credential: DatabaseCredential | None = None

    def _open(self, *, refresh: bool) -> Any:
        if refresh or self._credential is None:
            self._credential = self._credentials.fetch()
        cred = self._credential
        return self._connect(
            host=self._host,
            port=self._port,
            database=self._dbname,
            user=cred.username,
            password=cred.password,
        )

    def search(self, request: EvidenceQueryRequest) -> list[AuditEntry]:
        """Return entries within the request's scope.

        The tenant predicate is applied unconditionally and first. It is taken from the
        request object, which the surface builds from the authenticated subject — there is
        no code path by which a caller's input reaches it.
        """
        clauses = ["tenant_id = %s"]
        params: list[Any] = [request.tenant_id]

        # run_id narrows the same column: 005 defaults a run's id to its correlation id,
        # so this is an equivalence rather than a second column the entries lack.
        correlation = request.correlation_id or request.run_id
        if correlation is not None:
            clauses.append("correlation_id = %s")
            params.append(correlation)
        if request.start_time is not None:
            clauses.append("timestamp >= %s")
            params.append(request.start_time)
        if request.end_time is not None:
            clauses.append("timestamp <= %s")
            params.append(request.end_time)
        if request.event_types:
            placeholders = ", ".join(["%s"] * len(request.event_types))
            clauses.append(f"event_type IN ({placeholders})")
            params.extend(sorted(str(e) for e in request.event_types))

        sql = (
            "SELECT tenant_id, correlation_id, seq, event_type, timestamp, payload, "
            "       prev_hash, entry_hash "
            f"FROM audit_entries WHERE {' AND '.join(clauses)} "
            "ORDER BY timestamp, correlation_id, seq LIMIT %s"
        )
        params.append(request.limit)

        try:
            conn = self._open(refresh=False)
        except Exception:
            conn = self._open(refresh=True)
        try:
            cur = conn.cursor()
            cur.execute(sql, tuple(params))
            return [_row_to_entry(r) for r in cur.fetchall()]
        except Exception as exc:
            raise EvidenceReadError(f"evidence read failed: {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def exists_outside_tenant(self, *, correlation_id: str, tenant_id: str) -> bool:
        """See :meth:`core.audit.query.EvidenceQuery.exists_outside_tenant`.

        Note what this implies and does not: the SQL role can see that rows exist under
        another tenant, because the tenant boundary is enforced by this application rather
        than by the database. Postgres row-level security would move that enforcement one
        layer down and is the right eventual home for it; it is not in this feature's
        scope, and pretending the current arrangement is stronger than it is would be
        worse than recording the gap here.
        """
        try:
            conn = self._open(refresh=False)
        except Exception:
            conn = self._open(refresh=True)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM audit_entries WHERE correlation_id = %s AND tenant_id <> %s LIMIT 1",
                (correlation_id, tenant_id),
            )
            return cur.fetchone() is not None
        except Exception as exc:
            raise EvidenceReadError(f"evidence scope check failed: {exc}") from exc
        finally:
            try:
                conn.close()
            except Exception:
                pass


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


__all__ = ["EvidenceReadError", "PostgresEvidenceQuery"]
