# SPDX-License-Identifier: Apache-2.0
"""Every `ClaimStatus` value is produced by at least one fixture.

**This row was rewritten before it was written.** Its first draft said "assert no two values are
collapsible", which analysis pass 3 refused: there is no operational meaning to "collapsible",
nothing distinguishes a passing implementation from a failing one, and a row that cannot fail is
a governance hole with a green checkmark.

Reachability catches both failures the original was reaching for:

* a status that exists and can never be produced — nothing in the enum is aspirational;
* a status silently merged into another — its fixture stops producing it and this goes red.

It iterates the enum rather than a hand-written list, so a value added later and never handled
fails here rather than passing because the list was not updated. That distinction is the same one
that made SC-004a wrong for two analysis passes: a literal list drifts from the thing it lists.
"""

from __future__ import annotations

from tests.harness import recorded_runs as fixtures

from core.reports import ClaimStatus, compile_report

#: Which fixture reaches each status, and under what compile arguments.
#:
#: `observers` and `terminal` are part of the fixture: "the product could not be asked" and
#: "there was nobody to ask" are the same entries with a different registry, and a killed run is
#: the same entries with `terminal=False`. Encoding them here keeps the fixtures honest — a
#: fixture that only reached its status because of a compile flag would otherwise look like it
#: reached it on its own.
REACHES: dict[ClaimStatus, tuple] = {
    ClaimStatus.FROM_RECORD: (fixtures.clean_run, frozenset({"vault_write"}), True),
    ClaimStatus.OBSERVED: (fixtures.clean_run, frozenset({"vault_write"}), True),
    ClaimStatus.CONTRADICTED: (fixtures.contradicted_effect, frozenset({"vault_write"}), True),
    ClaimStatus.UNVERIFIED_UNREACHABLE: (
        fixtures.unreachable_product,
        frozenset({"vault_write"}),
        True,
    ),
    ClaimStatus.UNVERIFIED_NO_OBSERVER: (
        fixtures.tool_without_an_observer,
        frozenset(),
        True,
    ),
    ClaimStatus.UNVERIFIED_NOT_OBSERVED: (
        fixtures.killed_before_terminal,
        frozenset({"vault_write"}),
        False,
    ),
    ClaimStatus.UNRECONCILED: (fixtures.unrecognised_record, frozenset(), True),
}


def _statuses(fixture, observers, terminal) -> set[ClaimStatus]:
    report = compile_report(fixture(), run_id="run-fixture", observers=observers, terminal=terminal)
    return {claim.status for claim in report.claims}


def test_every_status_has_a_fixture_that_reaches_it() -> None:
    """The enum is the source; the mapping must cover it.

    Checked before the per-status assertions so a newly added value fails here — naming the
    gap — rather than raising a `KeyError` inside a loop.
    """
    missing = set(ClaimStatus) - set(REACHES)
    assert not missing, (
        f"{sorted(s.value for s in missing)} exist in ClaimStatus and no fixture reaches them. "
        "A status nothing can produce is either dead vocabulary or an unhandled case; both are "
        "worth a red row rather than a silent pass."
    )


def test_each_status_is_actually_produced() -> None:
    """Every value is reachable from the fixture claiming to reach it."""
    unreachable = []
    for status, (fixture, observers, terminal) in sorted(REACHES.items()):
        if status not in _statuses(fixture, observers, terminal):
            unreachable.append(f"{status.value} (via {fixture.__name__})")
    assert not unreachable, (
        f"these statuses were not produced by the fixture said to reach them: {unreachable}. "
        "Either the compiler stopped emitting one — most likely by collapsing it into a "
        "neighbouring status — or the fixture drifted."
    )


def test_the_detector_can_fail() -> None:
    """The row itself is falsifiable — asserted, not assumed.

    `AGENTS.md`: every assertion must be able to fail. A fixture that reaches no statuses at all
    would make the two rows above vacuous if they were written as "nothing is missing", so this
    proves the measurement responds to its input.
    """
    assert _statuses(fixtures.clean_run, frozenset({"vault_write"}), True)
    assert ClaimStatus.CONTRADICTED not in _statuses(
        fixtures.clean_run, frozenset({"vault_write"}), True
    ), "a clean run must not produce a contradicted claim, or the fixtures prove nothing"
