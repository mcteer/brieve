# SPDX-License-Identifier: Apache-2.0
"""Shipping arithmetic and reconciler verdicts, hermetically (015 T010/T015/T018).

**What a hermetic row can prove here, and what it deliberately cannot.** These assert the
bookkeeping: that the watermark advances only on confirmed delivery, that re-shipping is a
no-op, that each verdict fires on the state it names. What none of them can assert is the
*separation* — that the platform's credential cannot alter the second copy — because a double
in this process has whatever permissions the test gives it. That claim needs a real store
under a real foreign credential, and it lives in `tests/conformance/evidence/`.

Keeping the split explicit matters: a suite where the separation looked tested here would be
the substitution ADR-0055 warns about, one layer up.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.audit.chain import GENESIS_PREV_HASH, compute_entry_hash, verify_chain
from core.audit.egress import DestinationVerification, HeadObservation, ship_pass
from core.audit.reconcile import findings_by_kind, posture_reason, reconcile
from core.audit.schema import AuditEntry, AuditEventType


class FakeDestination:
    """An in-process second copy, honest about first-write-wins.

    Mirrors the Postgres implementation's `ON CONFLICT DO NOTHING` exactly, because that
    conflict clause is what makes the watermark-advances-last ordering safe — a double that
    overwrote instead would make a broken shipper look correct here and fail in the enclave.
    """

    def __init__(self, *, verification: DestinationVerification = "verified") -> None:
        self.entries: dict[tuple[str, int], AuditEntry] = {}
        self.observations: list[HeadObservation] = []
        self.verification = verification
        self.fail_next = False
        self.ship_calls = 0

    def ship_entries(self, entries: list[AuditEntry]) -> int:
        self.ship_calls += 1
        if self.fail_next:
            raise RuntimeError("destination unreachable")
        for entry in entries:
            self.entries.setdefault((entry.correlation_id, entry.seq), entry)
        return len(entries)

    def ship_head_observation(self, observation: HeadObservation) -> None:
        if self.fail_next:
            raise RuntimeError("destination unreachable")
        if observation not in self.observations:
            self.observations.append(observation)

    def read_entries(self, correlation_id: str) -> list[AuditEntry]:
        return [e for (cid, _), e in sorted(self.entries.items()) if cid == correlation_id]

    def read_head_observations(self, correlation_id: str) -> list[HeadObservation]:
        return [o for o in self.observations if o.correlation_id == correlation_id]

    def probe(self) -> DestinationVerification:
        return self.verification

    def coverage_start(self) -> datetime | None:
        return datetime(2026, 7, 30, tzinfo=UTC) if self.entries else None


class FakeCursor:
    def __init__(self, db: FakeLocal) -> None:
        self._db = db
        self._rows: list[Any] = []

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self._rows = self._db.run(sql, params)

    def fetchall(self) -> list[Any]:
        return self._rows

    def fetchone(self) -> Any:
        return self._rows[0] if self._rows else None

    def close(self) -> None:
        return None


class FakeLocal:
    """The platform's evidence store, reduced to what the shipper and reconciler read."""

    def __init__(self) -> None:
        self.entries: list[AuditEntry] = []
        self.heads: dict[str, tuple[int, str]] = {}
        self.watermarks: dict[str, int] = {}

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def append(self, correlation_id: str, count: int, *, tenant: str = "t") -> None:
        """Write a real, chain-linked stream — hashes computed the way the sink computes them."""
        prev = GENESIS_PREV_HASH
        start = len([e for e in self.entries if e.correlation_id == correlation_id])
        for i in range(start, start + count):
            ts = datetime(2026, 7, 30, 12, 0, i, tzinfo=UTC)
            payload = {"i": i}
            entry_hash = compute_entry_hash(
                correlation_id=correlation_id,
                tenant_id=tenant,
                seq=i,
                event_type=str(AuditEventType.RUN_START),
                timestamp=ts,
                payload=payload,
                prev_hash=prev,
            )
            self.entries.append(
                AuditEntry(
                    correlation_id=correlation_id,
                    tenant_id=tenant,
                    seq=i,
                    event_type=AuditEventType.RUN_START,
                    timestamp=ts,
                    payload=payload,
                    prev_hash=prev,
                    entry_hash=entry_hash,
                )
            )
            prev = entry_hash
        last = self.entries[-1]
        self.heads[correlation_id] = (last.seq, last.entry_hash)

    def run(self, sql: str, params: tuple[Any, ...] | None) -> list[Any]:
        text = " ".join(sql.split())
        if "SUM(h.highest_seq" in text:
            total = sum(
                head - self.watermarks.get(cid, -1)
                for cid, (head, _) in self.heads.items()
                if head > self.watermarks.get(cid, -1)
            )
            return [[total]]
        if "FROM audit_stream_heads h" in text and "WHERE h.highest_seq >" in text:
            return [
                [cid, head, head_hash, self.watermarks.get(cid, -1)]
                for cid, (head, head_hash) in sorted(self.heads.items())
                if head > self.watermarks.get(cid, -1)
            ]
        if "FROM audit_stream_heads h" in text:
            return [
                [cid, head, self.watermarks.get(cid, -1)]
                for cid, (head, _) in sorted(self.heads.items())
            ]
        if "FROM audit_entries" in text:
            assert params is not None
            cid = params[0]
            rows = [e for e in self.entries if e.correlation_id == cid]
            if len(params) > 1 and "seq >" in text:
                rows = [e for e in rows if e.seq > params[1]]
            return [
                [
                    e.tenant_id,
                    e.correlation_id,
                    e.seq,
                    str(e.event_type),
                    e.timestamp,
                    e.payload,
                    e.prev_hash,
                    e.entry_hash,
                ]
                for e in sorted(rows, key=lambda e: e.seq)
            ]
        if "INSERT INTO audit_egress_watermarks" in text:
            assert params is not None
            cid, seq = str(params[0]), int(params[1])
            self.watermarks[cid] = max(self.watermarks.get(cid, -1), seq)
            return []
        raise AssertionError(f"unexpected SQL in the fake: {text[:80]}")


