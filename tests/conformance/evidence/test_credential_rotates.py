# SPDX-License-Identifier: Apache-2.0
"""The shipping credential is Vault's, not anybody's (015, ROADMAP gap 0b).

015 first shipped this account as a hand-written password at a KV path, and argued at length
that it had to be — that removing it needed a second trust store, and that rotation needed
bespoke automation. None of that was true, and none of it had been checked. Vault onboards an
existing database user as a **static role** and rotates its password on a period; with a
**rootless** connection it does so while holding no privileged account at the destination at
all, connecting as that very user.

These rows assert the three properties that makes real, in the order they matter:

1. The password in configuration is **dead**. Vault rotates on import, so the value the
   collector's operator handed over stops working the moment it is onboarded — which is what
   makes seeding a bootstrap credential a non-event rather than a standing secret.
2. A rotation **changes the password in force**, on demand and without a human.
3. Shipping **keeps working across it**, because the shipper reads the current value rather
   than caching one — the failure mode a cached credential produces is an outage that looks
   like the collector going down.

What none of them weaken is the boundary, which never rested on password secrecy: the
account holds `INSERT` and `SELECT`, and `probe()` goes on demonstrating that `UPDATE` and
`DELETE` are refused. See `test_truncation_and_probe.py`.
"""

from __future__ import annotations

import uuid
from typing import Any

import pg8000.dbapi
import pytest

from core.audit.destination_postgres import PostgresAuditDestination
from core.audit.egress import ship_pass
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.schema import AuditEventType
from tests.conformance.evidence.conftest import (
    COLLECTOR_DB,
    COLLECTOR_PORT,
    SHIPPER_CREDENTIAL_PATH,
    _vault_read,
    _vault_write,
)

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: What `infra/collector/roles.sql` seeds the account with before Vault takes it over. It is
#: in the repository in plain text on purpose — after onboarding it authenticates nothing.
SEED_PASSWORD = "dev-only-shipper"


class _StaticCredentials:
    def __init__(self, credential: Any) -> None:
        self._credential = credential

    def fetch(self) -> Any:
        return self._credential


def _can_authenticate(password: str) -> bool:
    try:
        conn = pg8000.dbapi.connect(
            host="127.0.0.1",
            port=COLLECTOR_PORT,
            database=COLLECTOR_DB,
            user="harness_shipper",
            password=password,
        )
    except Exception:  # noqa: BLE001 — a refusal is the answer, not an error
        return False
    conn.close()
    return True


def test_row_the_seeded_password_authenticates_nothing_after_onboarding() -> None:
    """The bootstrap credential is meant to die, and this is where that is checked.

    A seed that still worked would mean the platform held a password somebody had written
    down — the standing credential this replaced, wearing a rotation schedule.
    """
    assert not _can_authenticate(SEED_PASSWORD), (
        "the password in `infra/collector/roles.sql` still authenticates. Vault did not "
        "rotate on import, so the credential in force is one a human chose and a "
        "repository contains."
    )


def test_row_a_rotation_changes_the_password_with_no_human_involved(
    egress_configured: dict[str, Any],
) -> None:
    """FR-005 / gap 0b — rotation is Vault's, on demand and on a period.

    Forced here rather than waited for: the period is 24 hours, and a row that slept for it
    would not run. What is asserted is the same transition the period performs.
    """
    before = str(egress_configured["password"])
    assert _can_authenticate(before), "the credential Vault reports does not authenticate"

    _vault_write(f"database/rotate-role/{SHIPPER_CREDENTIAL_PATH.rsplit('/', 1)[-1]}")

    after = str(_vault_read(SHIPPER_CREDENTIAL_PATH)["password"])
    assert after != before, "a forced rotation did not change the password"
    assert _can_authenticate(after)
    assert not _can_authenticate(before), (
        "the previous password still authenticates after rotation — a rotation that leaves "
        "the old credential live has rotated nothing"
    )


def test_row_shipping_survives_a_rotation_because_the_credential_is_read_fresh(
    platform_admin_connection: Any,
) -> None:
    """The failure a cached credential produces, and the reason it must not be cached.

    A destination built once at service start works until the first rotation and then fails
    authentication — which reads in the logs as the collector going down, on a 24-hour
    cadence, days after anyone touched the code. So the shipper reads the current value each
    time it builds a destination, and this row rotates underneath it and ships again.
    """
    from tests.harness.operator_credentials import OperatorCredentials

    credentials: Any = _StaticCredentials(OperatorCredentials().fetch())
    sink = PostgresAuditSink(credentials=credentials)

    correlation_id = f"rotate-{uuid.uuid4().hex[:12]}"
    for i in range(3):
        sink.append_event(
            correlation_id=correlation_id,
            tenant_id="tenant-local",
            event_type=AuditEventType.RUN_START,
            payload={"i": i},
        )

    fresh = _vault_read(SHIPPER_CREDENTIAL_PATH)
    destination = PostgresAuditDestination(
        host="127.0.0.1",
        port=COLLECTOR_PORT,
        dbname=COLLECTOR_DB,
        username=str(fresh["username"]),
        password=str(fresh["password"]),
    )
    ship_pass(local=platform_admin_connection, destination=destination)

    # ---- rotate underneath it, then build again the way the shipper does
    _vault_write(f"database/rotate-role/{SHIPPER_CREDENTIAL_PATH.rsplit('/', 1)[-1]}")

    for i in range(3, 6):
        sink.append_event(
            correlation_id=correlation_id,
            tenant_id="tenant-local",
            event_type=AuditEventType.RUN_START,
            payload={"i": i},
        )

    rotated = _vault_read(SHIPPER_CREDENTIAL_PATH)
    assert rotated["password"] != fresh["password"], "the rotation did not take"

    after = PostgresAuditDestination(
        host="127.0.0.1",
        port=COLLECTOR_PORT,
        dbname=COLLECTOR_DB,
        username=str(rotated["username"]),
        password=str(rotated["password"]),
    )
    ship_pass(local=platform_admin_connection, destination=after)

    assert [e.seq for e in after.read_entries(correlation_id)] == [0, 1, 2, 3, 4, 5], (
        "entries written across a rotation did not all reach the second copy"
    )
