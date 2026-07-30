# SPDX-License-Identifier: Apache-2.0
"""The second copy, in a Postgres the platform does not administer (ADR-0055, 015).

**The credential is deliberately not a `VaultDatabaseCredentials`, and the type difference
is the design.** Every other store this platform reaches is entered with a credential its
own Vault mints on demand — which is right for stores the platform administers, and exactly
wrong here. A credential the platform's Vault issues is one the platform's administrators
govern; handing them the destination's credential lifecycle would return the guarded
system's keys to the party being guarded against.

So this class takes a static credential the *collector administrator* issued, holding INSERT
and SELECT and nothing else. It is read from Vault KV under the service's own attested
identity — storage, not lifecycle control: the collector administrator can rotate or revoke
it at the destination whatever the platform's Vault has cached.

Not from jobspec env, which is where it nearly went: the SELECT half reads the whole
evidence copy across every tenant, and jobspec metadata is readable by anyone with scheduler
access. That would have created an ungoverned evidence read beside ADR-0035's governed one —
the same exposure the `run_inputs` rule already closed, arriving by a different door.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pg8000.dbapi

from core.audit.chain import GENESIS_PREV_HASH
from core.audit.egress import (
    PROBE_STREAM,
    DestinationVerification,
    HeadObservation,
)
from core.audit.schema import AuditEntry, AuditEventType
from core.errors import CoreError

#: Where `enclave-up` writes the shipping credential and the mcp role may read it.
EGRESS_CREDENTIAL_PATH = "secret/data/audit-egress/shipper"


class AuditDestinationError(CoreError):
    """The second copy could not be reached or written. Never swallowed."""


def load_egress_credential(*, token: str | None = None) -> dict[str, Any] | None:
    """Read the shipping credential from Vault, or None when egress is not configured.

    ``None`` rather than an exception, because an estate with no second destination is a
    valid posture — ABSENT (FR-009) — and the caller is the one positioned to report it as
    such. A raise here would make "not configured" indistinguishable from "misconfigured".
    """
    addr = (os.environ.get("VAULT_ADDR") or "https://127.0.0.1:8200").rstrip("/")
    vault_token = token or os.environ.get("VAULT_TOKEN")
    if not vault_token:
        # Inside an allocation the service exchanges its workload identity for a token
        # before reaching here; without one there is nothing to read with.
        return None
    cacert = os.environ.get("VAULT_CACERT")
    context = ssl.create_default_context(cafile=cacert) if cacert else None
    request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
        f"{addr}/v1/{EGRESS_CREDENTIAL_PATH}", headers={"X-Vault-Token": vault_token}
    )
    try:
        with urllib.request.urlopen(request, timeout=10, context=context) as response:  # noqa: S310
            body = json.loads(response.read())
        data: dict[str, Any] = body["data"]["data"]
        return data
    except Exception:  # noqa: BLE001 — absent and unreachable are both "no destination"
        return None


class PostgresAuditDestination:
    """Append-only access to the second copy."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        dbname: str,
        username: str,
        password: str,
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._dbname = dbname
        self._username = username
        self._password = password
        self._connect = connect or pg8000.dbapi.connect

    @classmethod
    def from_credential(cls, credential: dict[str, Any]) -> PostgresAuditDestination:
        return cls(
            host=str(credential["host"]),
            port=int(credential["port"]),
            dbname=str(credential["dbname"]),
            username=str(credential["username"]),
            password=str(credential["password"]),
        )

    def _open(self) -> Any:
        conn = self._connect(
            host=self._host,
            port=self._port,
            database=self._dbname,
            user=self._username,
            password=self._password,
        )
        conn.autocommit = True
        return conn

    def _run(self, work: Callable[[Any], Any]) -> Any:
        conn = None
        try:
            conn = self._open()
            return work(conn)
        except Exception as exc:
            raise AuditDestinationError(f"audit destination error: {exc}") from exc
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001 — never mask the real error
                    pass

    # ------------------------------------------------------------------ append

    def ship_entries(self, entries: list[AuditEntry]) -> int:
        """Append entries, first write wins.

        `ON CONFLICT DO NOTHING` is what lets the watermark advance last: a crash between
        delivery and the advance re-ships, and the re-ship changes nothing. It is also the
        evidence posture — an actor who rewrites a local entry and re-ships it collides with
        the honest original, so tampering is quiet here and loud at reconcile time. The
        shipper is not a judge.
        """
        if not entries:
            return 0

        def work(conn: Any) -> int:
            cursor = conn.cursor()
            try:
                for entry in entries:
                    cursor.execute(
                        "INSERT INTO shipped_entries "
                        "(tenant_id, correlation_id, seq, event_type, timestamp, payload, "
                        " prev_hash, entry_hash) "
                        "VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s) "
                        "ON CONFLICT (correlation_id, seq) DO NOTHING",
                        (
                            entry.tenant_id,
                            entry.correlation_id,
                            entry.seq,
                            str(entry.event_type),
                            entry.timestamp,
                            json.dumps(entry.payload, sort_keys=True),
                            entry.prev_hash,
                            entry.entry_hash,
                        ),
                    )
                return len(entries)
            finally:
                cursor.close()

        return int(self._run(work))

    def ship_head_observation(self, observation: HeadObservation) -> None:
        """Append a claim about a stream's length — never update one."""

        def work(conn: Any) -> None:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "INSERT INTO shipped_head_observations "
                    "(correlation_id, highest_seq, head_hash) VALUES (%s, %s, %s) "
                    "ON CONFLICT (correlation_id, highest_seq) DO NOTHING",
                    (observation.correlation_id, observation.highest_seq, observation.head_hash),
                )
            finally:
                cursor.close()

        self._run(work)

    # ------------------------------------------------------------------- read

    def read_entries(self, correlation_id: str) -> list[AuditEntry]:
        def work(conn: Any) -> list[AuditEntry]:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT tenant_id, correlation_id, seq, event_type, timestamp, payload, "
                    "       prev_hash, entry_hash "
                    "FROM shipped_entries WHERE correlation_id = %s ORDER BY seq",
                    (correlation_id,),
                )
                return [_row_to_entry(r) for r in cursor.fetchall()]
            finally:
                cursor.close()

        result = self._run(work)
        return list(result)

    def read_head_observations(self, correlation_id: str) -> list[HeadObservation]:
        def work(conn: Any) -> list[HeadObservation]:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT correlation_id, highest_seq, head_hash "
                    "FROM shipped_head_observations WHERE correlation_id = %s "
                    "ORDER BY highest_seq",
                    (correlation_id,),
                )
                return [
                    HeadObservation(
                        correlation_id=str(r[0]), highest_seq=int(r[1]), head_hash=str(r[2])
                    )
                    for r in cursor.fetchall()
                ]
            finally:
                cursor.close()

        result = self._run(work)
        return list(result)

    def coverage_start(self) -> datetime | None:
        """The earliest `received_at` — when the second copy's attestation begins."""

        def work(conn: Any) -> datetime | None:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT MIN(received_at) FROM shipped_entries")
                row = cursor.fetchone()
                if row is None or row[0] is None:
                    return None
                value: datetime = row[0]
                return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
            finally:
                cursor.close()

        result = self._run(work)
        return result if result is None else result

    # ------------------------------------------------------------------ probe

    def probe(self) -> DestinationVerification:
        """Try to tamper. Require refusal.

        The three outcomes are not symmetric, and the asymmetry is the safety:

        - Both refused → ``verified``. The platform demonstrably cannot alter what it shipped.
        - Either succeeded → ``non_compliant``. The destination is inside the platform's
          administrative reach, which is the non-solution ADR-0055 named — and it is now
          reported as such rather than passing for a second copy.
        - Could not be attempted → ``unverified``. Never ``verified``: a control the platform
          has not exercised must not report as one it has.

        **Aimed at a sacrificial stream** (`PROBE_STREAM`), because FR-020c forbids a probe
        that leaves the destination altered. Success alters nothing — refusal is the expected
        result. Failure alters only probe rows, and downgrades the posture besides, so the
        damage is bounded to the thing whose purpose was to be damaged.
        """
        try:
            self._seed_probe_stream()
        except Exception:  # noqa: BLE001 — cannot even append: nothing has been demonstrated
            return "unverified"

        update_refused = self._refused(
            "UPDATE shipped_entries SET payload = '{\"probe\":true}'::jsonb "
            "WHERE correlation_id = %s"
        )
        delete_refused = self._refused("DELETE FROM shipped_entries WHERE correlation_id = %s")

        if update_refused is None or delete_refused is None:
            return "unverified"
        return "verified" if (update_refused and delete_refused) else "non_compliant"

    def _seed_probe_stream(self) -> None:
        """One row for the probe to attack. Idempotent, and not evidence.

        Its `tenant_id` names it as platform-internal so a reconciliation walk or an
        evidence read never mistakes it for a tenant's trail.
        """
        self.ship_entries(
            [
                AuditEntry(
                    correlation_id=PROBE_STREAM,
                    tenant_id="__platform__",
                    seq=0,
                    event_type=AuditEventType.RUN_START,
                    timestamp=datetime.now(UTC),
                    payload={"probe": "separation"},
                    prev_hash=GENESIS_PREV_HASH,
                    entry_hash="probe",
                )
            ]
        )

    def _refused(self, sql: str) -> bool | None:
        """True if the statement was refused, False if it succeeded, None if undecidable.

        A permission error is the answer this looks for. Any *other* failure — the store
        unreachable, the table missing — means the question was never put, and reporting
        that as refusal would manufacture a verification out of an outage.
        """
        conn = None
        try:
            conn = self._open()
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (PROBE_STREAM,))
                return False
            finally:
                cursor.close()
        except Exception as exc:  # noqa: BLE001 — the exception IS the measurement
            return True if _is_permission_denied(exc) else None
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass


def _is_permission_denied(exc: Exception) -> bool:
    """SQLSTATE 42501 is insufficient_privilege.

    Matched on the code rather than the message, so a localised or reworded server string
    cannot silently turn a refusal into an undecidable result — the same reasoning the
    durability provider's auth-failure check already carries.
    """
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], dict):
        code = args[0].get("C", "")
        if isinstance(code, str) and code == "42501":
            return True
    return "permission denied" in str(exc).lower()


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


__all__ = [
    "build_destination",
    "EGRESS_CREDENTIAL_PATH",
    "AuditDestinationError",
    "PostgresAuditDestination",
    "load_egress_credential",
]


def build_destination() -> PostgresAuditDestination | None:
    """The second copy, or ``None`` when this estate has not configured one.

    ``None`` is a posture rather than a failure (FR-009). An estate without a destination
    has no tamper-evidence, and the honest response is to say so — reporting ABSENT — rather
    than to run a pass that quietly does nothing and reads as protected.

    The credential comes from Vault under the calling service's own attested identity, never
    from a jobspec env block: its SELECT half reads the entire evidence copy across every
    tenant, and jobspec metadata is readable by anyone with scheduler access.

    Lives here rather than in a surface because both surfaces need it, and a helper owned by
    one of them would make the other import across the boundary to get its second copy.
    """
    credential = load_egress_credential()
    if credential is None:
        return None
    return PostgresAuditDestination.from_credential(credential)