def _prepared(streams: int = 1, entries: int = 4) -> tuple[FakeLocal, FakeDestination]:
    local = FakeLocal()
    for n in range(streams):
        local.append(f"run-{n}", entries)
    return local, FakeDestination()


# --------------------------------------------------------------------------- shipping


def test_a_pass_ships_everything_above_the_watermark() -> None:
    local, destination = _prepared()

    outcome = ship_pass(local=local, destination=destination)

    assert outcome.shipped == 4
    assert outcome.backlog == 0
    assert local.watermarks["run-0"] == 3
    assert len(destination.read_entries("run-0")) == 4


def test_a_second_pass_with_nothing_new_ships_nothing() -> None:
    """The worklist is a join, so a fully-shipped stream is simply absent from it."""
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)
    calls_after_first = destination.ship_calls

    outcome = ship_pass(local=local, destination=destination)

    assert outcome.shipped == 0
    assert destination.ship_calls == calls_after_first, "an idle pass touched the destination"


def test_re_shipping_is_a_no_op_so_the_watermark_can_advance_last() -> None:
    """First write wins, which is what makes a crash between delivery and advance safe.

    The ordering `ship → confirm → advance` is only correct if re-shipping changes nothing.
    Asserted here rather than assumed, because the alternative ordering — advance first —
    looks equally reasonable and loses every entry written between the advance and a crash.
    """
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)
    original = destination.read_entries("run-0")[2]

    # Simulate the crash: the delivery happened, the watermark did not advance.
    local.watermarks["run-0"] = 0
    ship_pass(local=local, destination=destination)

    assert destination.read_entries("run-0")[2] is original, (
        "the re-ship replaced the original — a tampered re-ship would then overwrite the "
        "honest copy, which is the attack, not the recovery"
    )
    assert local.watermarks["run-0"] == 3


