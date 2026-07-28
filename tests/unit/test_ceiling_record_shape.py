# SPDX-License-Identifier: Apache-2.0
"""A ceiling record is understood completely or not at all.

**Half-understanding a ceiling means enforcing a subset of it**, and a subset of a ceiling
is a narrower ceiling — which sounds safe and is not: it silently breaks working agents
while telling nobody, and the same mechanism that narrows on one field would widen on
another the moment a future schema moves something.

So an unknown `schema_version` refuses. A record written by a newer platform is not a
record this one can partially parse; it is a record this one cannot read.
"""

from __future__ import annotations

import pytest

from core.authority.ceiling import SUPPORTED_SCHEMA_VERSION, parse_ceiling_record
from core.authority.errors import ResolutionRefused

KNOWN_TOOLS = frozenset({"echo", "plan", "apply"})
KNOWN_ACTIONS = frozenset({"product.workspace.read", "product.workspace.write"})


def _record(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "agent_definition_id": "planner-agent",
        "tool_names": ["echo", "plan"],
        "product_actions": ["product.workspace.read"],
    }
    base.update(overrides)
    return base


def test_a_well_formed_record_parses_to_a_scope() -> None:
    """The positive control. Without it, a parser that refused everything would pass."""
    scope = parse_ceiling_record(_record(), known_tools=KNOWN_TOOLS, known_actions=KNOWN_ACTIONS)

    assert scope.tool_names == frozenset({"echo", "plan"})
    assert scope.product_actions == frozenset({"product.workspace.read"})


def test_a_newer_schema_version_refuses() -> None:
    """Not "ignore the fields you know" — refuse."""
    with pytest.raises(ResolutionRefused) as caught:
        parse_ceiling_record(
            _record(schema_version=SUPPORTED_SCHEMA_VERSION + 1),
            known_tools=KNOWN_TOOLS,
            known_actions=KNOWN_ACTIONS,
        )

    assert caught.value.reason_code == "unsupported_schema_version"


def test_a_missing_schema_version_refuses() -> None:
    """Absent is not "assume the current one".

    A record with no version is either older than versioning or hand-written, and both are
    cases where guessing is how a ceiling gets misread.
    """
    record = _record()
    del record["schema_version"]

    with pytest.raises(ResolutionRefused) as caught:
        parse_ceiling_record(record, known_tools=KNOWN_TOOLS, known_actions=KNOWN_ACTIONS)

    assert caught.value.reason_code == "unsupported_schema_version"


def test_an_unknown_tool_refuses_and_names_it() -> None:
    """FR-005a. Naming it is the half that makes the refusal actionable."""
    with pytest.raises(ResolutionRefused) as caught:
        parse_ceiling_record(
            _record(tool_names=["echo", "teleport"]),
            known_tools=KNOWN_TOOLS,
            known_actions=KNOWN_ACTIONS,
        )

    assert caught.value.reason_code == "unknown_ceiling_entry"
    assert "teleport" in str(caught.value), (
        "the refusal did not name the unknown entry, so an operator reading it has no way "
        "to find which line of their configuration is wrong"
    )


def test_an_unknown_product_action_refuses_and_names_it() -> None:
    """The other half of the ceiling. A check covering only tools would miss it."""
    with pytest.raises(ResolutionRefused) as caught:
        parse_ceiling_record(
            _record(product_actions=["product.workspace.detonate"]),
            known_tools=KNOWN_TOOLS,
            known_actions=KNOWN_ACTIONS,
        )

    assert caught.value.reason_code == "unknown_ceiling_entry"
    assert "detonate" in str(caught.value)


def test_an_unknown_entry_is_never_silently_dropped() -> None:
    """The failure this row exists for, stated as the thing that must not happen.

    Dropping the entry produces a valid, narrower scope and no error — a change to
    authority that leaves no trace anywhere. It would pass every other assertion here.
    """
    with pytest.raises(ResolutionRefused):
        parse_ceiling_record(
            _record(tool_names=["echo", "plan", "teleport"]),
            known_tools=KNOWN_TOOLS,
            known_actions=KNOWN_ACTIONS,
        )


def test_an_empty_ceiling_is_legitimate() -> None:
    """Empty is a decision — "this definition may call nothing" — not a malformed record.

    Conflating the two would make the safest possible ceiling unrepresentable.
    """
    scope = parse_ceiling_record(
        _record(tool_names=[], product_actions=[]),
        known_tools=KNOWN_TOOLS,
        known_actions=KNOWN_ACTIONS,
    )

    assert scope.tool_names == frozenset()
    assert scope.product_actions == frozenset()
