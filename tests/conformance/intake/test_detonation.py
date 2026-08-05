# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the range, the separation, and the canaries (D1–D11).

**D5 is the load-bearing row of the whole feature.** Every other row here can pass while it
fails, and that combination is the vulnerability the gauntlet exists to inspect: an observer
that ingests candidate output *is* the injection surface.

The stub this contract exists to prevent is a detonation that runs nothing and reports clean
— which is why D1 asserts `tasks_run > 0` and D11 gives the corpus a floor.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from core.intake.detonation import (
    MIN_DENIED_ATTEMPTS,
    MIN_TASKS,
    CorpusRefused,
    GoldenTask,
    RunRecord,
    SeparationViolated,
    assert_corpus_floor,
    assert_no_candidate_content,
    compare,
)
from tests.fixtures.intake import (
    BASELINE,
    BEHAVES_IDENTICALLY,
    EXFILTRATES_CANARY,
    REACHES_FURTHER,
)

REPO = pathlib.Path(__file__).resolve().parents[3]
CORPUS = REPO / "corpus" / "golden-tasks" / "tasks.json"
RANGE_JOB = REPO / "infra" / "jobs" / "detonation-range.nomad.hcl"


def _tasks() -> list[GoldenTask]:
    raw = json.loads(CORPUS.read_text())["tasks"]
    return [GoldenTask(**t) for t in raw]


def test_both_versions_run_and_the_comparison_is_over_real_tasks() -> None:
    """D1 (FR-011, FR-014) — a comparison over zero tasks is no result wearing one."""
    result = compare(REACHES_FURTHER, BASELINE, tasks_run=len(_tasks()), observer="observer")
    assert result.tasks_run >= MIN_TASKS
    assert result.candidate_digest != result.baseline_digest

    with pytest.raises(CorpusRefused, match="zero tasks"):
        compare(REACHES_FURTHER, BASELINE, tasks_run=0, observer="observer")


def test_a_behavioural_difference_is_reported() -> None:
    """D2 — constructed, not hoped for. The fixture differs in a known way."""
    result = compare(REACHES_FURTHER, BASELINE, tasks_run=8, observer="observer")
    assert result.new_attempts == ["apply_to_production"]
    assert result.new_denials == ["apply_to_production"]


def test_an_identical_candidate_reports_no_difference() -> None:
    """D2's control — a comparison that always reported differences would assert nothing."""
    result = compare(BEHAVES_IDENTICALLY, BASELINE, tasks_run=8, observer="observer")
    assert result.new_attempts == [] and result.new_denials == []


def test_the_golden_corpus_meets_its_floor() -> None:
    """D11 (FR-011) — the corpus side of "detonation catches only what it provokes"."""
    assert_corpus_floor(_tasks())


def test_each_corpus_floor_clause_fails_on_its_own() -> None:
    """D11 — asserted per clause, on Q7's lesson about aggregate checks."""
    full = _tasks()
    with pytest.raises(CorpusRefused, match=f"the floor is {MIN_TASKS}"):
        assert_corpus_floor(full[: MIN_TASKS - 1])

    # Plenty of tasks, none of which provokes a denial.
    toothless = [GoldenTask(f"t{i}", "p", exercises_must_deny=(i == 0)) for i in range(12)]
    with pytest.raises(CorpusRefused, match=f"the floor is {MIN_DENIED_ATTEMPTS}"):
        assert_corpus_floor(toothless)

    # Denials but no must-deny case.
    unanchored = [GoldenTask(f"t{i}", "p", attempts_denied=(i < 3)) for i in range(10)]
    with pytest.raises(CorpusRefused, match="must-deny"):
        assert_corpus_floor(unanchored)


def test_specimen_and_observer_are_separate_identities() -> None:
    """D4 (FR-013) — two tasks, therefore two attested principals. Read, not inferred."""
    body = RANGE_JOB.read_text()
    assert 'task "specimen"' in body and 'task "observer"' in body, (
        "the range does not separate the specimen from the observer"
    )
    # Two identity blocks, one per task — the separation is structural, not a discipline.
    assert body.count("identity {") == 2, (
        f"expected one workload identity per role, found {body.count('identity {')}"
    )
    assert 'HARNESS_AUTHORITY_SOURCE = ""' in body, (
        "the range must hold no authority source at all — not a fake one (FR-015a)"
    )


def test_no_candidate_authored_content_reaches_the_observer() -> None:
    """D5 (FR-013, SC-005) — THE LOAD-BEARING ROW.

    The observer's input is a run RECORD, a type with no field for candidate output. Handing
    it anything else is refused at the seam, so somebody wanting a richer report must add a
    reviewable field to the record rather than passing the output through.
    """
    marker = "CANDIDATE-AUTHORED-MARKER-DO-NOT-INGEST"

    # The record type carries no candidate prose anywhere.
    record = RunRecord(digest="c" * 64, attempted=("read_module",), denied=())
    assert marker not in repr(record)

    comparison = compare(REACHES_FURTHER, BASELINE, tasks_run=8, observer="observer")
    assert marker not in repr(comparison), "candidate content reached the comparison"
    assert comparison.written_by == "observer", (
        "the comparison must record the OBSERVER's identity, never the specimen's"
    )

    # And the seam refuses candidate output outright.
    for hostile in (marker, {"stdout": marker}, [marker]):
        with pytest.raises(SeparationViolated):
            assert_no_candidate_content(hostile)


def test_a_canary_is_caught_mechanically() -> None:
    """D8 (SC-004) — nobody has to notice."""
    result = compare(EXFILTRATES_CANARY, BASELINE, tasks_run=8, observer="observer")
    assert result.canary_contacts == ["canary-alpha"]


def test_a_canarys_value_never_enters_the_record() -> None:
    """D9 — the record of a leak must not be a second copy of what leaked."""
    result = compare(EXFILTRATES_CANARY, BASELINE, tasks_run=8, observer="observer")
    for contact in result.canary_contacts:
        assert contact.startswith("canary-"), f"{contact!r} looks like a value, not an id"
        assert len(contact) < 40, "a canary identifier, never its content"


def test_benign_content_does_not_register_canary_contact() -> None:
    """D10 — a check firing on the word "secret" trains reviewers to ignore it."""
    result = compare(BASELINE, BASELINE, tasks_run=8, observer="observer")
    assert result.canary_contacts == []
