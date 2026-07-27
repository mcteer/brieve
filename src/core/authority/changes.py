# SPDX-License-Identifier: Apache-2.0
"""Authority-change evidence — the harness observes, and never decides.

An authority change is the highest-consequence write in the system: it changes what an
agent may *become*. Vault holds the decision; this module makes it reconstructable, joined
to the correlation ID an investigator already walks.

Two things it deliberately is not:

**It is not a second decision.** No quorum is evaluated here. A harness that could decide
would be a second answer to "who may do what", and two answers is not redundancy — it is
ambiguity, and during an incident someone reads the wrong one.

**It is not a mirror of Vault's approval state.** Recording *that a decision happened* is
evidence; keeping a synchronised copy of pending approvals would be that second answer
again, arriving by a slower route.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from core.errors import CoreError


class ChangeDisposition(StrEnum):
    """What became of a request. Four outcomes, and no fifth meaning "waiting on a human"
    that a run could ever observe — Control Groups gate what an agent may become, never
    what a running agent does."""

    REQUESTED = "requested"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class BlockedPendingApprovalError(CoreError):
    """The operation is queued for approval. **This is not a denial.**

    Collapsing the two would make an in-flight approval indistinguishable from a refusal,
    and a caller would either retry forever or report a failure that has not happened.
    Vault makes the distinction natively — a wrapping token rather than a 403 — and this
    error carries it across the seam rather than flattening it.
    """

    def __init__(
        self,
        message: str = "authority change is pending approval",
        *,
        accessor: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        super().__init__(message, correlation_id=correlation_id)
        self.reason_code = "blocked_pending_approval"
        #: Vault's handle for the pending request. Not a credential — an opaque reference.
        self.accessor = accessor


class AuthorityChangeEvent(BaseModel):
    """A record of what the trust fabric decided, not a copy of the authority itself."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    correlation_id: str
    controlled_path: str
    disposition: ChangeDisposition
    #: Requester, and each approver or denier. Identities, never credentials.
    identities: list[str] = Field(default_factory=list)
    occurred_at: datetime
    #: Vault's reference for the pending request, when there is one.
    accessor: str | None = None

    def public_dict(self) -> dict[str, object]:
        """Fields safe for audit and spans. No credential material, no policy content —
        an audit record of an authority change is not a place to copy the authority."""
        return {
            "correlation_id": self.correlation_id,
            "controlled_path": self.controlled_path,
            "disposition": self.disposition.value,
            "identities": sorted(self.identities),
            "occurred_at": self.occurred_at.isoformat(),
            "accessor": self.accessor,
        }


def observe_change(
    *,
    correlation_id: str,
    controlled_path: str,
    disposition: ChangeDisposition,
    identities: list[str] | None = None,
    occurred_at: datetime,
    accessor: str | None = None,
) -> AuthorityChangeEvent:
    """Build the record. Named `observe`, not `record_decision`, because the decision was
    made elsewhere and this only witnesses it."""
    return AuthorityChangeEvent(
        correlation_id=correlation_id,
        controlled_path=controlled_path,
        disposition=disposition,
        identities=list(identities or []),
        occurred_at=occurred_at,
        accessor=accessor,
    )
