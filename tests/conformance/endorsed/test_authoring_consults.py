# SPDX-License-Identifier: Apache-2.0
"""E24's authoring half — one loader serves both paths (045, T022, US7).

**The same requirement arrives through two doors.** "How long must we retain logs?" is an ask;
"write the Vault configuration for this repository, following our standards" is an authoring
run. If only the answering path could see a customer's endorsed material, the platform would
cite an organisation's own architecture standard when asked about it and ignore it when writing
against it — which is the more consequential of the two, because the artefact is a pull request
somebody merges.

042 proved a product feature can consume the authoring tier unchanged. This asserts 045 does
the same: the identical `resolves` callable, the identical provenance vocabulary, and a
proposal that discloses what it rests on the way an answer does.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.answering.corpus import Corpus, Document
from core.answering.endorsed.corpus import CombinedCorpus, build_endorsed_corpus
from core.answering.endorsed.records import (
    ADOPTED,
    EndorsedDocument,
    SyncedVersion,
    digest_of_document,
)
from surfaces.dispatch.policy_authoring import (
    UNSUPPORTED_DISCLOSURE,
    compose_policy_evidence,
    render_citation_evidence,
    resolved_citations,
)

ENDORSED = "/endorsed/acme-standards/vault.md#approle"
PINNED = "/validated-patterns/vault/agent#deployment"


def _combined() -> CombinedCorpus:
    """The exact object the ask path composes, handed to the authoring path unchanged."""
    sections = {"approle": "AppRoles are issued per workload, never per team."}
    endorsed = build_endorsed_corpus(
        [
            SyncedVersion(
                version_id="v-one",
                tenant_id="acme",
                source="acme-standards",
                upstream_tip="abc",
                synced_at=datetime(2026, 8, 1, tzinfo=UTC),
                synced_by="dan@acme.example",
                state=ADOPTED,
                documents={
                    "/endorsed/acme-standards/vault.md": EndorsedDocument(
                        path="/endorsed/acme-standards/vault.md",
                        url="https://git.example.com/acme/standards/vault.md",
                        digest=digest_of_document(sections),
                        anchors=frozenset(sections),
                        sections=dict(sections),
                    )
                },
            )
        ]
    )
    pinned = Corpus(
        digest="corpus-digest",
        documents={
            "/validated-patterns/vault/agent": Document(
                path="/validated-patterns/vault/agent",
                url="https://developer.hashicorp.com/validated-patterns/vault/agent",
                digest="d",
                anchors=frozenset({"deployment"}),
                sections={"deployment": "Deploy the agent as a sidecar."},
            )
        },
        synced_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    return CombinedCorpus(pinned=pinned, endorsed=endorsed)


class _Proposal:
    """The members `compose_policy_evidence` touches."""

    def __init__(self, rationale: str) -> None:
        self.rationale = rationale
        self.evidence: list[str] = []
        self.disclosures: list[str] = []


def _impact() -> dict[str, Any]:
    return {"paths": [], "truncated": False}


def test_the_authoring_path_resolves_endorsed_citations_through_the_same_callable() -> None:
    """One loader, both paths. The seam 042 established, consumed unchanged.

    `resolved_citations` takes a `resolves` callable precisely so the caller decides which pin
    is authoritative — and the caller now hands it the same combination the ask path built.
    """
    combined = _combined()

    found, grounded = resolved_citations(
        f"Per {ENDORSED} and {PINNED}, issue per workload.", combined.resolves
    )

    assert grounded
    assert set(found) == {ENDORSED.lstrip("/") and ENDORSED, PINNED}


def test_a_proposal_discloses_endorsed_material_separately_from_validated_designs() -> None:
    """FR-016. A reviewer told "this follows your own standard" is being told something
    different from "this follows HashiCorp's guidance", and merging is a decision they make on
    that basis."""
    proposal = _Proposal(f"Following {ENDORSED} and {PINNED}.")

    composed = compose_policy_evidence(
        proposal=proposal, impact=_impact(), resolves=_combined().resolves
    )

    evidence = "\n".join(composed.evidence)
    assert "your organisation's endorsed sources" in evidence
    assert "resolves against the pin" in evidence
    assert ENDORSED in evidence
    assert PINNED in evidence


def test_a_proposal_resting_only_on_validated_designs_does_not_claim_endorsed_material() -> None:
    """Composed from what was cited, never from what was available — the answer's rule, here."""
    proposal = _Proposal(f"Following {PINNED}.")

    composed = compose_policy_evidence(
        proposal=proposal, impact=_impact(), resolves=_combined().resolves
    )

    evidence = "\n".join(composed.evidence)
    assert "resolves against the pin" in evidence
    assert "endorsed sources" not in evidence


def test_a_proposal_resting_only_on_endorsed_material_says_exactly_that() -> None:
    proposal = _Proposal(f"Following {ENDORSED}.")

    composed = compose_policy_evidence(
        proposal=proposal, impact=_impact(), resolves=_combined().resolves
    )

    evidence = "\n".join(composed.evidence)
    assert "your organisation's endorsed sources" in evidence
    assert "resolves against the pin" not in evidence


def test_an_endorsed_citation_that_does_not_resolve_leaves_the_proposal_unsupported() -> None:
    """**The gate is not loosened for customer material, which is the risk this feature runs.**

    Making an organisation's own standard citable must not make citing it easier than citing a
    validated design. A path under `/endorsed/` that names nothing real is exactly as
    unsupported as a made-up HashiCorp URL, and the proposal says so.
    """
    proposal = _Proposal("Following /endorsed/acme-standards/invented.md#nothing.")

    composed = compose_policy_evidence(
        proposal=proposal, impact=_impact(), resolves=_combined().resolves
    )

    assert UNSUPPORTED_DISCLOSURE in composed.disclosures
    assert not composed.evidence[1:] or "endorsed sources" not in "\n".join(composed.evidence)


def test_the_provenance_split_has_one_reader() -> None:
    """`render_citation_evidence` calls `provenance_of` rather than testing the prefix itself.

    Two places deciding what a path means is how a convention decays into a bug — which is why
    research R2 emitted provenance as data in the first place.
    """
    lines = render_citation_evidence([ENDORSED, PINNED])

    assert len(lines) == 2
    assert any("endorsed sources" in line and ENDORSED in line for line in lines)
    assert any("resolves against the pin" in line and PINNED in line for line in lines)


def test_no_citations_at_all_is_unchanged_from_042() -> None:
    """US6's spirit on the authoring side: a proposal citing nothing behaves as it always did."""
    proposal = _Proposal("Just do it.")

    composed = compose_policy_evidence(
        proposal=proposal, impact=_impact(), resolves=_combined().resolves
    )

    assert UNSUPPORTED_DISCLOSURE in composed.disclosures
