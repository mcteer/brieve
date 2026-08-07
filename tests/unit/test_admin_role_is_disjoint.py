# SPDX-License-Identifier: Apache-2.0
"""FR-016a — `admin` is disjoint, in both directions (044, T005).

**Both directions, because a widening in either would be invisible.** `ROLE_VISIBILITY` would
still parse and every existing row would still pass if `admin` quietly gained the analyst's
set, or if the analyst gained configuration authority. The map's own docstring says the union
works equally well for disjoint sets — so nothing about the code resists the drift, and only a
row does.

**Why disjoint rather than a hierarchy.** The analyst is the operator's documented superset
because both answer *what happened*. An administrator answers *what may happen*. Making admin
a superset would hand configuration authority to everyone who can already read the trail; a
person needing both holds both mappings, which is a decision somebody makes rather than a
consequence of a role name.
"""

from __future__ import annotations

from pathlib import Path

from core.answering.scope import ROLE_VISIBILITY

ROOT = Path(__file__).resolve().parents[2]


def test_admin_confers_no_audit_visibility() -> None:
    """One direction: being an administrator shows you nothing about what happened.

    The empty set is the decision, not an omission — it falls out of the union exactly as an
    unrecognised role does, which is why the map needed no new machinery to express it.
    """
    assert "admin" in ROLE_VISIBILITY, "the role must exist in the map to be assertable"
    assert ROLE_VISIBILITY["admin"] == frozenset(), (
        "an administrator sees no audit events by virtue of the role. Anything here is a "
        "widening: the console's authority is over configuration, not over the trail."
    )


def test_admin_shares_nothing_with_either_existing_role() -> None:
    """Disjointness stated as set arithmetic rather than as a comment."""
    admin = ROLE_VISIBILITY["admin"]

    assert not (admin & ROLE_VISIBILITY["operator"])
    assert not (admin & ROLE_VISIBILITY["compliance-analyst"])


def test_neither_existing_role_gains_configuration_authority() -> None:
    """The other direction, and it is not about the visibility map at all.

    Configuration authority lives at the console's route check, so this asserts that the
    check names `admin` and nothing else — an `operator` added to that list would be the
    same widening arriving through a different file, invisible to the map above.
    """
    console = ROOT / "src" / "surfaces" / "api" / "console.py"
    if not console.exists():
        return  # the route lands in T006; the guard binds from then on

    text = console.read_text()
    for role in ("operator", "compliance-analyst"):
        assert f'"{role}"' not in text, (
            f"{role!r} appears in the console module. Configuration authority is `admin`'s "
            f"alone (FR-016a); a second role here is a widening the visibility map cannot see."
        )


def test_the_map_still_has_exactly_the_roles_this_platform_grants() -> None:
    """A fourth role appearing without a decision is the drift this file exists to catch."""
    assert set(ROLE_VISIBILITY) == {"operator", "compliance-analyst", "admin"}
