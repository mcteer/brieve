# SPDX-License-Identifier: Apache-2.0
"""The collector goes away, and neither runs nor entries are lost (015, SC-009/009a).

**A real outage, not a simulated one.** The collector's container is stopped, and every
failure below is a real connection failure through the real driver. A row that pointed the
shipper at a closed port would exercise the same code and prove less: it would show that
unreachability is handled, not that *this* destination going down is survivable, and the
difference is the whole reason the second copy is a separate store rather than a table.

Two claims, and they pull in opposite directions, which is why they are asserted together:

- **Runs complete anyway** (FR-014a). Delivery never gates availability. Putting a
  collector outage on the critical path of governed work would trade a real availability
  loss for an evidence gain the backlog already reports honestly.
- **Nothing is lost** (SC-009). The watermark does not advance past entries that were never
  confirmed, so when the destination returns the owed tail is still owed and still drains.

Between them sits the exposure window this feature is honest about: during the outage those
entries exist in one place, and the backlog is the number that says how many.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from typing import Any

import pytest

from core.audit.chain import verify_chain
from core.audit.destination_postgres import PostgresAuditDestination
from core.audit.egress import backlog_depth, ship_pass
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.schema import AuditEventType
from tests.conformance.evidence.conftest import COLLECTOR_PORT, query

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: How long the collector's scheduler is given to bring the task back. Generous: this row
#: is about surviving the outage, and a tight bound would turn a slow restart into a
#: failure of the property under test.
RESTART_BUDGET_SECONDS = 90


class _StaticCredentials:
    def __init__(self, credential: Any) -> None:
        self._credential = credential

    def fetch(self) -> Any:
        return self._credential


def _sink() -> PostgresAuditSink:
    from tests.harness.operator_credentials import OperatorCredentials

    credentials: Any = _StaticCredentials(OperatorCredentials().fetch())
    return PostgresAuditSink(credentials=credentials)


def _collector_container() -> str:
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=False
    )
    names = [n for n in result.stdout.split() if n.startswith("collector-postgres")]
    if not names:
        pytest.fail(
            "the collector container is not running — `make dev-up` brings it up. Not "
            "skippable: this row's whole subject is what happens when it stops, which "
            "cannot be observed if it never started."
        )
    return names[0]


def _reachable() -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", COLLECTOR_PORT), timeout=1):
            return True
    except OSError:
        return False


def _wait_until_reachable(deadline_seconds: int) -> None:
    """Wait for the scheduler to bring it back, and for Postgres to accept connections.

    Both, in that order: an open port is not a ready database, and the difference shows up
    as an authentication failure that reads like a credential problem.
    """
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if _reachable():
            try:
                PostgresAuditDestination(
                    host="127.0.0.1",
                    port=COLLECTOR_PORT,
                    dbname="collector",
                    username="harness_shipper",
                    password="dev-only-shipper",
                ).read_entries("readiness-probe")
                return
            except Exception:  # noqa: BLE001 — still booting; that is what we are waiting for
                pass
        time.sleep(2)
    pytest.fail(
        f"the collector did not return within {deadline_seconds}s. The enclave is now in a "
        "state this row created; `make dev-up` restores it."
    )


def test_row_an_outage_loses_no_entries_and_stops_no_runs(
    platform_admin_connection: Any, egress_configured: dict[str, Any]
) -> None:
    sink = _sink()
    destination = PostgresAuditDestination.from_credential(egress_configured)
    correlation_id = f"outage-{uuid.uuid4().hex[:12]}"

    for i in range(3):
        sink.append_event(
            correlation_id=correlation_id,
            tenant_id="tenant-local",
            event_type=AuditEventType.RUN_START,
            payload={"i": i},
        )
    ship_pass(local=platform_admin_connection, destination=destination)

    container = _collector_container()
    subprocess.run(["docker", "stop", container], capture_output=True, check=False)
    try:
        assert not _reachable(), "the collector is still reachable — the outage did not happen"

        # ---- the platform keeps working. This is the availability half.
        for i in range(3, 9):
            sink.append_event(
                correlation_id=correlation_id,
                tenant_id="tenant-local",
                event_type=AuditEventType.RUN_START,
                payload={"i": i},
            )
        during = query(
            platform_admin_connection,
            "SELECT count(*) FROM audit_entries WHERE correlation_id = %s",
            (correlation_id,),
        )
        assert during[0][0] == 9, "writing to the FIRST copy failed while the second was down"

        # ---- the shipper fails honestly, and says how far behind it is.
        outcome = ship_pass(local=platform_admin_connection, destination=destination)
        assert outcome.failures, "an unreachable destination reported no failure"
        assert outcome.shipped == 0
        assert backlog_depth(platform_admin_connection) >= 6, (
            "the undelivered tail was invisible — the exposure window must be observable"
        )
        watermark = query(
            platform_admin_connection,
            "SELECT shipped_seq FROM audit_egress_watermarks WHERE correlation_id = %s",
            (correlation_id,),
        )
        assert watermark[0][0] == 2, (
            "the watermark advanced past entries the destination never confirmed — those "
            "entries would never be re-attempted, which is silent loss"
        )
    finally:
        # Restoration belongs in `finally`: a failed assertion above must not leave the
        # enclave without its second copy for every row that runs after this one.
        subprocess.run(["docker", "start", container], capture_output=True, check=False)
        _wait_until_reachable(RESTART_BUDGET_SECONDS)

    # ---- recovery: the owed tail is still owed, and drains.
    recovered = ship_pass(local=platform_admin_connection, destination=destination)
    assert recovered.shipped >= 6, f"the outage's entries were not re-attempted: {recovered}"

    shipped = destination.read_entries(correlation_id)
    assert [e.seq for e in shipped] == list(range(9)), (
        f"entries written during the outage are missing from the second copy: "
        f"{[e.seq for e in shipped]}"
    )
    # And the recovered copy still stands on its own, which a gap would break.
    verify_chain(shipped)
