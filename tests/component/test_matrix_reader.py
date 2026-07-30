# SPDX-License-Identifier: Apache-2.0
"""The Qualified Model Matrix: what it accepts, and the four ways it refuses.

Two rows here are worth more than the rest.

**The per-role row** is the cheapest possible test of the dimension ADR-0039 exists to add,
and the one that fails loudly if the reader keys on `(pack, model)` and ignores `role` —
every other row in this file would still pass while a model qualified to `summarize` was
permitted to `write`.

**The identifier row** catches auto-tracking at the identifier rather than only at the
lookup. An alias or a bare name is a moving target; "latest" resolving differently next week
is auto-tracking whether or not anybody calls it that (FR-011).
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.matrix import (
    QualifiedCell,
    parse_matrix_record,
    resolve_with_fallback,
    validate_binding_map,
)

MODEL = "anthropic/claude-opus@5"
OTHER = "anthropic/claude-sonnet@5"


def _record(*cells: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": 1, "cells": list(cells)}


def _cell(role: str = "write", model: str = MODEL, **extra: Any) -> dict[str, Any]:
    return {"pack": "vault", "model": model, "role": role, "qualified_by": "fixture", **extra}


# --- Reading -----------------------------------------------------------------------------


def test_a_green_cell_resolves() -> None:
    cells = parse_matrix_record(_record(_cell()))
    assert cells[f"vault:{MODEL}:write"].qualified_by == "fixture"


def test_qualified_by_round_trips() -> None:
    """A cell must say whether it was qualified against a recording or a live model.

    SC-013: zero cells recorded as qualified without saying which. The distinction matters
    most for `write` — a model permitted to make changes, qualified against a replay.
    """
    cells = parse_matrix_record(_record(_cell(qualified_by="live")))
    assert cells[f"vault:{MODEL}:write"].qualified_by == "live"


def test_a_cell_must_say_how_it_was_qualified() -> None:
    with pytest.raises(ResolutionRefused) as caught:
        parse_matrix_record(_record({"pack": "v", "model": MODEL, "role": "write"}))
    assert caught.value.reason_code == "malformed_record"


def test_a_newer_schema_version_refuses_rather_than_being_guessed_at() -> None:
    """Absent and newer land in the same place, as `parse_ceiling_record` does it."""
    for version in (None, 2):
        with pytest.raises(ResolutionRefused) as caught:
            parse_matrix_record({"schema_version": version, "cells": []})
        assert caught.value.reason_code == "unsupported_schema_version"


def test_a_role_outside_the_closed_vocabulary_refuses() -> None:
    with pytest.raises(ResolutionRefused) as caught:
        parse_matrix_record(_record(_cell(role="deploy")))
    assert caught.value.reason_code == "malformed_record"


@pytest.mark.parametrize("model", ["claude", "anthropic/claude", "claude@5", "anthropic//c@5"])
def test_a_model_identifier_that_is_not_pinned_refuses_at_parse(model: str) -> None:
    """Caught at the identifier, not only at the lookup.

    A matrix that cannot express an alias cannot auto-track by accident.
    """
    with pytest.raises(ResolutionRefused) as caught:
        parse_matrix_record(_record(_cell(model=model)))
    assert caught.value.reason_code == "malformed_record"


def test_the_identifier_pattern_is_a_floor_and_not_a_guarantee() -> None:
    """The honest limit, asserted rather than left in a docstring.

    `anthropic/claude@latest` is structurally pinned and semantically a moving target. The
    pattern cannot tell a version from a word, so it accepts this — the guard against it is
    the per-cell qualification record and human review, not this regex.

    Documented by a row for the same reason the injection lens documents the phrasings it
    misses: a floor nobody has seen the shape of gets read as a ceiling. This row fails the
    day someone strengthens the pattern, which is when the docstring above should change.
    """
    cells = parse_matrix_record(_record(_cell(model="anthropic/claude@latest")))
    assert "anthropic/claude@latest" in {c.model for c in cells.values()}


# --- Binding maps ------------------------------------------------------------------------


def test_a_binding_to_a_qualified_cell_is_accepted() -> None:
    cells = parse_matrix_record(_record(_cell()))
    validate_binding_map({"write": f"vault:{MODEL}:write"}, cells, agent_definition_id="applier")


def test_an_unqualified_cell_is_refused_and_the_refusal_names_it() -> None:
    """Naming the cell is not decoration.

    "This definition is invalid" sends somebody to read the definition; naming the cell
    sends them to the matrix, which is where the fix is.
    """
    cells = parse_matrix_record(_record(_cell()))
    with pytest.raises(ResolutionRefused) as caught:
        validate_binding_map({"write": f"vault:{OTHER}:write"}, cells, agent_definition_id="a")
    assert caught.value.reason_code == "unqualified_cell"
    assert OTHER in str(caught.value)


def test_a_withdrawn_cell_is_refused_separately_from_an_absent_one() -> None:
    """Different reason codes because they are different problems.

    An absent cell was never qualified; a withdrawn one was qualified and then pulled — a
    model deprecated, a suite regressed, a bad result acted on. An investigator reading
    `cell_withdrawn` knows something changed; reading `unqualified_cell` they would think
    the definition was always wrong.
    """
    cells = parse_matrix_record(_record(_cell(withdrawn=True)))
    with pytest.raises(ResolutionRefused) as caught:
        validate_binding_map({"write": f"vault:{MODEL}:write"}, cells, agent_definition_id="a")
    assert caught.value.reason_code == "cell_withdrawn"


def test_the_same_pack_and_model_qualified_to_summarize_is_refused_for_write() -> None:
    """The dimension ADR-0039 adds, and the one a `(pack, model)` lookup would ignore.

    This is the cheapest possible test of the third dimension. A reader keying on pack and
    model alone passes every other row in this file while permitting a model to make changes
    because it was qualified to write summaries.
    """
    cells = parse_matrix_record(_record(_cell(role="summarize")))

    validate_binding_map({"summarize": f"vault:{MODEL}:summarize"}, cells, agent_definition_id="a")

    with pytest.raises(ResolutionRefused) as caught:
        validate_binding_map({"write": f"vault:{MODEL}:write"}, cells, agent_definition_id="a")
    assert caught.value.reason_code == "unqualified_cell"


# --- Fallback ----------------------------------------------------------------------------


def test_the_pinned_cell_is_used_when_available() -> None:
    cells = parse_matrix_record(_record(_cell()))
    cell, fallback = resolve_with_fallback(
        "write",
        f"vault:{MODEL}:write",
        cells,
        available=frozenset({MODEL}),
        agent_definition_id="a",
    )
    assert cell.model == MODEL
    assert fallback is None


def test_fallback_goes_to_another_qualified_cell_and_reports_it() -> None:
    """The recording is the load-bearing half.

    A fallback nobody can see is a definition that does not describe what ran.
    """
    cells = parse_matrix_record(_record(_cell(), _cell(model=OTHER)))
    cell, fallback = resolve_with_fallback(
        "write",
        f"vault:{MODEL}:write",
        cells,
        available=frozenset({OTHER}),
        agent_definition_id="a",
    )
    assert cell.model == OTHER
    assert fallback is not None
    assert fallback.pinned_cell == f"vault:{MODEL}:write"
    assert fallback.used_cell == f"vault:{OTHER}:write"


def test_fallback_never_reaches_an_unqualified_model() -> None:
    """SC-004, and the reason it is phrased as an absence.

    The unavailable model here IS qualified for `summarize`. A fallback that searched by
    pack and availability rather than by role would find it.
    """
    cells = parse_matrix_record(_record(_cell(), _cell(model=OTHER, role="summarize")))
    with pytest.raises(ResolutionRefused) as caught:
        resolve_with_fallback(
            "write",
            f"vault:{MODEL}:write",
            cells,
            available=frozenset({OTHER}),
            agent_definition_id="a",
        )
    assert caught.value.reason_code == "no_qualified_fallback"


def test_no_qualified_fallback_stops_with_the_reason_recorded() -> None:
    cells = parse_matrix_record(_record(_cell()))
    with pytest.raises(ResolutionRefused) as caught:
        resolve_with_fallback(
            "write",
            f"vault:{MODEL}:write",
            cells,
            available=frozenset(),
            agent_definition_id="applier",
        )
    assert caught.value.reason_code == "no_qualified_fallback"
    assert "applier" in str(caught.value)


def test_a_withdrawn_cell_is_not_a_fallback_candidate() -> None:
    cells = parse_matrix_record(_record(_cell(), _cell(model=OTHER, withdrawn=True)))
    with pytest.raises(ResolutionRefused) as caught:
        resolve_with_fallback(
            "write",
            f"vault:{MODEL}:write",
            cells,
            available=frozenset({OTHER}),
            agent_definition_id="a",
        )
    assert caught.value.reason_code == "no_qualified_fallback"


def test_the_fallback_payload_carries_what_an_investigator_needs() -> None:
    """ "A model decided something" and "the model that ran was not the one pinned" are
    different questions, and MATRIX_FALLBACK answers only the second."""
    cells = {
        f"vault:{OTHER}:write": QualifiedCell(
            pack="vault", model=OTHER, role="write", qualified_by="live"
        )
    }
    _, fallback = resolve_with_fallback(
        "write",
        f"vault:{MODEL}:write",
        cells,
        available=frozenset({OTHER}),
        agent_definition_id="a",
    )
    assert fallback is not None
    payload = fallback.as_payload(run_id="run-1")
    assert payload["run_id"] == "run-1"
    assert payload["role"] == "write"
    assert payload["reason"] == "unqualified_cell"
