# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a question's focus narrows the read and can never widen it.

**What focus is for**: a question about runs was answered from 1,000 of 63,947 entries, of which
sixty were run records. The read bounded by row count over undifferentiated types, so the estate's
noisiest activity took the window. Focus names the types a question is about so the bound can be
applied per type.

**What focus must never become**: a way to see more. `visible_event_types` decides what a role may
read at all; focus decides what is *relevant*. Composed as an intersection, the second can only
ever reduce the first — and these rows assert that at the composition, not by reading the code.

The distinction matters because the two are easy to confuse in exactly one direction: a focus that
*added* a type would look like a relevance improvement and be a scope defect.
"""

from __future__ import annotations

from core.answering.focus import FOCUS_TERMS, focus_types
from core.answering.scope import visible_event_types
from core.audit.schema import AuditEventType

#: The five questions that failed against the deployed platform on 2026-08-02.
QUESTIONS_THAT_FAILED = (
    "Which tools were used?",
    "What did the planner agent do?",
    "Were any secrets read?",
    "Which agents are active?",
    "What ran today?",
)


def _composed(question: str, roles: frozenset[str]) -> frozenset[AuditEventType]:
    """What the ask path passes to the read: focus ∩ visible, falling back to visible.

    Written here as the rows' subject rather than imported, because it is the composition the
    surface performs and these rows exist to pin its properties before the surface relies on them.
    """
    visible = visible_event_types(roles)
    focus = focus_types(question)
    if focus is None:
        return visible
    narrowed = focus & visible
    return narrowed or visible


def test_every_question_that_failed_names_the_types_its_answer_needs() -> None:
    """US2's premise: these questions are about something the trail records."""
    unfocused = [q for q in QUESTIONS_THAT_FAILED if focus_types(q) is None]
    assert unfocused == [], f"no focus recognised for: {unfocused}"


def test_a_runs_question_focuses_run_records() -> None:
    focus = focus_types("What ran today?")
    assert focus is not None
    assert AuditEventType.RUN_START in focus
    assert AuditEventType.EFFECT_OBSERVED not in focus, (
        "the question's focus includes the noisiest type in the estate, which is the starvation "
        "this feature exists to end"
    )


def test_a_tools_question_focuses_tool_records() -> None:
    focus = focus_types("Which tools were used?")
    assert focus == frozenset({AuditEventType.TOOL_CHOSEN, AuditEventType.TOOL_OUTCOME})


def test_a_question_naming_several_things_takes_the_union() -> None:
    """*"Which runs failed?"* is about runs AND failures; either alone answers half of it."""
    focus = focus_types("Which runs failed?")
    assert focus is not None
    assert AuditEventType.RUN_START in focus
    assert AuditEventType.ENFORCEMENT_ERROR in focus


def test_the_singular_plural_rule_is_routings_and_not_this_tables() -> None:
    """The distinction that decides whether a question starves.

    `routing.py` excludes singular nouns because they misroute documentation questions into a
    scoped read. This table is consulted only after routing has already chosen the estate, so a
    singular term here cannot cause a read that would not otherwise happen — it only decides which
    records an already-authorised read returns.

    Conflating the two rules left *"What did the planner agent do?"* — which routes correctly on
    `did` — focusing nothing and starving at volume, which is exactly what this module exists to
    prevent.
    """
    from core.answering.routing import ESTATE_NOUNS, ESTATE_TERMS

    assert "agent" in FOCUS_TERMS
    assert "agent" not in ESTATE_TERMS and "agent" not in ESTATE_NOUNS


def test_an_unrecognised_question_focuses_nothing_rather_than_guessing() -> None:
    """`None` is the honest answer and the safe one.

    A wrong narrowing produces an empty answer that looks exactly like an honest one — the same
    failure mode the router's false negatives had, which is why the table is small and the
    fallback is "read as before".
    """
    assert focus_types("What happened with the thing yesterday?") is None


# ------------------------------------------------------------------ composition: FR-005


def test_focus_can_only_narrow_what_a_role_may_see() -> None:
    """The property that keeps a relevance feature from becoming a scope defect.

    Asserted across every focus term rather than on a chosen example, because the failure would
    arrive through whichever term somebody added next.
    """
    for role in ("operator", "compliance-analyst"):
        visible = visible_event_types(frozenset({role}))
        for term in FOCUS_TERMS:
            composed = _composed(f"what about {term}", frozenset({role}))
            assert composed <= visible, (
                f"focus for {term!r} reached outside what {role!r} may see: {composed - visible}"
            )


def test_a_denials_question_now_narrows_for_an_operator() -> None:
    """The row that guarded the visibility decision, updated as the deliberate step it forced.

    Its previous form asserted `AUTHORITY_DENIED not in visible` for an operator, with a message
    saying the premise would need revisiting when FR-009's question was answered. 031 answered
    it: what happened to YOUR runs is yours to ask about, so an operator's *"Which runs were
    denied?"* now focuses denial records that are genuinely visible, and the intersection
    narrows instead of falling back.
    """
    operator = frozenset({"operator"})
    focus = focus_types("Which runs were denied?")
    visible = visible_event_types(operator)

    assert focus is not None
    assert AuditEventType.AUTHORITY_DENIED in focus
    assert AuditEventType.AUTHORITY_DENIED in visible, (
        "031 granted operators their own runs' denials; if this was deliberately reverted, "
        "revert the focus row, ADR-0059's note and the scope entry together"
    )
    assert AuditEventType.AUTHORITY_DENIED in _composed("Which runs were denied?", operator)

    # The fallback still exists for a focus with NO visible overlap — grants stay analyst-only.
    assert AuditEventType.AUTHORITY_ISSUED not in visible
    assert _composed("Who was granted access?", operator) == visible


def test_an_empty_visible_set_is_never_widened_by_a_focus() -> None:
    """025's rule, re-asserted where the new code could have eroded it.

    A role that may see nothing must still see nothing. The fallback above returns `visible` when
    the intersection is empty — and when `visible` is itself empty, that is still empty, which the
    ask path turns into a refusal before any read happens.
    """
    assert visible_event_types(frozenset({"nobody"})) == frozenset()
    assert _composed("Which tools were used?", frozenset({"nobody"})) == frozenset()


def test_focus_never_introduces_a_type_the_trail_does_not_define() -> None:
    """A typo here would be a filter matching nothing — an empty answer that looks honest."""
    for term, types in FOCUS_TERMS.items():
        assert types, f"{term!r} maps to no types, which would narrow a read to nothing"
        for kind in types:
            assert isinstance(kind, AuditEventType), f"{term!r} maps to a non-member: {kind!r}"
