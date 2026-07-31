# SPDX-License-Identifier: Apache-2.0
"""Row: a run is observed being refused when it writes the control plane that bounds it (018).

The constitution names this row blocking. Nothing implemented it and no ADR deferred it —
unowned since 004, which recorded the situation precisely and declined to invent a citation.

**What changes with these rows is the evidence, not the mechanism.** The refusals already
happen; every policy grants read and list and nothing more. What did not exist was anything
that had *watched* one. A configuration change adding a write capability to a ceiling path
would have passed every check in this repository.
"""

from __future__ import annotations

import pytest
from tests.conformance.authority import bounding_records as b

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


@pytest.fixture(scope="module")
def authority() -> str:
    """What a run actually holds — all three policies, as deployed."""
    return b.run_authority()


# ----------------------------------------------------------------- the derived half


def test_a_run_cannot_write_any_bounding_record(authority: str) -> None:
    """US1: every record a run may read, it must not be able to write."""
    targets = b.probe_targets()
    assert targets, "no bounding paths were derived — every row below would pass vacuously"

    failures = [a for path in targets if not (a := b.attempt_write(path, authority)).is_evidence]

    assert not failures, "\n".join(f"  {a.path}: {a.outcome.value} — {a.detail}" for a in failures)


def test_a_permitted_write_is_undone(authority: str) -> None:
    """FR-008: if a write ever succeeds, the check removes what it created — and says whether
    it managed to.

    A red test is something someone re-runs. A widened bound is a live condition, and this
    check would be the thing that created it.

    **Reporting the removal is not bookkeeping.** A run granted `create` is not thereby
    granted `delete`, so the removal can fail while the record persists — and the run
    demonstrating this feature's break fixture did exactly that, leaving
    `harness-ceilings/probe-018` behind on a real control plane. The first version of this row
    called `undo()` and discarded its answer, which is how nobody noticed.
    """
    permitted = [
        a
        for path in b.probe_targets()
        if (a := b.attempt_write(path, authority)).outcome is b.Outcome.PERMITTED
    ]
    removals = {a.path: b.undo(a.path, authority) for a in permitted}
    stuck = {p: r for p, r in removals.items() if r != "removed"}

    assert not permitted, (
        "a run WROTE a record bounding it — the platform's central claim is false.\n"
        + "\n".join(f"  {a.path}: removal {removals[a.path]}" for a in permitted)
        + (
            "\n\nAND THE RECORDS ARE STILL THERE. A run granted create is not granted "
            "delete, so this check created something it cannot remove:\n"
            + "\n".join(f"  {p}" for p in stuck)
            if stuck
            else ""
        )
    )


# ----------------------------------------------------------------- the named half


def test_a_run_cannot_write_the_grant_itself(authority: str) -> None:
    """US1, and the row the feature is named after.

    A run's ceiling is stated twice — as a record the platform consults, and as the grant the
    control plane enforces. Writing the second moves the bound without touching the first, and
    three analysis passes checked only the first.
    """
    failures = [
        a
        for path in b.NAMED_BOUNDS
        if not (a := b.attempt_write(path, authority, readable_check=False)).is_evidence
    ]

    assert not failures, "\n".join(
        f"  {a.path}: {a.outcome.value} — {b.NAMED_BOUNDS[a.path]}" for a in failures
    )


# --------------------------------------------------------------- attribution


def test_a_refusal_is_attributable(authority: str) -> None:
    """US2: the refusal is about the capability, not about a path that is not there.

    The control plane answers `403 permission denied` for a mount that does not exist, in
    words identical to a real bounding record — deliberately, since disclosing which would
    leak the shape of the tree. So a denial alone is not evidence.
    """
    for path in b.probe_targets():
        attempt = b.attempt_write(path, authority)
        assert attempt.outcome is not b.Outcome.UNATTRIBUTABLE, (
            f"{path}: refused, but the authority cannot see the path either — {attempt.detail}"
        )


