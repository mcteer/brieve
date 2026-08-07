# SPDX-License-Identifier: Apache-2.0
"""The binding parser refuses a mis-roled cell in BOTH directions (043, T002).

**This file exists because the parser refused this feature's own record.** Before 043,
`parse_ask_binding_record` iterated the two sources and refused at parse any cell whose role was
not `ask` — *"a cell qualified for another role licenses that role, not this one."* The relevance
binding names a **judge** cell, so the record being extended would have rejected the field being
added to it. The analyze pass caught it; without these rows the fix could silently become a
one-directional loosening, which is the shape the original refusal exists to prevent.
"""

from __future__ import annotations

import pytest

from core.authority.ask_binding import (
    ASK_ROLE,
    RELEVANCE_ROLE,
    SUPPORTED_SCHEMA_VERSION,
    parse_ask_binding_record,
)
from core.authority.errors import ResolutionRefused

MODEL = "anthropic/claude-sonnet@5"


def _record(**cells: str) -> dict[str, object]:
    return {"schema_version": SUPPORTED_SCHEMA_VERSION, **cells}


def test_a_relevance_cell_naming_a_judge_is_accepted() -> None:
    """The field this feature adds, in the shape it must take."""
    binding = parse_ask_binding_record(
        _record(
            guidance_cell=f"vault:{MODEL}:{ASK_ROLE}",
            relevance_cell=f"vault:{MODEL}:{RELEVANCE_ROLE}",
        )
    )

    assert binding.guidance_cell == f"vault:{MODEL}:{ASK_ROLE}"
    assert binding.relevance_cell == f"vault:{MODEL}:{RELEVANCE_ROLE}"


def test_a_relevance_cell_naming_an_ask_refuses() -> None:
    """The first direction: answering well is not judging well.

    The gate renders a verdict on an answer. A cell qualified to produce answers has been
    measured on producing them, and this is the whole reason roles are a closed vocabulary
    rather than a suggestion.
    """
    with pytest.raises(ResolutionRefused) as exc:
        parse_ask_binding_record(_record(relevance_cell=f"vault:{MODEL}:{ASK_ROLE}"))

    assert exc.value.reason_code == "malformed_record"
    assert RELEVANCE_ROLE in str(exc.value)


def test_a_source_cell_naming_a_judge_still_refuses() -> None:
    """The second direction, and the one a loosening would quietly break.

    The pre-043 refusal protected the source fields. Making the check per-field must not turn
    it into a check that only fires for the new one.
    """
    with pytest.raises(ResolutionRefused) as exc:
        parse_ask_binding_record(_record(guidance_cell=f"vault:{MODEL}:{RELEVANCE_ROLE}"))

    assert exc.value.reason_code == "malformed_record"
    assert ASK_ROLE in str(exc.value)


@pytest.mark.parametrize("role", ["plan", "write", "summarize"])
def test_no_other_role_licenses_either_field(role: str) -> None:
    """One qualification licenses one role. Asserted across the rest of the vocabulary."""
    for field in ("guidance_cell", "estate_cell", "relevance_cell"):
        with pytest.raises(ResolutionRefused):
            parse_ask_binding_record(_record(**{field: f"vault:{MODEL}:{role}"}))


def test_an_absent_relevance_cell_parses_to_empty() -> None:
    """Absent is not malformed — it is *nobody decided*, which the surface names later."""
    binding = parse_ask_binding_record(_record(guidance_cell=f"vault:{MODEL}:{ASK_ROLE}"))
    assert binding.relevance_cell == ""


def test_a_malformed_reference_still_refuses_in_the_new_field() -> None:
    """The shape check did not get weaker for the field that was added."""
    with pytest.raises(ResolutionRefused) as exc:
        parse_ask_binding_record(_record(relevance_cell="vault:model-without-a-role"))
    assert exc.value.reason_code == "malformed_record"


def test_existing_records_parse_unchanged() -> None:
    """A record written before this feature is still a valid record."""
    binding = parse_ask_binding_record(
        _record(
            guidance_cell=f"vault:{MODEL}:{ASK_ROLE}",
            estate_cell=f"vault:{MODEL}:{ASK_ROLE}",
        )
    )
    assert binding.guidance_cell and binding.estate_cell
    assert binding.relevance_cell == ""