def test_a_failed_ship_leaves_the_watermark_and_reports_the_backlog() -> None:
    """FR-015/016: never a silent drop, and the shortfall is visible.

    The entries stay owed and the backlog names how many. An implementation that advanced
    the watermark anyway would lose them with no error and no record — the failure mode this
    whole feature exists to close, reproduced inside the mechanism meant to close it.
    """
    local, destination = _prepared()
    destination.fail_next = True

    outcome = ship_pass(local=local, destination=destination)

    assert outcome.failures, "a failed delivery was not reported"
    assert outcome.backlog == 4
    assert "run-0" not in local.watermarks, "the watermark advanced past entries never delivered"

    destination.fail_next = False
    recovered = ship_pass(local=local, destination=destination)
    assert recovered.shipped == 4, "the owed entries were not re-attempted after recovery"
    assert local.watermarks["run-0"] == 3


def test_one_failing_stream_does_not_strand_the_others() -> None:
    local, destination = _prepared(streams=3)

    class OneBadStream(FakeDestination):
        def ship_entries(self, entries: list[AuditEntry]) -> int:
            if entries and entries[0].correlation_id == "run-1":
                raise RuntimeError("this stream only")
            return super().ship_entries(entries)

    destination = OneBadStream()
    outcome = ship_pass(local=local, destination=destination)

    assert [cid for cid, _ in outcome.failures] == ["run-1"]
    assert local.watermarks.get("run-0") == 3
    assert local.watermarks.get("run-2") == 3


def test_every_chain_field_survives_the_trip() -> None:
    """T010 — a digest-only copy is the wrong half (ADR-0055).

    The second copy has to be independently chain-verifiable and comparable entry-for-entry,
    and both of those need every hashed field. A shipper that dropped one would still look
    like it worked right up until the copy had to stand on its own.
    """
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)

    for original, shipped in zip(local.entries, destination.read_entries("run-0"), strict=True):
        assert shipped == original, "a field did not survive shipping"
    verify_chain(destination.read_entries("run-0"))


def test_a_head_observation_is_added_never_replaced() -> None:
    """D5 — observations are append-only because an updatable head defeats the point.

    Each observation is the platform's own earlier claim about how long a stream was. If a
    later pass could overwrite an earlier one, an actor who truncated the local trail could
    lower the shipped claim to match and the truncation would disappear from both copies —
    the exact attack shipping the head exists to catch.
    """
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)
    local.append("run-0", 3)
    ship_pass(local=local, destination=destination)

    observed = sorted(o.highest_seq for o in destination.read_head_observations("run-0"))
    assert observed == [3, 6], f"the earlier claim did not survive the later one: {observed}"


# ---------------------------------------------------------------------- reconciliation


def test_a_broken_chain_at_the_destination_is_reported() -> None:
    """SC-002 — the second copy has to stand alone, so its own integrity is checked.

    Reconciliation compares two copies; if the destination's copy is itself incoherent, the
    comparison has no ground to stand on and says so rather than quietly treating a damaged
    witness as a sound one.
    """
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)
    broken = destination.entries[("run-0", 2)]
    destination.entries[("run-0", 2)] = broken.model_copy(update={"prev_hash": "0" * 64})

    report = reconcile(local=local, destination=destination)

    assert "destination_chain_broken" in findings_by_kind(report)


def test_agreeing_copies_report_no_findings() -> None:
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)

    report = reconcile(local=local, destination=destination)

    assert report.ok
    assert report.posture == "in_force"
    assert report.coverage_since is not None, "FR-017: the attested range must be stated"


def test_a_rewritten_local_entry_is_named_by_stream_and_sequence() -> None:
    """SC-003 — identified, not merely sensed."""
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)
    local.entries[2] = local.entries[2].model_copy(update={"entry_hash": "rewritten"})

    report = reconcile(local=local, destination=destination)

    assert [(f.kind, f.seq) for f in report.findings] == [("entry_mismatch", 2)]


def test_a_rewritten_payload_is_caught_even_with_the_hash_column_left_intact() -> None:
    """The rewrite that a hash-column comparison misses — and a live row caught first.

    This is the attack an administrator actually commits: one UPDATE against `payload`. The
    `entry_hash` column still holds its original value, so the two copies make identical
    claims about themselves while holding different evidence. A reconciler comparing the
    claims reports agreement, which is the worst possible answer — it is the platform
    certifying the tampering.

    Written after the enclave row failed. The double had been tampering by editing the hash,
    which no attacker needs to do, and it made a broken comparison look correct.
    """
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)
    local.entries[2] = local.entries[2].model_copy(update={"payload": {"rewritten": True}})

    report = reconcile(local=local, destination=destination)

    assert [(f.kind, f.seq) for f in report.findings] == [("entry_mismatch", 2)]


