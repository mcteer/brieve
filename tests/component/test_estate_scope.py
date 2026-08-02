# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — scope is a union that can be empty, and empty is a refusal.

ADR-0035's scope algebra, tested at the level it is computed. The rows that matter are the ones
where scope produces *less*: an unknown role, and no roles at all.
"""

from __future__ import annotations

from core.answering.scope import ROLE_VISIBILITY, visible_event_types
from core.audit.schema import AuditEventType


def test_a_known_role_sees_its_own_set() -> None:
    assert visible_event_types(["operator"]) == ROLE_VISIBILITY["operator"]


def test_two_roles_union_rather_than_intersect() -> None:
    """Holding more roles means seeing more.

    The alternative — intersection — would mean that granting somebody an extra role could
    *narrow* what they could already see, which nobody would predict from being granted something.
    """
    both = visible_event_types(["operator", "compliance-analyst"])
    assert both == ROLE_VISIBILITY["operator"] | ROLE_VISIBILITY["compliance-analyst"]
    assert both >= ROLE_VISIBILITY["operator"]


def test_the_two_seeded_roles_differ() -> None:
    """SC-001 is unarrangeable unless the map has at least two visibility classes (analysis P4-2).

    A map with one class would satisfy every other row here and quietly refute ADR-0035's central
    claim — two people asking the same question get the same answer.
    """
    operator = visible_event_types(["operator"])
    analyst = visible_event_types(["compliance-analyst"])
    assert analyst - operator, "the analyst must see something the operator does not"
    assert AuditEventType.AUTHORITY_ISSUED in analyst - operator


def test_an_unknown_role_contributes_nothing() -> None:
    """It cannot widen scope, and it is not an error — it simply supplies no visibility."""
    assert visible_event_types(["not-a-role"]) == frozenset()
    assert visible_event_types(["operator", "not-a-role"]) == ROLE_VISIBILITY["operator"]


def test_no_roles_produces_the_empty_set_the_caller_must_refuse_on() -> None:
    """FR-004c's computed half. The refusal itself is the caller's — see the module docstring.

    Empty here must never be read as "sees everything"; the read path is what turns this into a
    refusal *before* any query runs, so a subject with no mapped roles leaves no access record.
    """
    assert visible_event_types([]) == frozenset()
    assert not visible_event_types([])


def test_every_mapped_type_is_a_real_audit_event_type() -> None:
    """A mapping naming a nonexistent event type would narrow a query to nothing and read as scope.

    Cheap to assert, and the failure it prevents is a silent one: the query would return zero rows
    and the answer would decline, looking exactly like "your scope contains nothing".
    """
    known = set(AuditEventType)
    for role, types in ROLE_VISIBILITY.items():
        unknown = types - known
        assert not unknown, f"{role} maps to types that do not exist: {unknown}"
