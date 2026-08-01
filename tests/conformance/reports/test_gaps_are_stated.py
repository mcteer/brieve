# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — a claim that cannot be reconciled is flagged, never softened (021, US2).

**This is the half that makes US1 worth anything.** A report that traces every claim it makes and
silently drops the ones it could not verify is more dangerous than one that never claimed to
verify anything — it terminates the investigation that would have found the problem, which is
ADR-0018's argument in one sentence.
"""

from __future__ import annotations

import ast
from pathlib import Path

from core.reports import ClaimStatus, ReportBasis, compile_report, validate
from tests.harness import recorded_runs as fixtures

ROOT = Path(__file__).resolve().parents[3]
OBSERVERS = frozenset({"vault_write"})


def test_an_unrecognised_record_is_stated_not_dropped() -> None:
    """FR-005 — silence is the failure mode.

    A compiler that ignores what it does not recognise gets **quieter as the trail gets richer**:
    every audit event added after it was written would vanish from every report, and nothing
    would go red. 020 added two members; the next feature will add more.
    """
    report = compile_report(
        fixtures.unrecognised_record(), run_id="run-fixture", observers=OBSERVERS, terminal=True
    )
    unreconciled = [c for c in report.claims if c.status is ClaimStatus.UNRECONCILED]
    assert unreconciled, (
        "a record type the compiler does not interpret produced no claim at all — it was "
        "dropped, which is the one outcome a reader cannot detect"
    )


def test_one_unreconcilable_claim_does_not_suppress_the_report() -> None:
    """FR-005, SC-003 — **the property whose absence looks like caution.**

    A compiler that refused to emit anything when one claim failed would read as conservative
    and would hide every other finding in the run. The unreconcilable claim is emitted *beside*
    the rest, not instead of it.
    """
    entries = fixtures.clean_run() + fixtures.unrecognised_record()[1:]
    report = compile_report(entries, run_id="run-fixture", observers=OBSERVERS, terminal=True)

    statuses = {c.status for c in report.claims}
    assert ClaimStatus.UNRECONCILED in statuses, "the unreconcilable claim is missing"
    assert statuses - {ClaimStatus.UNRECONCILED}, (
        "the report contains nothing but the unreconcilable claim — one bad claim suppressed "
        "everything else, which hides more than it protects"
    )
    assert ClaimStatus.OBSERVED in statuses, (
        "the confirmed effect stopped being reported because something else could not be reconciled"
    )


def test_validation_downgrades_a_claim_whose_evidence_is_absent() -> None:
    """FR-004 — validated *against* the record, not merely populated *from* it.

    The two are the same thing only while the compiler is correct, which is the assumption this
    removes. A claim citing evidence that is not among the entries it was compiled from becomes
    `unreconciled` — it is never dropped, and it never suppresses the rest.

    **Non-vacuous by construction**: validation runs against a deliberately narrowed entry set,
    so the row would pass trivially if `validate` returned its input unchanged and fails here
    when it does.
    """
    entries = fixtures.clean_run()
    report = compile_report(entries, run_id="run-fixture", observers=OBSERVERS, terminal=True)
    assert any(c.status is not ClaimStatus.UNRECONCILED for c in report.claims)

    # The records the claims cite are gone; every claim must degrade rather than stand.
    checked = validate(report, entries[:1])
    citing_removed = [
        c for c in checked.claims if not set(c.evidence) <= {f"{entries[0].correlation_id}#0"}
    ]
    assert citing_removed, "the fixture no longer exercises validation; nothing cited a gap"
    for claim in citing_removed:
        assert claim.status is ClaimStatus.UNRECONCILED, (
            f"claim {claim.statement!r} cites a record that is not present and still reads "
            f"{claim.status.value} — validation is not checking, only copying"
        )
    assert len(checked.claims) == len(report.claims), "validation dropped a claim"


def test_the_basis_is_stated() -> None:
    """FR-010 — a report says whether its own evidence verified.

    A report compiled from records nobody checked is a weaker claim than one compiled from
    records that were. `reconciled=None` is deliberately not `False`: no configured destination
    is a different fact from a reconciliation that failed, and collapsing them would report an
    unconfigured estate as a tampered one.
    """
    default = compile_report(fixtures.clean_run(), run_id="run-fixture", observers=OBSERVERS)
    assert default.basis.chain_verified is False
    assert default.basis.reconciled is None, (
        "an absent second copy reports as a failed reconciliation; those are different facts"
    )

    verified = compile_report(
        fixtures.clean_run(),
        run_id="run-fixture",
        observers=OBSERVERS,
        basis=ReportBasis(chain_verified=True, reconciled=True),
    )
    assert verified.basis.chain_verified is True
    assert verified.basis.reconciled is True


def test_the_scope_is_stated() -> None:
    """FR-012, ADR-0032 — what the report can and cannot evidence, never left to inference."""
    report = compile_report(fixtures.clean_run(), run_id="run-fixture", observers=OBSERVERS)
    assert report.scope, "the report states no scope at all"
    assert "run-end" in report.scope, (
        "the scope omits the limit most likely to be misread: observations are facts about "
        "run-end, and 'verified' invites a present tense the claim does not have"
    )


def test_two_reports_of_one_run_agree() -> None:
    """FR-014b — every claim, not merely the record-derived ones.

    **Cheap to assert only because of the Principle IV redesign.** Before read-back moved to run
    end, a report re-read products at request time and two reports could legitimately differ;
    the spec's first clarification said so. Now nothing is re-derived, so any disagreement means
    the compiler is not a function of the records.
    """
    first = compile_report(
        fixtures.clean_run(), run_id="run-fixture", observers=OBSERVERS, terminal=True
    )
    second = compile_report(
        fixtures.clean_run(), run_id="run-fixture", observers=OBSERVERS, terminal=True
    )
    assert first == second, (
        "two compilations of one run disagree; the compiler is carrying state or reading "
        "something outside its entries"
    )


def test_no_report_is_ever_persisted() -> None:
    """FR-014a — a negative property nothing else would catch.

    A report store added later would break no existing row, and FR-014's *nothing may read a
    report to decide anything* starts eroding the moment one exists to read. **Parsed, not
    grepped** — the words "save" and "store" appear in this module's own prose.
    """
    forbidden_calls = {"save", "append_event", "record_intent", "record_result", "execute"}
    offenders: list[str] = []
    for path in (ROOT / "src/core/reports").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name in forbidden_calls:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}: {name}")
    assert not offenders, (
        f"the report package writes something: {offenders}. A report is compiled on demand and "
        f"never stored — anything persisted is eventually read as a source, which is exactly "
        f"what FR-014 forbids."
    )
