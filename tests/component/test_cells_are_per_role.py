# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the same pack and model, qualified to summarize, refused to write.

**The cheapest possible test of the dimension ADR-0039 exists to add.** Cells are
(pack × model × role); the third axis is the whole of that ADR. A reader keying on
`(pack, model)` and ignoring `role` passes every other matrix row in this repository while
permitting a model to *make changes* because it was qualified to write summaries.

That failure is silent in the worst way: the model is real, the cell is real, the
qualification happened. Only the *role* is wrong, and nothing else in the system would
notice.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.matrix import ROLES, parse_matrix_record, validate_binding_map

MODEL = "anthropic/claude-opus@5"


def _matrix(*roles: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "cells": [
            {"pack": "vault", "model": MODEL, "role": r, "qualified_by": "fixture"} for r in roles
        ],
    }


def test_one_model_qualified_to_summarize_is_refused_for_write() -> None:
    cells = parse_matrix_record(_matrix("summarize"))

    validate_binding_map({"summarize": f"vault:{MODEL}:summarize"}, cells, agent_definition_id="a")

    with pytest.raises(ResolutionRefused) as caught:
        validate_binding_map({"write": f"vault:{MODEL}:write"}, cells, agent_definition_id="a")
    assert caught.value.reason_code == "unqualified_cell"


@pytest.mark.parametrize("qualified", sorted(ROLES))
def test_qualifying_one_role_qualifies_exactly_that_role(qualified: str) -> None:
    """Every role, so no single pairing passes by coincidence.

    Parameterised rather than written once because "summarize does not qualify write" could
    hold while some other pair leaked. The property is that qualification is per-role, not
    that one particular pair is separated.
    """
    cells = parse_matrix_record(_matrix(qualified))
    reference = f"vault:{MODEL}:{qualified}"

    validate_binding_map({qualified: reference}, cells, agent_definition_id="a")

    for other in sorted(ROLES - {qualified}):
        with pytest.raises(ResolutionRefused):
            validate_binding_map({other: f"vault:{MODEL}:{other}"}, cells, agent_definition_id="a")


def test_a_cell_reference_bound_to_the_wrong_role_refuses() -> None:
    """The sharper case: a *qualified* reference, bound under a different role's key.

    `{"write": "vault:model:summarize"}` names a cell that genuinely exists and is genuinely
    green. Only the role it is being used for is wrong, so a check that merely confirmed the
    reference resolves would accept it.
    """
    cells = parse_matrix_record(_matrix("summarize"))
    with pytest.raises(ResolutionRefused) as caught:
        validate_binding_map(
            {"write": f"vault:{MODEL}:summarize"}, cells, agent_definition_id="applier"
        )
    assert caught.value.reason_code == "unqualified_cell"
    assert "summarize" in str(caught.value), "the refusal does not say which role the cell holds"


def test_all_five_roles_can_be_bound_when_all_five_are_qualified() -> None:
    """SC-014: a definition can be bound end to end without an unqualified reference."""
    cells = parse_matrix_record(_matrix(*sorted(ROLES)))
    binding_map = {role: f"vault:{MODEL}:{role}" for role in sorted(ROLES)}
    validate_binding_map(binding_map, cells, agent_definition_id="applier")


def test_a_role_outside_the_closed_vocabulary_refuses() -> None:
    """`ask | plan | write | judge | summarize` and nothing else.

    An open vocabulary would let a definition bind a role no suite scores, which is a cell
    qualified by nothing wearing a role's name.
    """
    cells = parse_matrix_record(_matrix("write"))
    with pytest.raises(ResolutionRefused) as caught:
        validate_binding_map({"deploy": f"vault:{MODEL}:write"}, cells, agent_definition_id="a")
    assert caught.value.reason_code == "malformed_record"
