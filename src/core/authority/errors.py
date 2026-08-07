# SPDX-License-Identifier: Apache-2.0
"""Typed authority refuse/deny errors."""

from __future__ import annotations

from typing import Final

from core.errors import CoreError

#: Every reason code identity resolution may refuse with, and what each one means.
#:
#: **A frozen mapping rather than bare strings, because FR-012 requires three situations to
#: stay distinguishable and a reason code invented at the call site is one nothing can
#: assert on.** The three situations, in the order a reader of an audit trail cares about:
#:
#: - **who** is asking cannot be established;
#: - **what** they may do cannot be established;
#: - what they may do **does not include this**.
#:
#: Only the last is a policy answer. Everything else is the platform declining to guess, and
#: conflating them is how a platform failure comes to look like a permissions decision —
#: which sends whoever investigates to the wrong system entirely.
RESOLUTION_REASONS: Final[dict[str, str]] = {
    # --- who is asking is unknown
    "unknown_subject": "who is asking cannot be established",
    "no_role_for_subject": "authenticated, but claims map to no role",
    # --- what they may do is unknown
    "unbound_role": "role exists, no binding record",
    "unknown_agent_definition": "no registration for this agent definition",
    "missing_ceiling_record": "registered, but no harness ceiling record",
    "unknown_ceiling_entry": "ceiling names a tool or action the platform does not know",
    "unsupported_schema_version": "record written by a newer platform",
    "fabric_unreachable": "the trust fabric did not answer",
    "fabric_timeout": "the trust fabric answered too slowly",
    "entitlement_unavailable": "the product could not be asked",
    "broker_not_implemented": "the brokered credential path does not exist yet",
    # --- 043: nobody decided who may judge whether an answer addresses the question
    #
    # A FOURTH place between a question and an answer, and it earns its own code for the
    # reason the three above do. `unbound_ask_source` means no operator decided which model
    # may ANSWER; this means none decided which may JUDGE the answer — and one qualification
    # never licenses the other, so an operator who bound an ask cell and stopped is in a
    # state the platform must be able to name precisely.
    #
    # Distinct from `unqualified_cell` (the matrix has not qualified the named judge) and from
    # `fabric_unreachable` (nobody could read the record at all). Governance precedes
    # availability: "nobody decided" is what an operator needs before "it could not be
    # reached", and collapsing them sends them to a vendor's status page during a governance
    # gap.
    "relevance_unbound": "no binding names a cell to judge whether an answer is relevant",
    "relevance_unqualified": "the relevance judge's cell is not qualified, or was withdrawn",
    # --- 027: the cell is qualified, and the credential to call it could not be obtained
    #
    # Three codes now sit between a question and a model, and each sends someone somewhere
    # different. `unqualified_cell` means evaluation has not qualified what was asked for —
    # go to the matrix. `fabric_unreachable` means the store itself did not answer — go to the
    # outage. This one means both of those succeeded and the credential is simply not there:
    # never written, rotated to nothing, or revoked. Go to whoever governs the credential.
    #
    # Collapsing it into either neighbour was the tempting shape, and it costs the one thing
    # the code buys: revocation is *supposed* to produce this, so an operator who deletes a
    # credential must see something distinguishable from an outage they did not cause.
    "credential_unavailable": "the cell is qualified and the model credential could not be "
    "obtained; the platform holds no authority to call this vendor",
    # --- what they may do does not include this
    "outside_scope": "resolution succeeded; the action is not permitted",
    # --- 013: the record could not be read as written
    "malformed_record": "a control-plane record is present but not well-formed",
    # --- 013: the model bound for a role is not one evaluation qualified
    #
    # Resolution reasons rather than operation reasons: these refuse while establishing what
    # a definition may do, alongside `unknown_ceiling_entry`, and they refuse before a run
    # exists. A binding is checked twice — at definition registration and again at run start
    # — because a cell can be WITHDRAWN while the definition that pinned it sits unchanged.
    "unqualified_cell": "the definition pins a cell evaluation has not qualified",
    "cell_withdrawn": "the pinned cell was qualified once and has since been withdrawn",
    "no_qualified_fallback": "the pinned cell is unavailable and no other qualified cell "
    "exists for that role; the run stops rather than proceeding unqualified",
    # --- 020: the definition binds NO model for a role a run is about to consult one for
    #
    # Distinct from `unqualified_cell`, and the difference decides where somebody goes to fix
    # it: that one means the matrix has not qualified what the definition asked for, and sends
    # them to the matrix; this one means the definition asked for nothing at all, and sends
    # them to the definition.
    #
    # It exists because the alternative is defaulting, and a default model is an ungoverned
    # model choice — the same defect as an ungoverned tool choice, one level up. 013 built the
    # binding map and nothing consumed it, so until a run actually resolved a model there was
    # no path on which "bound to nothing" could be refused rather than shrugged at.
    "no_binding_for_role": "the definition binds no model for the role a run needs one for; "
    "refused rather than defaulted, because a defaulted model is an ungoverned model choice",
    # --- 026: asking is bound per SOURCE, and nothing is bound for this one
    #
    # Distinct from `no_binding_for_role` above, and the difference is what an ask is: a run
    # binds through its agent definition, so "bound to nothing" is a fact about a definition.
    # An ask has no definition — it binds through an operator-authored record, per source, so
    # guidance can be bound while estate is not. Sending someone to a definition would send
    # them somewhere that does not exist for this path.
    #
    # It refuses rather than defaulting for the same reason `no_binding_for_role` does: a
    # defaulted model is an ungoverned model choice. 024 and 025 shipped an answering path
    # that consulted no binding at all, and this is the code that makes that unrepeatable.
    "unbound_ask_source": "no ask binding names a cell for the source this question needs; "
    "refused rather than defaulted, because a defaulted model is an ungoverned model choice",
    # --- 013: the pack a definition names cannot supply what it is being asked for
    "pack_exceeds_ceiling": "a named pack declares a tool the ceiling does not permit; a "
    "pack narrows what a definition may do and never widens it",
    "pack_not_loaded": "the definition names a pack that is not loaded",
    "pack_not_reachable": "the definition does not name the pack this tool was qualified by",
    "ambiguous_tool_name": "two reachable packs declare this tool name; qualify it, because "
    "resolving by load order makes the answer change when the directory listing does",
    "above_tier": "the composition is above the definition's competency tier",
}

