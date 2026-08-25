# SPDX-License-Identifier: Apache-2.0
"""T025 — plan evidence survives analyzer → proposer checkpoint (047)."""

from __future__ import annotations

from core.authoring.proposal import Proposal, ProposedFile
from surfaces.dispatch.authoring import proposal_from_payload, proposal_payload
from surfaces.dispatch.terraform_authoring import attach_plan_evidence


def test_plan_evidence_round_trips_through_the_handoff() -> None:
    proposal = Proposal(
        target_repository="acme/app",
        branch="brieve/abc",
        task="add a bucket",
        files=[ProposedFile(path="main.tf", body='resource "null_resource" "x" {}', is_diff=False)],
        rationale="add a bucket",
    )
    attach_plan_evidence(
        proposal=proposal,
        plan_result={
            "fixture": False,
            "exit_code": 2,
            "has_changes": True,
            "output": "Plan: 1 to add, 0 to change, 0 to destroy.",
        },
    )
    restored = proposal_from_payload({"authoring_proposal": proposal_payload(proposal)})
    assert restored.evidence
    assert any("1 to add" in line for line in restored.evidence)
    body = restored.render()
    assert "## Measured impact" in body
    assert "1 to add" in body