def test_the_consistent_truncation_is_caught_by_the_shipped_head() -> None:
    """SC-004 — the rewrite that defeats every LOCAL mechanism at once.

    Delete the newest entries and lower the head to match: the chain verifies perfectly and
    the head agrees with it, because the actor who can rewrite one can rewrite both. The
    destination's earlier head observation is the witness that survives.
    """
    local, destination = _prepared(entries=5)
    ship_pass(local=local, destination=destination)

    local.entries = [e for e in local.entries if e.seq < 2]
    local.heads["run-0"] = (1, local.entries[-1].entry_hash)

    report = reconcile(local=local, destination=destination)

    assert "local_truncated" in findings_by_kind(report)


def test_entries_not_yet_shipped_are_backlog_rather_than_divergence() -> None:
    """FR-013 / SC-008 — the case that would otherwise cry wolf on every concurrent run.

    Entries above the watermark have not been offered to the destination yet. Reporting
    their absence as divergence would make every reconcile during active writing red, and
    a check that is always red is a check nobody reads.
    """
    local, destination = _prepared(entries=6)
    ship_pass(local=local, destination=destination)
    local.append("run-0", 3)  # written after the pass — legitimately not shipped

    report = reconcile(local=local, destination=destination)

    assert report.ok, f"lag was reported as divergence: {report.findings}"
    assert report.backlog == 3


def test_an_entry_missing_below_the_watermark_is_divergence() -> None:
    """The other side of the same line: confirmed delivered, and now absent."""
    local, destination = _prepared()
    ship_pass(local=local, destination=destination)
    del destination.entries[("run-0", 1)]

    report = reconcile(local=local, destination=destination)

    assert "missing_at_destination" in findings_by_kind(report)


def test_no_destination_reports_absent_rather_than_protected() -> None:
    """FR-009 / SC-006 — the posture an estate without a second copy actually has.

    Stated, never defaulted. A platform that reported anything else here would be claiming a
    control it does not have, which is the failure mode this feature exists to correct one
    level up.
    """
    local, _ = _prepared()

    report = reconcile(local=local, destination=None)

    assert report.posture == "absent"
    assert report.destination_verified == "unverified"


def test_an_unverified_or_non_compliant_probe_never_reports_in_force() -> None:
    """FR-020b — a control the platform has not exercised must not read as one it has."""
    local, _ = _prepared()

    cases: list[tuple[DestinationVerification, str]] = [
        ("verified", "in_force"),
        ("non_compliant", "non_compliant"),
        ("unverified", "unverified"),
    ]
    for verification, expected in cases:
        destination = FakeDestination(verification=verification)
        ship_pass(local=local, destination=destination)
        report = reconcile(local=local, destination=destination)
        assert report.posture == expected, f"{verification} produced posture {report.posture}"


def test_every_posture_states_a_reason_and_only_one_of_them_claims_protection() -> None:
    """T025/T026 — four postures, distinguishable by what they say, not just by their names.

    A status line reading `NON_COMPLIANT` tells an operator something is wrong. It does not
    tell them their second copy is one their own administrators can rewrite, which is the
    sentence that gets it fixed. The reasons are asserted distinct because a shared or
    defaulted string would quietly make the four postures interchangeable in the one place a
    human actually reads them.
    """
    local, _ = _prepared()
    reports = [reconcile(local=local, destination=None)]
    probes: list[DestinationVerification] = ["verified", "non_compliant", "unverified"]
    for verification in probes:
        destination = FakeDestination(verification=verification)
        ship_pass(local=local, destination=destination)
        reports.append(reconcile(local=local, destination=destination))

    reasons = [posture_reason(r) for r in reports]
    assert len(set(reasons)) == 4, "two postures report the same reason"
    assert [r.posture for r in reports] == ["absent", "in_force", "non_compliant", "unverified"]
    claiming = [r.posture for r in reports if r.posture == "in_force"]
    assert claiming == ["in_force"], "more than one posture claimed tamper-evidence"
