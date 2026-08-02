# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a binding refuses more often than it resolves, and each refusal is named.

The rows worth reading are the ones where a plausible record does **not** authorise: a cell
qualified for another role, a cell the matrix has withdrawn, a source nobody bound. Each is a way
an ask could quietly reach a model an operator never approved.
"""

from __future__ import annotations

import pytest

from core.authority.ask_binding import (
    AskAuthority,
    AskBinding,
    parse_ask_binding_record,
    resolve_ask_cell,
)
from core.authority.errors import ResolutionRefused
from core.authority.matrix import MatrixFallback, QualifiedCell, parse_matrix_record

MODEL = "anthropic/claude-opus@5"
GUIDANCE_CELL = f"vault:{MODEL}:ask"
ESTATE_CELL = f"terraform:{MODEL}:ask"


def _record(**cells: str) -> dict[str, object]:
    return {"schema_version": 1, **cells}


def _matrix(*refs: str, withdrawn: bool = False, role: str = "ask") -> dict[str, object]:
    return {
        "schema_version": 1,
        "cells": [
            {
                "pack": ref.split(":")[0],
                "model": ref.split(":")[1],
                "role": role,
                "qualified_by": "fixture",
                "judge": "seed",
                "withdrawn": withdrawn,
            }
            for ref in refs
        ],
    }


# ------------------------------------------------------------------ parsing (T004)


def test_a_well_formed_record_parses() -> None:
    binding = parse_ask_binding_record(
        _record(guidance_cell=GUIDANCE_CELL, estate_cell=ESTATE_CELL)
    )
    assert binding.cell_for("guidance") == GUIDANCE_CELL
    assert binding.cell_for("estate") == ESTATE_CELL


def test_either_cell_may_be_omitted() -> None:
    """An operator binding one source and not the other is saying "not yet" legibly."""
    assert parse_ask_binding_record(_record(guidance_cell=GUIDANCE_CELL)).estate_cell == ""
    assert parse_ask_binding_record(_record(estate_cell=ESTATE_CELL)).guidance_cell == ""


def test_both_omitted_is_well_formed_and_binds_nothing() -> None:
    """Well-formed, and refuses everything — which is a decision, not a malformed record."""
    binding = parse_ask_binding_record(_record())
    assert binding == AskBinding()


@pytest.mark.parametrize("version", [None, 0, 2, "1"])
def test_an_unsupported_or_absent_schema_version_refuses(version: object) -> None:
    """Absent and newer land in the same place — the ceiling's rule.

    A record with no version is either older than versioning or hand-written, and both are cases
    where guessing is how a binding gets misread.
    """
    record: dict[str, object] = {"guidance_cell": GUIDANCE_CELL}
    if version is not None:
        record["schema_version"] = version
    with pytest.raises(ResolutionRefused) as refused:
        parse_ask_binding_record(record)
    assert refused.value.reason_code == "unsupported_schema_version"


def test_a_cell_naming_another_role_refuses_at_parse() -> None:
    """A mis-authored binding fails when written about, not when first asked through.

    And the substance: a green `plan` cell licenses planning. Roles exist precisely so one
    qualification does not license everything.
    """
    with pytest.raises(ResolutionRefused) as refused:
        parse_ask_binding_record(_record(guidance_cell=f"vault:{MODEL}:plan"))
    assert refused.value.reason_code == "malformed_record"


def test_a_malformed_cell_reference_refuses() -> None:
    with pytest.raises(ResolutionRefused) as refused:
        parse_ask_binding_record(_record(estate_cell="not-a-reference"))
    assert refused.value.reason_code == "malformed_record"


# ------------------------------------------------------------------ resolution (T005)


def _resolve(
    binding: AskBinding, matrix: dict[str, object], source: str = "guidance"
) -> tuple[QualifiedCell, MatrixFallback | None]:
    return resolve_ask_cell(
        source, binding, parse_matrix_record(matrix), available=frozenset({MODEL})
    )


def test_a_bound_and_green_cell_resolves_pinned() -> None:
    cell, fallback = _resolve(AskBinding(guidance_cell=GUIDANCE_CELL), _matrix(GUIDANCE_CELL))
    assert cell.reference == GUIDANCE_CELL
    assert fallback is None


def test_no_binding_for_this_source_refuses_unbound() -> None:
    """SC-003a's mechanism: guidance bound does not license estate."""
    with pytest.raises(ResolutionRefused) as refused:
        _resolve(AskBinding(guidance_cell=GUIDANCE_CELL), _matrix(GUIDANCE_CELL), source="estate")
    assert refused.value.reason_code == "unbound_ask_source"


