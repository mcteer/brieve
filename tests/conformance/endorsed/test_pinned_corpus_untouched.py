# SPDX-License-Identifier: Apache-2.0
"""E22 — the pinned corpus is not weakened, asserted from the first commit (045, T001).

**This row lands FIRST and that is its design.** US6's guarantee is that `corpus.py` was never
edited — research R1 chose a second, parallel corpus precisely so "nothing weakened" would be a
property of what was not touched rather than a discipline about how it was. A diff row that
first ran in the last phase would have nothing to say about the phases before it, so this one
runs from the beginning and speaks about every commit after.

**Why the temptation is real.** The obvious design is a `tenant_id` threaded through
`load_corpus`, and it is wrong: one reader would then serve two trust models — content vendored
through the supply chain and content endorsed at runtime — and every check on the pinned side
would grow a branch for the endorsed side. `corpus.py`'s own docstring calls citation resolution
*"the single most important check in this feature"*. Extending it is exactly how it gets
loosened.

**The baseline is the merge-base, resolved the way 043's R9 had to learn.** `git merge-base main
HEAD` works on a developer's clone and returns nothing in a PR checkout, where `actions/checkout`
leaves the trunk as a remote-tracking ref only.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: The pinned corpus's reader. **This feature does not edit it.** If a change here is ever
#: genuinely required, that is a design decision that belongs in a record, not a diff.
PINNED_READER = "src/core/answering/corpus.py"

#: The answering and citation rows that must keep asserting exactly what they asserted before.
#: A feature that made customer content citable by making *everything* easier to cite would have
#: traded this platform's most important check for a capability, and these are what notice.
FROZEN = (
    PINNED_READER,
    "tests/conformance/answering/test_relevance_gate.py",
    "tests/conformance/answering/test_relevance_regression.py",
    "tests/conformance/answering/test_the_ground_discloses.py",
    "tests/component/test_answering.py",
)

#: `test_answering.py` is frozen for its CITATION and corpus rows, and 045 legitimately extends
#: its ask-record exact-key-set row with `endorsed_version` (T018) — the seventh feature in
#: seven to do so. That extension is admitted here by name so the freeze keeps its teeth
#: everywhere else in the file rather than being dropped wholesale.
PERMITTED_EDITS = {"tests/component/test_answering.py"}


def _baseline_refs() -> list[str]:
    base_ref = os.environ.get("GITHUB_BASE_REF", "").strip()
    candidates = ["main", "origin/main"]
    if base_ref:
        candidates = [base_ref, f"origin/{base_ref}", *candidates]
    return candidates


def _merge_base() -> str:
    for ref in _baseline_refs():
        result = subprocess.run(
            ["git", "merge-base", ref, "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    return ""


def _changed(base: str, *paths: str) -> list[str]:
    return subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()


def test_the_pinned_corpus_reader_is_not_edited() -> None:
    """The row this file exists for, and the strictest of them.

    `corpus.py` is untouched, full stop. The endorsed reader lives beside it — a second
    implementation of the same contract — so this is not "we were careful with the shared
    reader", it is "there is no shared reader".
    """
    base = _merge_base()
    assert base, (
        f"no merge-base against any of {_baseline_refs()}; the baseline this row needs does "
        f"not exist, so the promise it asserts is unverified — which is not a pass"
    )

    assert not _changed(base, PINNED_READER), (
        f"{PINNED_READER} was edited. 045's whole design (research R1) is that customer "
        f"content is a SECOND corpus behind the same contract, so that the platform's most "
        f"important check is not extended to content the platform does not control. An edit "
        f"here is a design change and belongs in a record before it belongs in a diff."
    )


def test_the_answering_and_citation_rows_are_unedited() -> None:
    """E22 — the promise asserted as a diff rather than as a claim (FR-014, SC-008).

    One file is permitted to change and is named: `test_answering.py`'s exact-key-set row
    admits `endorsed_version` (T018). Naming the exception is what keeps the freeze meaningful
    for the other four — a blanket exemption, or quietly dropping the file, would leave this
    row asserting nothing about the rows that matter most.
    """
    base = _merge_base()
    assert base, "no baseline; see the row above"

    frozen = [path for path in FROZEN if path not in PERMITTED_EDITS]
    edited = _changed(base, *frozen)

    assert not edited, (
        f"{edited} are the answering and citation rows this feature promised not to touch. "
        f"They caught real regressions; editing one to accommodate customer content is the "
        f"gate tuning this estate refuses."
    )


def test_the_frozen_list_names_files_that_exist() -> None:
    """The quiet way this row stops working: the files move and the diff matches nothing.

    A path that no longer exists makes the check vacuous rather than red — it passes forever
    while asserting nothing, which is the failure mode 040's capability inventory was built to
    end and 042's protected-set scan repeats.
    """
    missing = [path for path in FROZEN if not (ROOT / path).exists()]

    assert not missing, (
        f"{missing} are named in this row's frozen list and do not exist. Update the list "
        f"deliberately — an unmatched path makes this check vacuous rather than failing."
    )


def test_no_endorsed_machinery_lives_inside_the_pinned_reader() -> None:
    """Belt and braces with the diff row, and it survives a rebase the diff row would miss.

    The diff compares against a merge-base; a rebase or a squash can move that. This asserts
    the property directly from the file's contents, so "the endorsed reader is beside the
    pinned one" holds regardless of what the history looks like.
    """
    source = (ROOT / PINNED_READER).read_text()

    for leaked in ("endorsed", "tenant_id", "EndorsedCorpus", "adopted_version"):
        assert leaked not in source, (
            f"{leaked!r} appears in {PINNED_READER}. The pinned reader knows nothing about "
            f"customer content by design — that is what makes US6 structural."
        )
