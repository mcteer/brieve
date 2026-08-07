# SPDX-License-Identifier: Apache-2.0
"""C18 — absent means enabled, and that default is a compatibility guarantee (044, T004).

**The row that stops a dataclass default from reintroducing gap 0g.** Every ask-binding record
written before 044 carries no `relevance_enabled` field. If absence read as `False`, the
relevance gate would silently switch off across every estate the moment this field shipped —
answers assembled from true, cited, resolving claims about the wrong subject, exactly what 043
closed, reintroduced by a default value nobody would look at twice.

**Unbound and disabled are different states**, and this file keeps them apart. Unbound means
*nobody decided who judges* and refuses before availability is even considered (026's rule,
043's `relevance_unbound`). Disabled means *somebody decided not to judge* and answers with the
absence disclosed. A gap and a decision, and they send a reader to different places.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.ask_binding import (
    ASK_ROLE,
    RELEVANCE_ROLE,
    SUPPORTED_SCHEMA_VERSION,
    parse_ask_binding_record,
)
from core.authority.errors import ResolutionRefused

MODEL = "anthropic/claude-sonnet@5"
JUDGE = "anthropic/claude-opus@5"


def _record(**fields: Any) -> dict[str, Any]:
    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "guidance_cell": f"vault:{MODEL}:{ASK_ROLE}",
        "relevance_cell": f"vault:{JUDGE}:{RELEVANCE_ROLE}",
        **fields,
    }


def test_row_c18_a_record_without_the_field_is_enabled() -> None:
    """C18 — the compatibility guarantee, asserted rather than assumed.

    This is the shape of every binding record in every estate today. If it ever reads as
    disabled, 043's gate is off everywhere and nothing else in the suite would notice.
    """
    assert parse_ask_binding_record(_record()).relevance_enabled is True


def test_row_c18_an_explicit_false_disables() -> None:
    """The only way the gate turns off: somebody wrote it down."""
    assert parse_ask_binding_record(_record(relevance_enabled=False)).relevance_enabled is False


def test_row_c18_an_explicit_true_enables() -> None:
    """Round-trips, so an administrator turning the gate back on is honoured."""
    assert parse_ask_binding_record(_record(relevance_enabled=True)).relevance_enabled is True


@pytest.mark.parametrize("nonsense", ["no", "false", 0, None, ""])
def test_a_nonsense_value_reads_as_enabled(nonsense: Any) -> None:
    """The safe direction for a gate.

    `bool("false")` is `True` and `bool(0)` is `False` — a truthiness check would disable the
    gate for `0` and enable it for the string `"false"`, which is the wrong answer in both
    directions from a record somebody hand-edited. Only an explicit `false` disables.
    """
    assert parse_ask_binding_record(_record(relevance_enabled=nonsense)).relevance_enabled is True


def test_disabled_is_not_unbound() -> None:
    """The distinction the whole feature rests on.

    A disabled gate still names who *would* judge, so re-enabling needs no second decision —
    and an operator reading the record can tell "we turned it off" from "we never chose".
    """
    binding = parse_ask_binding_record(_record(relevance_enabled=False))

    assert binding.relevance_enabled is False
    assert binding.relevance_cell, (
        "disabling must not clear the bound judge; that would turn a reversible decision "
        "into a second one somebody has to remember to make"
    )


def test_the_toggle_does_not_weaken_the_parsers_role_check() -> None:
    """Adding a field must not become a way past the checks that were already there.

    043's parser refuses a relevance cell whose role is not `judge`, at parse rather than at
    resolution. A record that disables the gate is still a record, and still malformed if its
    cell is.
    """
    with pytest.raises(ResolutionRefused):
        parse_ask_binding_record(
            _record(relevance_enabled=False, relevance_cell=f"vault:{JUDGE}:{ASK_ROLE}")
        )
