# SPDX-License-Identifier: Apache-2.0
"""What this asker may see — the executable half of ADR-0035's scope algebra.

ADR-0035 decided on 2026-07-01 that estate-state answers are *"differentiated by scope algebra
rather than per-persona interfaces: everyone asks in the same place, and the answer is bounded by
the asker's own entitlements."* Until now nothing implemented it. This is the map that does.

**It narrows the query; it does not filter the results.** The distinction is the whole security
argument. A post-filter reads everything and then hides some of it, so a scoping bug leaks
silently and the access record shows a broad read that never should have happened. Narrowing puts
the bound *in the request*: out-of-scope entries are never read, and the trail records exactly
what was asked for.

**In `answering`, not `authority`, and that is deliberate.** This maps a role to *what records it
may see*, never to what it may do. Filing it under `authority` would invite the reading that an
estate answer grants something — it grants nothing; it is a bounded read that produces prose.

**Empty means refuse, and the refusal lives at the call site.** This module computes a set and
raises nothing. The caller checks for empty and refuses *before* attempting a read, so a subject
with no mapped roles produces no access record — there was no access to record.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Final

from core.audit.schema import AuditEventType

#: What each role may see in the trail.
#:
#: **Two keys, and the provenance of each matters** (analysis P4-2). `operator` is the one role
#: name this platform's own claim mappings actually produce — everything else in the repository
#: that names a role names that one. `compliance-analyst` is **introduced by this feature**,
#: because ADR-0035's central scenario is two people asking the same question and getting
#: different answers, and a map with one visibility class cannot produce that. A map that could
#: not differentiate would satisfy its own tests and refute the ADR.
#:
#: The analyst is a **superset** of the operator, which is the honest shape for these two: an
#: operator needs to see what ran and what broke; an analyst needs that *plus* who was granted
#: what and who read which evidence. Nothing here is a hierarchy the code relies on — the union
#: below would work equally well for disjoint sets, and roles that overlap partially are expected.
#:
#: A role absent from this map contributes **nothing**. That is not a special case: it falls out of
#: the union, and it is why an unrecognised role cannot widen anyone's scope.
ROLE_VISIBILITY: Final[dict[str, frozenset[AuditEventType]]] = {
    "operator": frozenset(
        {
            AuditEventType.RUN_START,
            AuditEventType.RUN_STOPPED,
            AuditEventType.RUN_RESUMED,
            AuditEventType.STEP_REOBSERVED,
            AuditEventType.TOOL_OUTCOME,
            AuditEventType.TOOL_CHOSEN,
            AuditEventType.EFFECT_OBSERVED,
            AuditEventType.PRE_DECISION,
            AuditEventType.POST_DECISION,
            AuditEventType.ENFORCEMENT_ERROR,
            AuditEventType.MODEL_GATE,
            AuditEventType.MATRIX_FALLBACK,
            # 031, the decision 029 recorded and 030 held open: what happened to YOUR runs is
            # yours to ask about. An operator's dispatched run can be refused by governance, and
            # until this line the person who caused the refusal could not see it through the ask
            # path — a correct decline that read as a half-proof. DENIED and REFUSED only:
            # ISSUED, EXPIRED and the grant/change records stay analyst-only, because
            # who-holds-what-authority is a different sensitivity than what-was-refused.
            AuditEventType.AUTHORITY_DENIED,
            AuditEventType.AUTHORITY_REFUSED,
        }
    ),
    "compliance-analyst": frozenset(
        {
            # Everything the operator sees…
            AuditEventType.RUN_START,
            AuditEventType.RUN_STOPPED,
            AuditEventType.RUN_RESUMED,
            AuditEventType.STEP_REOBSERVED,
            AuditEventType.TOOL_OUTCOME,
            AuditEventType.TOOL_CHOSEN,
            AuditEventType.EFFECT_OBSERVED,
            AuditEventType.PRE_DECISION,
            AuditEventType.POST_DECISION,
            AuditEventType.ENFORCEMENT_ERROR,
            AuditEventType.MODEL_GATE,
            AuditEventType.MATRIX_FALLBACK,
            # …plus who was granted what, and who read which evidence.
            AuditEventType.AUTHORITY_ISSUED,
            AuditEventType.AUTHORITY_REFUSED,
            AuditEventType.AUTHORITY_DENIED,
            AuditEventType.AUTHORITY_EXPIRED,
            AuditEventType.AUTHORITY_CHANGE_OBSERVED,
            AuditEventType.MIRRORING_DECISION,
            AuditEventType.EVIDENCE_READ,
            AuditEventType.EVIDENCE_READ_REFUSED,
            AuditEventType.RECORD_READ,
            AuditEventType.RECORD_READ_REFUSED,
            AuditEventType.AUDIT_RECONCILED,
        }
    ),
    # 044: the administrator, and the empty set is the decision rather than an omission.
    #
    # **Disjoint from both roles above.** The analyst is the operator's superset because both
    # answer *what happened*; an administrator answers *what may happen*. Making admin a
    # superset would hand configuration authority to everyone who can already read the trail
    # — a widening nobody asked for — and making the analyst a superset of admin would do the
    # reverse. They are different questions, so they are different sets, and a person who
    # needs both holds both mappings.
    #
    # The empty frozenset falls out of the union exactly as the docstring above describes for
    # an absent role: **being an administrator confers no audit visibility at all**. What it
    # confers lives at the console's routes, which check the role directly.
    #
    # A row asserts both directions, because a widening in either would be invisible here —
    # this map would still parse, and every existing test would still pass.
    "admin": frozenset(),
}


def visible_event_types(roles: Iterable[str]) -> frozenset[AuditEventType]:
    """The union of what these roles may see. Empty is a legitimate — and refusing — answer.

    **Union rather than intersection**: holding two roles makes someone able to see more, not
    less. The alternative would mean adding a role could silently narrow what a person could
    already see, which nobody would predict from being granted something.
    """
    seen: set[AuditEventType] = set()
    for role in roles:
        seen |= ROLE_VISIBILITY.get(role, frozenset())
    return frozenset(seen)


__all__ = ["ROLE_VISIBILITY", "visible_event_types"]
