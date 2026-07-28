# SPDX-License-Identifier: Apache-2.0
"""Enumerating agent definitions — what exists, and what this person may start.

The disclosure decision (C2) is the substance: a definition a subject cannot start still
appears, marked. Omitting it presents a world in which the agent does not exist, so nobody
thinks to ask for access — and "request access to the thing you cannot see" is not a
workflow.

It is a wider disclosure than this platform makes anywhere else, and the rows below assert
both of its bounds: never credential-issuance detail, and never a resolution failure
answered as an empty or unmarked list.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.types import AuthorityScope
from core.identity.types import AuthenticatedSubject, SubjectKind
from surfaces.api.definitions import AgentDefinitionView, definition_views


def _subject(user: str = "alice") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id=user,
        tenant_id="tenant-a",
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )


class Fabric:
    """A fabric with two definitions and per-subject scope."""

    def __init__(
        self,
        *,
        scopes: dict[str, AuthorityScope] | None = None,
        ceilings: dict[str, AuthorityScope] | None = None,
        definitions: list[str] | None = None,
        scope_raises: bool = False,
        list_raises: bool = False,
        unreadable: frozenset[str] = frozenset(),
    ) -> None:
        self._scopes = scopes or {}
        self._ceilings = ceilings or {}
        self._definitions = definitions if definitions is not None else ["planner", "applier"]
        self._scope_raises = scope_raises
        self._list_raises = list_raises
        self._unreadable = unreadable

    def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
        if self._scope_raises:
            raise ResolutionRefused("fabric down", reason_code="fabric_unreachable")
        return self._scopes.get(subject_user_id, AuthorityScope())

    def list_definitions(self) -> list[str]:
        if self._list_raises:
            raise ResolutionRefused("fabric down", reason_code="fabric_unreachable")
        return list(self._definitions)

    def resolve_ceiling(self, agent_definition_id: str) -> AuthorityScope:
        if agent_definition_id in self._unreadable:
            raise ResolutionRefused("no ceiling record", reason_code="missing_ceiling_record")
        return self._ceilings.get(agent_definition_id, AuthorityScope())


def _fabric(**kwargs: Any) -> Fabric:
    defaults: dict[str, Any] = {
        "scopes": {
            "alice": AuthorityScope(tool_names=frozenset({"echo", "plan", "apply"})),
            "bob": AuthorityScope(tool_names=frozenset({"echo"})),
        },
        "ceilings": {
            "planner": AuthorityScope(tool_names=frozenset({"echo", "plan"})),
            "applier": AuthorityScope(tool_names=frozenset({"apply"})),
        },
    }
    defaults.update(kwargs)
    return Fabric(**defaults)


def test_two_subjects_see_the_same_definitions_marked_differently() -> None:
    """SC-008. The same world, different doors — which is the disclosure decision working."""
    alice = definition_views(subject=_subject("alice"), fabric=_fabric())
    bob = definition_views(subject=_subject("bob"), fabric=_fabric())

    assert [v.agent_definition_id for v in alice] == [v.agent_definition_id for v in bob]
    assert {v.agent_definition_id: v.may_start for v in alice} == {
        "planner": True,
        "applier": True,
    }
    # Bob holds only `echo`, which overlaps planner and not applier.
    assert {v.agent_definition_id: v.may_start for v in bob} == {
        "planner": True,
        "applier": False,
    }


def test_an_unstartable_definition_is_shown_rather_than_hidden() -> None:
    """The whole of C2 in one assertion.

    Bob cannot start `applier`. He can see it exists, which is what lets him ask.
    """
    views = definition_views(subject=_subject("bob"), fabric=_fabric())

    applier = next(v for v in views if v.agent_definition_id == "applier")
    assert applier.may_start is False


def test_partial_overlap_counts_as_startable() -> None:
    """Intersection non-empty, not subset.

    A subject covering part of a ceiling can start that agent with a narrower request —
    002 refuses only requests that EXCEED scope. Requiring subset would tell people they
    cannot use something they can.
    """
    fabric = _fabric(
        scopes={"carol": AuthorityScope(tool_names=frozenset({"plan"}))},
        ceilings={"planner": AuthorityScope(tool_names=frozenset({"echo", "plan"}))},
        definitions=["planner"],
    )

    views = definition_views(subject=_subject("carol"), fabric=fabric)

    assert views[0].may_start is True


def test_no_overlap_at_all_is_not_startable() -> None:
    """The other side, so the intersection rule is not trivially always-true."""
    fabric = _fabric(
        scopes={"carol": AuthorityScope(tool_names=frozenset({"echo"}))},
        ceilings={"applier": AuthorityScope(tool_names=frozenset({"apply"}))},
        definitions=["applier"],
    )

    assert definition_views(subject=_subject("carol"), fabric=fabric)[0].may_start is False


def test_no_credential_issuance_detail_reaches_the_caller() -> None:
    """FR-014, asserted by key inspection rather than by reading the constructor.

    The view is a closed model, so a field could only appear if someone added one — and
    this is the row that would notice.
    """
    view = definition_views(subject=_subject("alice"), fabric=_fabric())[0]
    serialised = view.model_dump_json()

    for forbidden in ("ceiling_polic", "allowed_paths", "secret/", "policy"):
        assert forbidden not in serialised, (
            f"{forbidden!r} reached a caller — the credential-issuance jurisdiction is not "
            "this surface's to disclose"
        )
    assert set(view.model_dump()) == {"agent_definition_id", "description", "owner", "may_start"}


def test_an_unresolvable_subject_scope_refuses() -> None:
    """FR-018. Not an empty list, not an unmarked one.

    Both read as fail-closed and are wrong answers about a person's authority: an empty
    list says "nothing exists", an unmarked one says "we know what you can do".
    """
    with pytest.raises(ResolutionRefused):
        definition_views(subject=_subject(), fabric=_fabric(scope_raises=True))


def test_an_unlistable_registry_refuses_rather_than_reporting_none() -> None:
    """ "No agents exist" and "we could not look" produce the same screen otherwise."""
    with pytest.raises(ResolutionRefused):
        definition_views(subject=_subject(), fabric=_fabric(list_raises=True))


def test_a_definition_with_no_readable_ceiling_is_shown_as_unstartable() -> None:
    """Neither hidden nor promised.

    Hiding it would be the omission this surface exists to avoid; claiming it startable
    would be a promise the platform cannot keep.
    """
    views = definition_views(
        subject=_subject("alice"), fabric=_fabric(unreadable=frozenset({"applier"}))
    )

    applier = next(v for v in views if v.agent_definition_id == "applier")
    assert applier.may_start is False
    assert isinstance(applier, AgentDefinitionView)


def test_an_empty_registry_is_an_empty_list_not_an_error() -> None:
    """Nothing registered is an answer."""
    assert definition_views(subject=_subject(), fabric=_fabric(definitions=[])) == []
