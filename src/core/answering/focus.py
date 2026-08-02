# SPDX-License-Identifier: Apache-2.0
"""Which record types a question is *about* — so its answer rests on records about it.

**The defect this exists for is competition, not size.** A question about runs was answered from
1,000 of 63,947 entries, composed as `effect_observed` 383, `pre_decision` 302, … `run_start` 60:
sixty run records buried in 940 pieces of per-step machinery. The model declined, correctly, on
the evidence it was handed. Raising the bound would not have helped — at any row count the estate's
noisiest activity crowds out the question's own records — so the read bounds per type instead, and
this is what tells it which types to bound.

**Focus NARROWS and can never widen.** The caller composes `focus ∩ visible`, so a question can
only ever reduce what a role may already see. `visible_event_types` decides what is permitted;
this decides what is *relevant*, and those are different jobs that must not be confused: a focus
that could add a type would be a scope bug wearing a relevance feature's clothes.

**No model decides, for the same reason routing does not.** A model here would put Principle
VIII's gates on the read path and make the blocking lane score against recordings. Deterministic
term overlap is scorable with no credential, and a wrong mapping is a bug with a failing row
rather than a judgement call.

**It lives in `answering`, not `audit`.** The query layer gains a *bound* and stays ignorant of
questions; this layer knows about questions and stays ignorant of SQL. A `focus` parameter on
`EvidenceQueryRequest` would put question semantics in the store, which is the seam that would
then have to be maintained in two vocabularies.

**Nothing here reads anything** — no roles, no clock, no store. A string in, a set of types out.
"""

from __future__ import annotations

import re
from typing import Final

from core.audit.schema import AuditEventType

#: What a question's words say about which records could answer it.
#:
#: Drawn from the trail's own vocabulary, like `routing.py`'s, and deliberately overlapping with
#: it: the words that make a question estate-shaped are largely the words that say which part of
#: the estate.
#:
#: **The singular/plural rule does NOT apply here, and the difference is worth stating.** In
#: `routing.py` that rule keeps documentation questions out of the evidence plane — the singular
#: `agent` there would misroute *"How does an AI agent obtain an identity with Vault?"* to a
#: scoped read. This table is consulted only *after* routing has already sent a question to the
#: estate, so a singular term here cannot cause a read that would not otherwise happen. It can
#: only decide which records an already-authorised read returns.
#:
#: Different risks, different rules. Conflating them would have left *"What did the planner agent
#: do?"* — which routes correctly on `did` — focusing nothing and starving at volume, which is
#: the defect this module exists to fix.
#:
#: **A term absent here costs nothing** — an unfocused question reads as it does today, which is
#: the fallback the whole design leans on. A term mapped to the *wrong* types is the expensive
#: mistake: it produces an empty answer that looks exactly like an honest one, which is the same
#: failure mode the router's false negatives had. That asymmetry is why this table is small and
#: why `focus_types` returns `None` rather than guessing.
FOCUS_TERMS: Final[dict[str, frozenset[AuditEventType]]] = {
    "run": frozenset({AuditEventType.RUN_START, AuditEventType.RUN_STOPPED}),
    "runs": frozenset(
        {
            AuditEventType.RUN_START,
            AuditEventType.RUN_STOPPED,
            AuditEventType.RUN_RESUMED,
        }
    ),
    "ran": frozenset({AuditEventType.RUN_START, AuditEventType.RUN_RESUMED}),
    "resumed": frozenset({AuditEventType.RUN_RESUMED}),
    "stopped": frozenset({AuditEventType.RUN_STOPPED}),
    "tools": frozenset({AuditEventType.TOOL_CHOSEN, AuditEventType.TOOL_OUTCOME}),
    "used": frozenset({AuditEventType.TOOL_CHOSEN, AuditEventType.TOOL_OUTCOME}),
    # Singular included: see the note above on why the routing rule does not apply here. What an
    # agent *did* is its runs and the tools it chose within them, which is why this maps to three
    # types rather than to the record that merely names it.
    "agent": frozenset(
        {
            AuditEventType.RUN_START,
            AuditEventType.TOOL_CHOSEN,
            AuditEventType.TOOL_OUTCOME,
        }
    ),
    "agents": frozenset(
        {
            AuditEventType.RUN_START,
            AuditEventType.TOOL_CHOSEN,
            AuditEventType.TOOL_OUTCOME,
        }
    ),
    "active": frozenset({AuditEventType.RUN_START, AuditEventType.RUN_RESUMED}),
    "secrets": frozenset({AuditEventType.EFFECT_OBSERVED}),
    "denied": frozenset({AuditEventType.AUTHORITY_DENIED, AuditEventType.AUTHORITY_REFUSED}),
    "refused": frozenset({AuditEventType.AUTHORITY_DENIED, AuditEventType.AUTHORITY_REFUSED}),
    "granted": frozenset({AuditEventType.AUTHORITY_ISSUED}),
    "failed": frozenset({AuditEventType.ENFORCEMENT_ERROR, AuditEventType.RUN_STOPPED}),
    "error": frozenset({AuditEventType.ENFORCEMENT_ERROR}),
    "errors": frozenset({AuditEventType.ENFORCEMENT_ERROR}),
    "read": frozenset({AuditEventType.EVIDENCE_READ, AuditEventType.RECORD_READ}),
    "changed": frozenset({AuditEventType.AUTHORITY_CHANGE_OBSERVED}),
}

_WORD = re.compile(r"[a-z0-9]+")


def focus_types(question: str) -> frozenset[AuditEventType] | None:
    """The record types this question is about, or `None` if it names none.

    The union of every term's types, so *"which runs failed?"* reaches both the run records and
    the failure ones rather than whichever term happened to be checked first.

    `None` is a real answer and the common one: it means read as before. A question the table does
    not recognise must not be narrowed to a guess, because a wrong narrowing produces an empty
    answer indistinguishable from an honest one — the expensive failure this module is careful
    about in exactly the way the router had to learn to be.
    """
    words = _WORD.findall(question.lower())
    matched: set[AuditEventType] = set()
    for word in words:
        matched |= FOCUS_TERMS.get(word, frozenset())
    return frozenset(matched) if matched else None


__all__ = ["FOCUS_TERMS", "focus_types"]