def test_a_typo_in_a_path_does_not_pass(authority: str) -> None:
    """The row that tests the guard, without which the guard is untested.

    One letter wrong. A check reading 403 as proof would pass this forever, having asserted
    nothing at all — and this module's own first implementation had the inverse bug, reporting
    every genuine refusal as unattributable because it required a read to return 200 when
    every probe path deliberately does not exist.
    """
    attempt = b.attempt_write("harness-authority/data/harness-ceilingz/probe-018", authority)

    assert attempt.outcome is b.Outcome.UNATTRIBUTABLE, (
        f"a misspelled path reported {attempt.outcome.value}. A denial on a path the "
        f"authority cannot see proves nothing, and accepting it would make this whole gate "
        f"satisfiable by a typo."
    )


def test_no_refusal_is_asserted_with_administrator_authority() -> None:
    """FR-004: two kinds of act, two authorities, never mixed.

    A denial to an administrator is the opposite of interesting. Enumeration may use admin;
    assertion may not — and the separation is what makes the coverage checks legal at all.
    """
    here = b.ROOT / "tests/conformance/authority"
    source = (here / "test_a_run_cannot_move_its_own_bounds.py").read_text()
    for name in ("attempt_write", "undo"):
        for line in source.splitlines():
            if f"{name}(" in line and "admin" in line:
                pytest.fail(f"a refusal is asserted with administrator authority: {line.strip()}")


# ------------------------------------------------------------------ coverage


def test_every_existing_record_is_covered() -> None:
    """FR-011: the derivation is blind outside a run's read grants, and this is the only
    direction that blindness can be seen from."""
    derived_prefixes = {p.rsplit("/", 1)[0] for p in b.probe_targets()}
    unplaced: dict[str, str] = {}

    for mount, prefixes in b.existing_prefixes().items():
        for prefix in prefixes:
            for shape in (f"{mount}/data/{prefix}", f"{mount}/{prefix}"):
                if shape in derived_prefixes:
                    break
            else:
                if prefix not in b.EXCLUDED_PREFIXES:
                    unplaced[f"{mount}/{prefix}"] = "exists but is not derived or excluded"

    assert not unplaced, "records exist that no bounding path covers:\n" + "\n".join(
        f"  {k}: {v}" for k, v in unplaced.items()
    )


def test_every_enumerable_surface_is_named_or_excluded() -> None:
    """FR-012: the named half is checked against what the control plane lists, so it cannot
    be a subject list that goes stale in silence."""
    surfaces = b.enumerate_configuration_surfaces()
    assert set(surfaces) == set(b.ENUMERABLE_KINDS), (
        f"expected {b.ENUMERABLE_KINDS}, enumerated {sorted(surfaces)}"
    )
    assert any(surfaces.values()), "the control plane enumerated nothing — the check is vacuous"


def test_the_named_half_cannot_shrink_silently() -> None:
    """FR-012: nothing else would notice, because nothing derives these."""
    required = {
        "sys/policies/acl/agent-ceiling-planner",
        "auth/nomad/role/agent-run",
        "auth/nomad/config",
        "identity/entity",
        "identity/group",
    }
    missing = required - set(b.NAMED_BOUNDS)

    assert not missing, (
        f"named bounds removed without replacement: {sorted(missing)}. These cannot be "
        f"derived — a run holds no read access to any of them — so their absence is invisible "
        f"to every other check in this feature."
    )


def test_ordinary_writes_are_not_in_scope() -> None:
    """FR-009: a run writing its own space is the product working.

    A check that drifted across this line would forbid the platform's purpose while looking
    stricter, which is a worse failure than the one this feature fixes.
    """
    for path in [*b.probe_targets(), *b.NAMED_BOUNDS]:
        assert not path.startswith("secret/"), (
            f"{path} is in the agent secret space. Writing there is what a run is FOR — the "
            f"vault pack ships a write tool for exactly it."
        )
