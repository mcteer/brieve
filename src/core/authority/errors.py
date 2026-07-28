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
    # --- what they may do does not include this
    "outside_scope": "resolution succeeded; the action is not permitted",
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
