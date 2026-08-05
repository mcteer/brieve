# SPDX-License-Identifier: Apache-2.0
"""The platform does not enact what it authored (038, FR-020; research R11).

**Provenance, not capability.** It is not that applying is forbidden — it is that applying
*one's own output* is. `terraform_apply` keeps doing exactly what it did before: applying
configuration a person wrote and reviewed. Once a human merges a proposal, the artefact **is**
reviewed configuration, and applying it is the ordinary governed act it always was.

**Two layers, and the second is not redundant.**

1. *Structural* — the authoring definition's ceiling carries no enacting tool, and per-task
   scope narrows it further. Nothing to check because nothing is reachable.
2. *Provenance* — this module. Digests of what the platform produced, consulted **at the
   moment of enactment**.

The first is a fact about *today's definitions*. The second is what survives a definition
somebody writes next year, which is what "checkable at the moment of enactment, not inferred
later" asks for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.authoring.proposal import ProposalState


@dataclass(frozen=True)
class Provenance:
    """One authored artefact, and where it stands."""

    content_digest: str
    authoring_correlation_id: str
    proposal_state: ProposalState

    @property
    def human_merged(self) -> bool:
        """Whether a person accepted it. **Observed**, never written by the platform."""
        return self.proposal_state is ProposalState.MERGED


@dataclass
class ProvenanceLedger:
    """What the platform authored, keyed by content digest.

    Keyed on the digest rather than on a path, because enactment sees *content*: a file moved,
    renamed or copied into another repository is the same bytes, and a rule that turned on the
    path would be defeated by `cp`.
    """

    entries: dict[str, Provenance] = field(default_factory=dict)

    def record(self, provenance: Provenance) -> None:
        self.entries[provenance.content_digest] = provenance

    def mark_merged(self, content_digest: str) -> None:
        """Note an **observed** merge. The platform does not perform one."""
        existing = self.entries.get(content_digest)
        if existing is not None:
            self.entries[content_digest] = Provenance(
                content_digest=existing.content_digest,
                authoring_correlation_id=existing.authoring_correlation_id,
                proposal_state=ProposalState.MERGED,
            )

    def may_enact(self, content_digest: str) -> tuple[bool, Provenance | None]:
        """Whether this content may be enacted, and the provenance that decided it.

        Content the platform never authored is not this rule's business: it returns permitted
        with no provenance, because the rule is about *our own output* and nothing else.
        """
        provenance = self.entries.get(content_digest)
        if provenance is None:
            return True, None
        return provenance.human_merged, provenance


__all__ = ["Provenance", "ProvenanceLedger"]
