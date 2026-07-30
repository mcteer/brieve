# SPDX-License-Identifier: Apache-2.0
"""The second copy is real, stands alone, and exposes a rewrite (015, SC-001/002/003).

**These rows hold two credentials that a hermetic row cannot distinguish**: the platform's,
which can append to the destination and nothing more, and the collector administrator's,
which can do anything there. The separation between them is the property ADR-0055
establishes, and it is why these are `host_enclave` — the arranging has to happen somewhere
the platform's own identity cannot reach.

The attacks below are committed as the PLATFORM's database administrator, which is the
threat actor the whole feature models: the party who can rewrite the local trail and its
head consistently, defeating the chain, the append-only grant, and the head together.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from core.audit.chain import verify_chain
from core.audit.destination_postgres import PostgresAuditDestination
from core.audit.egress import ship_pass
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.reconcile import reconcile
from core.audit.schema import AuditEventType
from tests.conformance.evidence.conftest import execute, query

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


class _StaticCredentials:
    """Wraps an already-fetched credential so the sink can use this row's connection.

    The sink expects something with `.fetch()`; here the operator has already obtained one.
    """

    def __init__(self, credential: Any) -> None:
        self._credential = credential

    def fetch(self) -> Any:
        return self._credential


def _write_stream(entries: int = 5) -> str:
    """A real stream through the real sink — positions, hashes, and head all genuine."""
    from tests.harness.operator_credentials import OperatorCredentials

    # Typed as Any: the sink's parameter names the production credential class, and an
    # operator-held credential is deliberately not one — the same distinction the
    # dispatch harness draws for `PostgresDependencyStore`.
    credentials: Any = _StaticCredentials(OperatorCredentials().fetch())
    sink = PostgresAuditSink(credentials=credentials)
    correlation_id = f"egress-{uuid.uuid4().hex[:12]}"
    for i in range(entries):
        sink.append_event(
            correlation_id=correlation_id,
            tenant_id="tenant-local",
            event_type=AuditEventType.RUN_START,
            payload={"i": i},
        )
    return correlation_id


def test_row_every_entry_reaches_the_second_copy_with_its_chain_intact(
    platform_admin_connection: Any,
    collector_admin_connection: Any,
    egress_configured: dict[str, Any],
) -> None:
    """SC-001 and SC-002, read back under the DESTINATION's own credential.

    Read as the collector administrator rather than through the shipper, because the claim
    is about what is *there* — a read through the object that wrote it would be asking the
    writer whether it wrote.
    """
    correlation_id = _write_stream()
    destination = PostgresAuditDestination.from_credential(egress_configured)

    ship_pass(local=platform_admin_connection, destination=destination)

    rows = query(
        collector_admin_connection,
        "SELECT tenant_id, seq, event_type, prev_hash, entry_hash FROM shipped_entries "
        "WHERE correlation_id = %s ORDER BY seq",
        (correlation_id,),
    )
    assert len(rows) == 5, f"the second copy holds {len(rows)} of 5 entries"

    local = query(
        platform_admin_connection,
        "SELECT tenant_id, seq, event_type, prev_hash, entry_hash FROM audit_entries "
        "WHERE correlation_id = %s ORDER BY seq",
        (correlation_id,),
    )
    assert rows == local, "the copies differ in a hashed field — they cannot be compared"

    # The head observation ships too. Without it the truncation attack survives against both
    # copies at once, which is the half most likely to be dropped as an optimisation.
    heads = query(
        collector_admin_connection,
        "SELECT highest_seq FROM shipped_head_observations WHERE correlation_id = %s",
        (correlation_id,),
    )
    assert heads, "entries shipped without the head that makes truncation detectable"

    # SC-002: the second copy verifies on its own contents, with no local read.
    verify_chain(destination.read_entries(correlation_id))


def test_row_shipping_does_not_alter_the_local_trail(
    platform_admin_connection: Any, egress_configured: dict[str, Any]
) -> None:
    """FR-004 — structural under the outbox design, and asserted so it stays a row.

    The shipper only ever reads `audit_entries`; nothing in this feature writes to it. That
    is easy to believe and cheap to check, and the check is what would catch a future
    "optimisation" that marked entries shipped in place.
    """
    correlation_id = _write_stream(3)
    before = query(
        platform_admin_connection,
        "SELECT seq, entry_hash, prev_hash, payload FROM audit_entries "
        "WHERE correlation_id = %s ORDER BY seq",
        (correlation_id,),
    )

    ship_pass(
        local=platform_admin_connection,
        destination=PostgresAuditDestination.from_credential(egress_configured),
    )

    after = query(
        platform_admin_connection,
        "SELECT seq, entry_hash, prev_hash, payload FROM audit_entries "
        "WHERE correlation_id = %s ORDER BY seq",
        (correlation_id,),
    )
    assert before == after, "shipping modified the first copy"


def test_row_a_rewritten_local_entry_is_named_by_stream_and_sequence(
    platform_admin_connection: Any, egress_configured: dict[str, Any]
) -> None:
    """SC-003 — the attack, committed with the credential that can commit it.

    Rewriting an entry breaks the local chain, so the chain alone would catch this one. What
    the second copy adds is the *location* and the independent witness: the finding names
    which position disagrees, and it does so from a copy the rewriting credential cannot
    reach.
    """
    correlation_id = _write_stream()
    destination = PostgresAuditDestination.from_credential(egress_configured)
    ship_pass(local=platform_admin_connection, destination=destination)

    execute(
        platform_admin_connection,
        "UPDATE audit_entries SET payload = '{\"rewritten\": true}'::jsonb "
        "WHERE correlation_id = %s AND seq = 2",
        (correlation_id,),
    )

    report = reconcile(
        local=platform_admin_connection, destination=destination, only={correlation_id}
    )
    mismatches = [f for f in report.findings if f.kind == "entry_mismatch"]
    assert mismatches, f"a rewritten entry went unreported: {report.findings}"
    assert mismatches[0].seq == 2, "the finding did not name the position that differs"

    # FR-019: the report locates divergence and never quotes the evidence it read.
    assert all("rewritten" not in f.detail for f in report.findings)
