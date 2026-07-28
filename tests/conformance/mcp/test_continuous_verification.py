# SPDX-License-Identifier: Apache-2.0
"""Row: evidence integrity is checked while the system runs (FR-017, SC-010).

008 shipped the checker and called it from `make enclave-verify`, which covers bring-up
and not the running estate. A tamper-detection mechanism that only runs when an operator
restarts something detects tampering on a schedule the tamperer chooses.

**The clean-store half matters as much as the detection half.** A check that always fires
gets disabled, and a disabled check is worse than none because the gate still appears to
exist.
"""

from __future__ import annotations

from typing import Any

from core.audit.integrity import IntegrityFinding, IntegrityReport, verify_stream_integrity


class FakeConn:
    """A connection over hand-built rows, so the row tests the CHECKER rather than Postgres.

    The store's behaviour against a real database is an enclave row. What is under test
    here is whether the checker reports what it should — which is exactly the part a
    database cannot tell you is wrong.
    """

    def __init__(self, heads: list[tuple], entries: list[tuple]) -> None:
        self._heads = heads
        self._entries = entries
        self._result: list[tuple] = []

    def cursor(self) -> FakeConn:
        return self

    def execute(self, sql: str, params: tuple = ()) -> None:
        if "audit_stream_heads" in sql:
            self._result = self._heads
        elif "DISTINCT correlation_id" in sql:
            self._result = [(e[1],) for e in self._entries]
        else:
            self._result = [e for e in self._entries if e[1] == params[0]]

    def fetchall(self) -> list[tuple]:
        return self._result

    def close(self) -> None:
        return None


def test_row_a_clean_store_reports_clean() -> None:
    """The false-positive half. A check that always fires gets turned off."""
    report = verify_stream_integrity(lambda: FakeConn(heads=[], entries=[]))
    assert report.ok
    assert report.findings == []


def test_row_entries_with_no_recorded_head_are_reported() -> None:
    """Removing the head is the cheapest way to hide a truncation from a head-based check."""
    entries = [
        ("tenant-a", "stream-1", 0, "run_start", _ts(), "{}", "0" * 64, "h0"),
    ]
    report = verify_stream_integrity(lambda: FakeConn(heads=[], entries=entries))

    assert not report.ok
    kinds = {f.kind for f in report.findings}
    assert "head_missing" in kinds


def test_row_a_head_with_no_entries_is_reported() -> None:
    """The stream was emptied. The head is what remembers it existed."""
    report = verify_stream_integrity(
        lambda: FakeConn(heads=[("stream-1", 2, "h2")], entries=[])
    )

    assert not report.ok
    assert {f.kind for f in report.findings} == {"stream_emptied"}


def test_row_findings_carry_enough_for_an_operator_to_act() -> None:
    """A finding that named nothing would be an alert nobody can act on."""
    report = verify_stream_integrity(
        lambda: FakeConn(heads=[("stream-1", 5, "h5")], entries=[])
    )
    finding = report.findings[0]

    assert isinstance(finding, IntegrityFinding)
    assert finding.correlation_id == "stream-1"
    assert finding.kind
    assert finding.detail, "a finding with no detail tells an operator only that something is wrong"


def test_row_a_scoped_check_does_not_walk_the_whole_estate() -> None:
    """`only` exists so a targeted check is possible without scanning all history."""
    report = verify_stream_integrity(
        lambda: FakeConn(heads=[("stream-1", 0, "h0"), ("stream-2", 0, "h0")], entries=[]),
        only={"stream-1"},
    )
    assert report.streams_checked == 1
    assert {f.correlation_id for f in report.findings} == {"stream-1"}


def test_report_ok_is_derived_rather_than_set() -> None:
    """So a report cannot claim clean while carrying findings."""
    report = IntegrityReport()
    assert report.ok
    report.findings.append(IntegrityFinding("s", "truncated", "detail"))
    assert not report.ok


def _ts() -> Any:
    from datetime import UTC, datetime

    return datetime(2026, 1, 1, tzinfo=UTC)