#: The one reason code above that reports a **decision** rather than a failure to decide.
#:
#: Named so a caller can ask the question rather than hardcoding the answer. Anything not in
#: this set means the platform could not find out, and a caller treating those as denials
#: would be reporting a decision nobody made.
DECIDED_REASONS: Final[frozenset[str]] = frozenset({"outside_scope"})


class ResolutionRefused(CoreError):
    """Identity resolution could not answer, or answered no.

    Carries a reason code from :data:`RESOLUTION_REASONS` and refuses to carry one that is
    not there — a reason code nothing can assert on is the defect the mapping exists to
    prevent, and accepting an unknown one at construction time would reintroduce it one
    call site at a time.
    """

    def __init__(
        self,
        message: str,
        *,
        reason_code: str,
        correlation_id: str | None = None,
    ) -> None:
        if reason_code not in RESOLUTION_REASONS:
            raise ValueError(
                f"unknown resolution reason code {reason_code!r}; "
                f"add it to RESOLUTION_REASONS with what it means"
            )
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = reason_code

    @property
    def is_decision(self) -> bool:
        """Whether this refusal is a policy answer rather than a failure to answer."""
        return self.reason_code in DECIDED_REASONS


class AuthorityRefuseError(CoreError):
    """Run start refused — no usable task credential issued."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str = "authority_refused",
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = reason_code


class AuthorityExpiredError(CoreError):
    """Task credential past TTL."""

    def __init__(
        self,
        message: str = "task authority expired",
        *,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = "authority_expired"


class AuditAppendFailed(CoreError):
    """Audit append failed on an authority/mirroring enforcement path."""

    def __init__(
        self,
        message: str = "audit append failed",
        *,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
