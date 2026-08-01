# SPDX-License-Identifier: Apache-2.0
"""What a report is: claims, each with the evidence behind it and how well it is supported.

**Reports are presentation; attestation rests on records** (ADR-0018). Nothing here is a source
of truth — every field is populated from the run's own records, and nothing in this platform may
read a report to decide anything.

**A report is never persisted.** It has no identity and no lifecycle; it does not exist between
requests. A stored report would be a second copy of the evidence that can drift from it, and
anything persisted is eventually read as a source — which is the one thing a report must never
become.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ClaimStatus(StrEnum):
    """How well one statement is supported. Closed vocabulary.

    **Seven values rather than "verified" and "unknown"**, and the four unsupported ones are
    kept apart because each sends a reader somewhere different: to the product, to the tool's
    registration, to why the run never finished, or to the records themselves. A single honest
    "unknown" would be useless, and a reader who cannot tell *which* kind of gap they are
    looking at cannot act on it.
    """

    #: The records say this, and nothing more was required. The ordinary case.
    FROM_RECORD = "from_record"
    #: The product was asked at run end and confirmed it. The strongest claim available.
    OBSERVED = "observed"
    #: The product was asked and said the effect did **not** land.
    #:
    #: **This must be impossible to read as success.** It is the failure ADR-0018 opens with —
    #: "applied successfully to three workspaces" when a fourth silently failed — and the one
    #: a reader is least able to catch by reading, because a plausible report terminates the
    #: investigation that would have found it.
    CONTRADICTED = "contradicted"
    #: The product could not be reached when the run tried to observe.
    #:
    #: Not success, and not failure either. An unreachable product is the case a two-way
    #: outcome would force a guess about, which is why `ObservationOutcome` is three-way.
    UNVERIFIED_UNREACHABLE = "unverified_unreachable"
    #: The tool has no registered observer, so nothing could ask.
    #:
    #: A fact about the tool's *registration* rather than about the product, which is why it
    #: is separate from the value above — it sends a reader to a different file.
    UNVERIFIED_NO_OBSERVER = "unverified_no_observer"
    #: The run never reached a terminal state, so it never observed.
    #:
    #: A killed run and a down product are different facts. Collapsing them would report an
    #: infrastructure outage as an interrupted run, or the reverse.
    UNVERIFIED_NOT_OBSERVED = "unverified_not_observed"
    #: The records disagree, or a bracket opened and never closed.
    #:
    #: **Flagged in place, never softened.** A report that silently omits what it could not
    #: reconcile is more dangerous than one that never claimed to reconcile anything.
    UNRECONCILED = "unreconciled"


#: The statuses that may attach to a claim about an **effect** — something a tool did.
#:
#: These five partition every effect claim: it was observed, contradicted, unobservable for one
#: of two reasons, or never observed at all. **Nothing falls through to a bare "completed"**,
#: which is the silent assertion this whole vocabulary exists to prevent.
#:
#: `FROM_RECORD` is absent deliberately — an effect claim resting on the record alone is exactly
#: what ADR-0018 forbids, so it has no status here to land on. `UNRECONCILED` is absent because
#: it describes the records disagreeing rather than the effect being unverified.
EFFECT_STATUSES: frozenset[ClaimStatus] = frozenset(
    {
        ClaimStatus.OBSERVED,
        ClaimStatus.CONTRADICTED,
        ClaimStatus.UNVERIFIED_UNREACHABLE,
        ClaimStatus.UNVERIFIED_NO_OBSERVER,
        ClaimStatus.UNVERIFIED_NOT_OBSERVED,
    }
)


class Claim(BaseModel):
    """One statement, with what it was checked against and how that went.

    **A claim is never dropped for being unsupportable.** It is emitted carrying a status that
    says so — omitting it would leave a report that reads complete and is not, which is the
    failure mode a reader cannot detect.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: What the claim is about — a step, a tool, the run itself.
    subject: str
    #: What is being asserted. Populated from evidence, never composed.
    statement: str
    #: How well it is supported.
    status: ClaimStatus
    #: Which records support it. **Every claim carries at least one**, which is what makes
    #: "every claim traces to a record" checkable rather than asserted.
    evidence: tuple[str, ...] = ()

    @property
    def is_effect(self) -> bool:
        """Whether this claim is about something a tool did."""
        return self.status in EFFECT_STATUSES


class ReportBasis(BaseModel):
    """Whether the evidence this report compiled from was itself verified.

    **A report compiled from records nobody checked is a weaker claim than one compiled from
    records that were**, and the difference must be visible rather than assumed. 015 gave the
    trail a second copy and a reconciler that compares contents rather than hash claims; this
    is where a report says whether either ran.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: The hash chain verified over the entries this report read.
    chain_verified: bool = False
    #: A second copy exists and was reconciled. ``None`` when no destination is configured —
    #: which is not the same as "reconciliation failed", and must not read as it.
    reconciled: bool | None = None
    #: Why, when either is false. Empty when there is nothing to explain.
    detail: str = ""


class RunReport(BaseModel):
    """A typed account of one run, compiled on demand and never stored.

    **The gate and the person read the same object.** There is no projection, no gate-only
    variant, and no field visible to one consumer and not the other — because a gate that scores
    a different object from the one a person reads is not gating what anyone sees, which is this
    platform's recurring failure shape.

    **It carries no part of the run's result payload.** That is `get_run_result`'s, and it is
    restricted to the subject who started the run; a report is tenant-scoped, so carrying it
    would route around the restriction. The absence of that field is a security property rather
    than an omission.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    #: Running, refused, or how it ended. A report of an unfinished run must not read as an
    #: account of a finished one.
    disposition: str
    claims: tuple[Claim, ...] = ()
    basis: ReportBasis = Field(default_factory=ReportBasis)
    #: What this report can and cannot evidence (ADR-0032) — stated, never left to inference.
    scope: str = ""

    @property
    def effect_claims(self) -> tuple[Claim, ...]:
        return tuple(claim for claim in self.claims if claim.is_effect)


__all__ = ["EFFECT_STATUSES", "Claim", "ClaimStatus", "ReportBasis", "RunReport"]
