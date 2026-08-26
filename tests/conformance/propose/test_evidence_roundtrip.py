# SPDX-License-Identifier: Apache-2.0
"""T025 — a proposal's evidence survives the analyzer → proposer checkpoint (047).

The row was written against the Terraform plan gate, which attached bounded plan facts and
was the only thing putting evidence on a proposal. The gate is gone; **the seam it exercised
is not**. Evidence is composed in the analyzer and rendered by the proposer in a different
task, with a durability checkpoint between them, so "does it survive the handoff" is a real
property of that boundary and not a fact about Terraform. Rewritten to assert it directly
rather than deleted with the feature that happened to be its first caller.
"""

from __future__ import annotations

from core.authoring.proposal import Proposal, ProposedFile
from surfaces.dispatch.authoring import proposal_from_payload, proposal_payload


def test_evidence_round_trips_through_the_handoff() -> None:
    proposal = Proposal(
        target_repository="acme/app",
        branch="brieve/abc",
        task="add a bucket",
        files=[ProposedFile(path="main.tf", body='resource "null_resource" "x" {}', is_diff=False)],
        rationale="add a bucket",
    )
    proposal.evidence.extend(["Authored 1 file", "Reviewed by a second model"])

    restored = proposal_from_payload({"authoring_proposal": proposal_payload(proposal)})

    assert restored.evidence == ["Authored 1 file", "Reviewed by a second model"]
    body = restored.render()
    assert "## Measured impact" in body
    assert "Reviewed by a second model" in body
