# SPDX-License-Identifier: Apache-2.0
"""M16, FR-013, SC-009 — every capability is reachable, or recorded as deliberately not.

**Merge-blocking, and it is not about 040.** It is here because 040 is the feature that made
the second instance visible, and because it costs very little beside the rest of the work.

Two capabilities have shipped defined-and-unreachable behind passing rows — 036's `run_program`
and 038's authoring trio — months apart, both found by accident. The rows that should have
caught them could not: they drove the implementation directly, so they passed every day the
capability could not be reached. This row asks the only question those could not, which is
whether anything can actually get to it.
"""

from __future__ import annotations

import pytest
from tests.unit.capability_inventory import (
    DELIBERATELY_UNREACHABLE,
    Withheld,
    defined_capabilities,
    registered_capabilities,
    stale_ledger_entries,
    unaccounted,
)


def test_every_defined_capability_is_reachable_or_recorded() -> None:
    """The row itself. A capability in neither set fails the merge."""
    offenders = unaccounted()
    assert not offenders, (
        f"these capabilities are defined and cannot be reached, and nothing says why: "
        f"{offenders}. Either register them, or add an entry to DELIBERATELY_UNREACHABLE "
        f"naming the reason and the record that decided it. This has shipped twice — a "
        f"capability nobody can reach is not a bug on its own, but nobody knowing which it "
        f"is has been one both times."
    )


def test_the_ledger_has_not_gone_stale() -> None:
    """The other direction, and it rots faster.

    An entry claiming a capability is *deliberately unreachable* when a run can now reach it
    is a record that has quietly become false — the exact failure this repository's roadmap
    warns about in its own Next section, where three entries described a platform shape that
    had not been true for months.
    """
    stale = stale_ledger_entries()
    assert not stale, (
        f"these ledger entries no longer describe the platform: {stale}. Each is either now "
        f"registered — in which case the entry is a false record and should be deleted — or "
        f"no longer defined at all, in which case it is describing something that does not "
        f"exist."
    )


def test_every_ledger_entry_names_a_reason_and_a_record() -> None:
    """An entry is a decision, not a TODO, and the difference is whether it cites something."""
    for name, withheld in DELIBERATELY_UNREACHABLE.items():
        assert isinstance(withheld, Withheld)
        assert withheld.reason.strip(), f"{name} is withheld for no stated reason"
        assert withheld.record.strip(), (
            f"{name} is withheld by no record. 'Nobody has got to this yet' and 'somebody "
            f"decided this' are different states, and only the second belongs here."
        )


def test_the_sweep_finds_the_capabilities_that_are_actually_there() -> None:
    """The sweep is what keeps the ledger honest, so its own reach is asserted.

    A sweep that silently found nothing would make the row above vacuously green — the
    failure mode of every check that compares two sets it computed itself.
    """
    defined = defined_capabilities()
    assert "run_program" in defined, (
        "the sweep no longer finds the capability whose absence produced ADR-0065 — it has "
        "stopped reading the shape tool names are declared in, and every row here is now "
        "measuring an empty set against another empty set"
    )
    assert {"author_file", "read_subject", "open_proposal"} <= set(defined), (
        "the sweep no longer finds 038's authoring capabilities"
    )
    assert "vault_write" in registered_capabilities(), (
        "the assembled registry resolves nothing — the reachable side has gone empty"
    )


def test_row_the_check_can_lose(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Prove M16 can fail**: remove a ledger entry, and the check must trip.

    A reachability guard that cannot lose is the same defect wearing a checkmark, which is
    precisely what the two shipped instances looked like from outside.
    """
    without_run_program = {
        name: value for name, value in DELIBERATELY_UNREACHABLE.items() if name != "run_program"
    }
    monkeypatch.setattr(
        "tests.unit.capability_inventory.DELIBERATELY_UNREACHABLE", without_run_program
    )

    offenders = unaccounted()
    assert "run_program" in offenders, (
        "with its ledger entry removed, `run_program` is defined, unreachable, and unrecorded "
        "— and the check did not notice. It cannot catch the third instance either."
    )


def test_row_the_stale_check_can_lose(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Prove the staleness check can fail**: claim something reachable is withheld."""
    lying = dict(DELIBERATELY_UNREACHABLE)
    lying["vault_write"] = Withheld(reason="a claim that is not true", record="none")
    monkeypatch.setattr("tests.unit.capability_inventory.DELIBERATELY_UNREACHABLE", lying)

    assert "vault_write" in stale_ledger_entries(), (
        "the ledger claimed a reachable capability was deliberately withheld and the staleness "
        "check agreed with it — a record that cannot be caught being false is not a record"
    )