def test_a_withdrawn_cell_refuses_exactly_like_an_absent_one() -> None:
    """SC-002. Inherited from `resolve_with_fallback` and asserted anyway.

    Inherited properties that nobody asserts are the ones that quietly stop being inherited.
    """
    with pytest.raises(ResolutionRefused) as no_cell:
        _resolve(AskBinding(guidance_cell=GUIDANCE_CELL), _matrix())
    with pytest.raises(ResolutionRefused) as withdrawn:
        _resolve(AskBinding(guidance_cell=GUIDANCE_CELL), _matrix(GUIDANCE_CELL, withdrawn=True))

    # EQUALITY is the requirement, not a particular code. `resolve_with_fallback` collapses every
    # exhausted-candidates case to `no_qualified_fallback` — absent, withdrawn, and wrong-role
    # alike — which satisfies SC-002 more strongly than naming one code would: the two are
    # indistinguishable at the seam, so no caller can learn which it was.
    assert no_cell.value.reason_code == withdrawn.value.reason_code == "no_qualified_fallback"


def test_a_cell_qualified_for_another_role_does_not_authorise(  # noqa: D103
) -> None:
    """SC-003, at resolution — the parse-time guard catches the binding, this catches the matrix.

    Both are needed: the binding could name `...:ask` while the matrix qualifies that pack/model
    only for `plan`, and nothing in the reference string would show it.
    """
    with pytest.raises(ResolutionRefused) as refused:
        _resolve(AskBinding(guidance_cell=GUIDANCE_CELL), _matrix(GUIDANCE_CELL, role="plan"))
    # Same collapse as the withdrawn case above: the cell is not qualified for `ask`, no other is
    # either, so candidates are exhausted. The surface maps every such refusal to the caller- and
    # trail-facing `unqualified_cell` disposition.
    assert refused.value.reason_code == "no_qualified_fallback"


def test_an_unavailable_model_falls_back_to_another_qualified_cell() -> None:
    """FR-006's mechanism: the fallback pair, with both cells named."""
    other = "vault:anthropic/claude-sonnet@5:ask"
    matrix = parse_matrix_record(_matrix(GUIDANCE_CELL, other))
    cell, fallback = resolve_ask_cell(
        "guidance",
        AskBinding(guidance_cell=GUIDANCE_CELL),
        matrix,
        available=frozenset({"anthropic/claude-sonnet@5"}),
    )
    assert cell.reference == other
    assert fallback is not None
    assert fallback.pinned_cell == GUIDANCE_CELL
    assert fallback.used_cell == other


def test_no_qualified_alternative_refuses_rather_than_reaching_further() -> None:
    """FR-007. There is no path from unavailability to an unqualified model."""
    with pytest.raises(ResolutionRefused):
        resolve_ask_cell(
            "guidance",
            AskBinding(guidance_cell=GUIDANCE_CELL),
            parse_matrix_record(_matrix(GUIDANCE_CELL)),
            available=frozenset({"anthropic/some-other-model@1"}),
        )


# ------------------------------------------------------------------ the authority collaborator


def test_an_unreadable_fabric_is_not_an_empty_one() -> None:
    """SC-004. An outage is not a governance state.

    Treating the two alike would make every model look unqualified during an incident, sending an
    operator to argue with governance instead of to the outage.
    """

    def _broken() -> dict[str, object]:
        raise ConnectionError("vault is down")

    authority = AskAuthority(read_binding=_broken, read_matrix=lambda: _matrix())
    with pytest.raises(ResolutionRefused) as refused:
        authority.resolve("guidance", available=frozenset({MODEL}))
    assert refused.value.reason_code == "fabric_unreachable"

    empty = AskAuthority(read_binding=lambda: _record(), read_matrix=lambda: _matrix())
    with pytest.raises(ResolutionRefused) as unbound:
        empty.resolve("guidance", available=frozenset({MODEL}))
    assert unbound.value.reason_code == "unbound_ask_source"


def test_the_authority_resolves_end_to_end() -> None:
    authority = AskAuthority(
        read_binding=lambda: _record(guidance_cell=GUIDANCE_CELL),
        read_matrix=lambda: _matrix(GUIDANCE_CELL),
    )
    cell, fallback = authority.resolve("guidance", available=frozenset({MODEL}))
    assert cell.reference == GUIDANCE_CELL and fallback is None
