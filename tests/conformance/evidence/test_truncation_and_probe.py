# SPDX-License-Identifier: Apache-2.0
"""The attack local mechanisms cannot see, and the probe that proves separation.

Two rows, and between them they carry the feature's whole claim.

**Truncation** (SC-004) is the one the chain provably cannot catch: delete the newest
entries and lower the head to match, and `seq 0..N-4` verifies perfectly against a head that
agrees with it. Every local mechanism is satisfied, because the actor who can rewrite one can
rewrite both. Only the platform's own earlier claim — shipped where that actor cannot reach
it — survives to disagree.

**The probe** (SC-005) is what makes any of this more than an assertion. ADR-0055 foreclosed
shipping to storage the enclave's own role can write, precisely so that non-solution would be
*visibly* non-compliant rather than arguably sufficient. The only honest way to tell the
difference is to try the tampering and require refusal.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from core.audit.destination_postgres import PostgresAuditDestination
from core.audit.egress import ship_pass
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.reconcile import findings_by_kind, reconcile
from core.audit.schema import AuditEventType
from tests.conformance.evidence.conftest import (
    COLLECTOR_DB,
    COLLECTOR_PORT,
    execute,
    query,
)

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


class _StaticCredentials:
    def __init__(self, credential: Any) -> None:
        self._credential = credential

    def fetch(self) -> Any:
        return self._credential


def _write_stream(entries: int = 6) -> str:
    from tests.harness.operator_credentials import OperatorCredentials

    # Typed as Any: the sink's parameter names the production credential class, and an
    # operator-held credential is deliberately not one — the same distinction the
    # dispatch harness draws for `PostgresDependencyStore`.
    credentials: Any = _StaticCredentials(OperatorCredentials().fetch())
    sink = PostgresAuditSink(credentials=credentials)
    correlation_id = f"trunc-{uuid.uuid4().hex[:12]}"
    for i in range(entries):
        sink.append_event(
            correlation_id=correlation_id,
            tenant_id="tenant-local",
            event_type=AuditEventType.RUN_START,
            payload={"i": i},
        )
    return correlation_id


def test_row_the_consistent_truncation_is_reported(
    platform_admin_connection: Any, egress_configured: dict[str, Any]
) -> None:
    """SC-004 — and the row this feature's whole head-shipping design exists for.

    Note what is asserted first: that the LOCAL mechanisms are satisfied by the tampering.
    Without that, the row would not be demonstrating anything the chain could not already
    do, and the shipped head would look like belt-and-braces rather than the load-bearing
    part it is.
    """
    correlation_id = _write_stream()
    destination = PostgresAuditDestination.from_credential(egress_configured)
    ship_pass(local=platform_admin_connection, destination=destination)

    # The attack: delete the newest entries AND lower the head to match, as the platform's
    # own database administrator. This is the rewrite that defeats chain, grant, and head
    # together, because one credential reaches all three.
    execute(
        platform_admin_connection,
        "DELETE FROM audit_entries WHERE correlation_id = %s AND seq >= 3",
        (correlation_id,),
    )
    execute(
        platform_admin_connection,
        "UPDATE audit_stream_heads SET highest_seq = 2, head_hash = "
        "(SELECT entry_hash FROM audit_entries WHERE correlation_id = %s AND seq = 2) "
        "WHERE correlation_id = %s",
        (correlation_id, correlation_id),
    )

    # The local view is now internally consistent — this is the precondition that makes the
    # row meaningful rather than a restatement of what the chain already catches.
    from core.audit.chain import verify_chain
    from core.audit.reconcile import _local_entries

    verify_chain(_local_entries(platform_admin_connection, correlation_id))
    head = query(
        platform_admin_connection,
        "SELECT highest_seq FROM audit_stream_heads WHERE correlation_id = %s",
        (correlation_id,),
    )
    assert head[0][0] == 2, "the arranged head does not agree with the arranged entries"

    # The supervisory loop keeps shipping after the tampering, so the row does too. This is
    # not incidental: it is the attacker's best remaining move. If head observations were
    # ever stored as an upsert rather than appended, this pass would lower the platform's
    # own shipped claim to match the truncated head and destroy the only witness. Detecting
    # a truncation that is never shipped over again would be detecting the easy case.
    ship_pass(local=platform_admin_connection, destination=destination)

    report = reconcile(
        local=platform_admin_connection, destination=destination, only={correlation_id}
    )

    assert "local_truncated" in findings_by_kind(report), (
        f"the consistent truncation was not reported: {[(f.kind, f.seq) for f in report.findings]}"
    )


def test_row_the_platform_cannot_alter_what_it_shipped(
    egress_configured: dict[str, Any],
) -> None:
    """SC-005 — separation demonstrated by attempting to break it.

    `verified` is only ever returned when both a modification and a deletion were refused by
    the destination itself. An operator's assertion in configuration would pass a check that
    never ran; this one runs.
    """
    destination = PostgresAuditDestination.from_credential(egress_configured)

    assert destination.probe() == "verified", (
        "the platform's own shipping credential was able to alter or remove a shipped "
        "record — the destination is inside the platform's administrative reach, which is "
        "the non-solution ADR-0055 named"
    )


def test_row_a_writable_destination_is_reported_non_compliant() -> None:
    """SC-005's negative, and the one that makes the positive mean something.

    Pointed at the COLLECTOR ADMIN's account — a destination the platform can write freely.
    It looks exactly like a second copy and is worthless as one, and the probe must say so
    rather than accept it.
    """
    writable = PostgresAuditDestination(
        host="127.0.0.1",
        port=COLLECTOR_PORT,
        dbname=COLLECTOR_DB,
        username="collector",
        password="dev-only-collector-admin",
    )

    assert writable.probe() == "non_compliant", (
        "a destination the platform can rewrite reported as compliant — the check that "
        "exists to make this shortcut visible did not see it"
    )


def test_row_an_unreachable_destination_is_unverified_never_verified() -> None:
    """FR-020b — the safe direction.

    A destination that cannot be probed has demonstrated nothing, and `unverified` says so.
    Reporting `verified` here would be the platform vouching for a control it never
    exercised, which is the shape of claim this entire feature was built to retire.
    """
    unreachable = PostgresAuditDestination(
        host="127.0.0.1",
        port=1,  # nothing listens here
        dbname=COLLECTOR_DB,
        username="harness_shipper",
        password="dev-only-shipper",
    )

    assert unreachable.probe() == "unverified"
