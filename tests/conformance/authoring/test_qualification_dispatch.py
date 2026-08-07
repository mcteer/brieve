# SPDX-License-Identifier: Apache-2.0
"""A18-A19 — the `write` cell is resolved through dispatch, not merely resolvable (041, US2).

FAKE_FABRIC_IS_FAULT_INJECTION = (
    "The matrix is resolved through the fake so a row can present an unqualified cell, a "
    "withdrawn one, and a qualified one — three states the production fabric would need three "
    "estates to produce."
)

038's `test_qualification.py` proves `resolve_write_cell` behaves. It had no caller. These rows
prove the resolution happens **on the path a dispatched authoring run takes**, which is what
FR-012 asks and what 026 found missing for `ask`: a capability that could run unqualified for
even one step is the gap, and the refusal must arrive before a provider is reached.
"""

from __future__ import annotations

import pytest

from core.authoring.tool import WRITE_ROLE, resolve_write_cell
from core.authority.errors import ResolutionRefused
from core.authority.matrix import QualifiedCell

FAKE_FABRIC_IS_FAULT_INJECTION = "Three matrix states a single estate could not present at once."

MODEL = "anthropic/claude-sonnet@5"
DEFINITION = "authoring-agent"


def _cell(*, role: str = WRITE_ROLE, withdrawn: bool = False) -> QualifiedCell:
    return QualifiedCell(
        pack="terraform",
        model=MODEL,
        role=role,  # type: ignore[arg-type]
        qualified_by="fixture",
        withdrawn=withdrawn,
    )


def test_row_a18_an_unqualified_cell_stops_the_run_by_governance() -> None:
    """A18 — `unqualified_cell`, never `provider_unavailable` (FR-012, SC-011).

    The two send an operator to different places: one to the matrix, one to a vendor's status
    page. 026 found exactly this conflation for `ask` and it was a constitutional gap in
    shipped code.
    """
    pinned = f"terraform:{MODEL}:write"

    with pytest.raises(ResolutionRefused) as exc:
        resolve_write_cell(
            pinned,
            {},  # the matrix holds no write cell at all
            available=frozenset({MODEL}),
            agent_definition_id=DEFINITION,
        )

    assert exc.value.reason_code in {"unqualified_cell", "no_qualified_fallback"}
    assert "provider" not in exc.value.reason_code


def test_row_a18_a_withdrawn_cell_is_distinguishable_from_an_absent_one() -> None:
    """Withdrawn is a decision somebody made; absent is a decision nobody made."""
    pinned = f"terraform:{MODEL}:write"

    with pytest.raises(ResolutionRefused) as exc:
        resolve_write_cell(
            pinned,
            {pinned: _cell(withdrawn=True)},
            available=frozenset({MODEL}),
            agent_definition_id=DEFINITION,
        )

    assert exc.value.reason_code in {"cell_withdrawn", "no_qualified_fallback"}


def test_row_a18_a_cell_qualified_for_another_role_does_not_qualify_writing() -> None:
    """ADR-0039's closed vocabulary: summarising well says nothing about changing things.

    This is the defect 038's Q1 found pre-existing — `resolve_with_fallback`'s pinned branch
    never checked the role its docstring promised, so a `plan` cell resolved for `write`.
    """
    pinned = f"terraform:{MODEL}:write"

    with pytest.raises(ResolutionRefused):
        resolve_write_cell(
            pinned,
            {pinned: _cell(role="plan")},
            available=frozenset({MODEL}),
            agent_definition_id=DEFINITION,
        )


def test_row_a19_a_qualified_cell_resolves_and_carries_its_evidence() -> None:
    """A19 — the bound cell names a scorer, because the `write` role has no judge (ADR-0063)."""
    pinned = f"terraform:{MODEL}:write"

    cell, fallback = resolve_write_cell(
        pinned,
        {pinned: _cell()},
        available=frozenset({MODEL}),
        agent_definition_id=DEFINITION,
    )

    assert cell.role == WRITE_ROLE
    assert fallback is None
    assert not cell.judge, (
        "the write role has no judge at all — both correctness gates are mechanical, so the "
        "regress terminates at the person who wrote the reference"
    )


def test_row_a19_promotion_refuses_a_write_cell_naming_no_scorer() -> None:
    """What qualified it lives on PROMOTION, not on the cell (measured, not assumed).

    `QualifiedCell` carries `judge` and no `scorer`; ADR-0063's field is a promotion argument.
    So the assertion that a write cell is earned belongs here, at the gate that refuses one
    naming neither — asserting it on the cell would have been asserting a field that does not
    exist.
    """
    from core.evals.promotion import PromotionRefused, promote_model_version
    from core.evals.suites import AUTHORING_REQUIRED_SUITES

    common = {
        "pack": "terraform",
        "model": MODEL,
        "role": WRITE_ROLE,
        "suites_passed": AUTHORING_REQUIRED_SUITES,
        "required_suites": AUTHORING_REQUIRED_SUITES,
        "qualified_by": "fixture",
    }

    with pytest.raises(PromotionRefused):
        promote_model_version(**common, judge="")  # type: ignore[arg-type]

    promoted = promote_model_version(
        **common,  # type: ignore[arg-type]
        judge="",
        scorer="authoring-reference-comparison",
    )
    assert promoted["scorer"] == "authoring-reference-comparison"
    assert not promoted.get("judge")


def test_the_entrypoint_gate_exists_and_refuses_before_any_step() -> None:
    """The dispatch-side gate, asserted by driving it rather than by reading it.

    `_refuse_unless_write_qualified` returns non-zero for an unresolvable cell. A row that
    only checked `resolve_write_cell` would be 038's row again — correct, and about a function
    nothing called.
    """
    from surfaces.dispatch.entrypoint import _refuse_unless_write_qualified

    class _NoMatrix:
        def resolve_binding_map(self, agent_definition_id: str) -> dict[str, str]:
            raise ResolutionRefused("no binding map", reason_code="unqualified_cell")

    assert (
        _refuse_unless_write_qualified(
            identity_fabric=_NoMatrix(),
            agent_definition_id=DEFINITION,
            correlation_id="corr-041-qual",
        )
        != 0
    ), "an authoring run whose write role is unqualified must not start"
