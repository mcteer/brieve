# SPDX-License-Identifier: Apache-2.0
"""SC-008, FR-014 — 041's tier is consumed, not forked (042, US5).

**A promise asserted as a diff rather than as a claim.** 041's authoring tier is product-blind
on purpose: a Terraform module and a Vault policy are written identically, so a product feature
that forked the tier would prove the design wrong. The cheapest way to fork it is not a
deliberate copy — it is a small edit to a shared file that makes one product's path special,
and every other row in this feature would stay green through that.

**The baseline is the merge-base with the trunk, and it is resolved the way 043's R9 had to
learn.** `git merge-base main HEAD` works on a developer's clone and returns nothing in a PR
checkout, where `actions/checkout` leaves the trunk as a remote-tracking ref only. That row
passed locally and failed the fast lane; this one starts where that one ended up.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

#: 041's conformance files. Editing one to make this feature pass would be the gate tuning this
#: estate refuses — and would be invisible in a diff nobody was asked to read.
FROZEN = (
    "tests/conformance/authoring/test_governed_path.py",
    "tests/conformance/authoring/test_producing.py",
    "tests/conformance/authoring/test_proposing.py",
    "tests/conformance/authoring/test_publishing.py",
    "tests/conformance/authoring/test_provenance.py",
    "tests/conformance/authoring/test_containment.py",
    "tests/conformance/authoring/test_acquisition.py",
)


def _baseline_refs() -> list[str]:
    """Where the trunk might be named, in the order worth trying.

    `GITHUB_BASE_REF` first: a PR against a release branch has a different baseline and should
    compare against the one it is actually merging into. Then the local branch, then the
    remote-tracking ref — which is the only one that exists in a PR checkout.
    """
    base_ref = os.environ.get("GITHUB_BASE_REF", "").strip()
    candidates = ["main", "origin/main"]
    if base_ref:
        candidates = [base_ref, f"origin/{base_ref}", *candidates]
    return candidates


def _merge_base() -> str:
    """The baseline commit, or empty when no candidate resolves."""
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


def test_041s_conformance_rows_are_unedited() -> None:
    """SC-008 — measured as an empty diff, not asserted as an intention.

    Fails loudly when no baseline resolves rather than skipping: a row that cannot establish
    its baseline has not verified the promise it exists to verify, and reporting that as a
    pass is the shape this whole estate refuses.
    """
    base = _merge_base()
    assert base, (
        f"no merge-base against any of {_baseline_refs()}; the baseline this row needs does "
        f"not exist, so the promise it asserts is unverified — which is not a pass"
    )

    changed = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD", "--", *FROZEN],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()

    assert not changed, (
        f"{changed} are 041's conformance rows and this feature edited them. 041's tier is "
        f"consumed unchanged (FR-014); a row edited to accommodate a product is a gate tuned "
        f"to its subject."
    )


def test_the_frozen_list_names_files_that_exist() -> None:
    """A frozen list of files that moved would assert an empty diff over nothing.

    That is the quiet way this row stops working: the files get renamed, the diff finds no
    matches, and SC-008 passes forever without checking anything.
    """
    missing = [path for path in FROZEN if not (ROOT / path).exists()]

    assert not missing, (
        f"{missing} are named in this row's frozen list and do not exist. Update the list "
        f"deliberately — an unmatched path makes this check vacuous rather than failing."
    )


def test_exactly_one_publishing_path_is_registered() -> None:
    """FR-014's other half: this feature adds no second publisher.

    042 opens its proposals through `open_proposal` and 041's publisher. A second path would
    be two lifecycles for one act, and one of them would stop getting the attention the other
    receives — which is the argument `build_sweeper` already makes about resume dispatch.
    """
    from core.authoring import tool as authoring_tool

    registered = [name for name in dir(authoring_tool) if name.isupper() and "PROPOSAL" in name]

    assert registered == ["OPEN_PROPOSAL"], (
        f"the authoring tier names {registered} as proposal entry points; there is one act "
        f"of publishing and it has one name"
    )


def test_core_authoring_is_untouched_by_this_feature() -> None:
    """The product-blindness boundary, measured on the diff rather than trusted.

    One exception, and it is deliberate: `proposal.py` gains a GENERIC `evidence` field so the
    measured impact has a labelled section a reviewer can find. No Vault knowledge enters —
    042 supplies the lines from `surfaces/dispatch/policy_authoring.py`, and
    `test_core_is_product_blind` keeps asserting over the result.
    """
    base = _merge_base()
    assert base, "no baseline; see the row above"

    changed = subprocess.run(
        ["git", "diff", "--name-only", base, "HEAD", "--", "src/core/authoring/"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split()

    assert changed in ([], ["src/core/authoring/proposal.py"]), (
        f"this feature changed {changed} inside the product-blind authoring tier. Vault "
        f"knowledge belongs in the pack and the surfaces; the only permitted change here is "
        f"the generic evidence section on `Proposal`."
    )
