# SPDX-License-Identifier: Apache-2.0
"""Stream integrity verification — the detector, not just the detectability.

A recorded head makes truncation *detectable*. Something has to read it back for
truncation to be *detected*, and the difference is the whole value (FR-010e). A control
whose only enforcement is everyone remembering is the shape the constitution legislates
against.

What each mechanism catches, because they are not interchangeable:

- **The chain** catches modification and middle-deletion. Both break the ``seq`` sequence
  or the ``prev_hash`` link.
- **The head** catches truncation, which the chain cannot: delete the newest three entries
  and ``seq 0..N-4`` verifies perfectly. That is the obvious move against a log of who
  read what, and it is why this module exists.

Runs under the **run** role. The evidence role holds no grant on ``audit_stream_heads`` at
all — not even ``SELECT`` — so the read path cannot learn what it would need to forge.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from core.audit.chain import verify_chain
from core.audit.postgres_sink import _row_to_entry


@dataclass
class IntegrityFinding:
    correlation_id: str
    kind: str
    detail: str


@dataclass
class IntegrityReport:
    streams_checked: int = 0
    findings: list[IntegrityFinding] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings


def verify_stream_integrity(conn_factory: Callable[[], Any]) -> IntegrityReport:
    """Walk every stream, verify its chain, and compare its tail to the recorded head.

    ``conn_factory`` returns a connection holding the **run** role, since the evidence
    role cannot read the heads table.
    """
    report = IntegrityReport()
    conn = conn_factory()
    try:
        cur = conn.cursor()
        cur.execute("SELECT correlation_id, highest_seq, head_hash FROM audit_stream_heads")
        heads = {str(r[0]): (int(r[1]), str(r[2])) for r in cur.fetchall()}

        cur.execute("SELECT DISTINCT correlation_id FROM audit_entries")
        streams = {str(r[0]) for r in cur.fetchall()}

        for correlation_id in sorted(streams | set(heads)):
            report.streams_checked += 1
            cur.execute(
                "SELECT tenant_id, correlation_id, seq, event_type, timestamp, payload, "
                "       prev_hash, entry_hash "
                "FROM audit_entries WHERE correlation_id = %s ORDER BY seq",
                (correlation_id,),
            )
            entries = [_row_to_entry(r) for r in cur.fetchall()]

            if correlation_id not in heads:
                # Entries with no head at all: the head row was removed, which is the
                # cheapest way to hide a truncation from a check that trusts the head.
                report.findings.append(
                    IntegrityFinding(
                        correlation_id,
                        "head_missing",
                        f"{len(entries)} entries with no recorded head",
                    )
                )
                continue

            highest_seq, head_hash = heads[correlation_id]

            if not entries:
                report.findings.append(
                    IntegrityFinding(
                        correlation_id,
                        "stream_emptied",
                        f"head records seq {highest_seq} but no entries remain",
                    )
                )
                continue

            try:
                verify_chain(entries)
            except ValueError as exc:
                # Modification or middle-deletion. The chain is the mechanism here.
                report.findings.append(IntegrityFinding(correlation_id, "chain_broken", str(exc)))
                continue

            tail = entries[-1]
            if tail.seq != highest_seq or tail.entry_hash != head_hash:
                # Truncation. The chain verified perfectly above and still missed this,
                # which is exactly why the head exists.
                report.findings.append(
                    IntegrityFinding(
                        correlation_id,
                        "truncated",
                        f"head records seq {highest_seq} but the stream ends at {tail.seq}",
                    )
                )
        return report
    finally:
        try:
            conn.close()
        except Exception:
            pass


__all__ = ["IntegrityFinding", "IntegrityReport", "verify_stream_integrity"]
