# SPDX-License-Identifier: Apache-2.0
"""E18–E21 — a customer's own documents are citable, and the answer says so (045, T020, US5).

**Citable, not merely readable.** `answer.py` drops any claim whose citations do not resolve,
so customer material that the platform could read but not cite would produce declines on every
question it should have answered. These rows exercise the whole path — provider to payload —
because that is where the difference between "read" and "cited" actually shows.

**Provenance is data, not presentation** (clarify Q2). A reader acting on "your own standard
says so" is in a different position from one acting on "HashiCorp's validated design says so",
and an interface that renders both identically has told them they are the same.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient

from core.answering.corpus import Corpus, Document
from core.answering.endorsed.corpus import (
    CUSTOMER_ENDORSED,
    VALIDATED_DESIGN,
    CombinedCorpus,
    build_endorsed_corpus,
    provenance_of,
)
from core.answering.endorsed.records import (
    ADOPTED,
    EndorsedDocument,
    SyncedVersion,
    digest_of_document,
)
from tests.harness.api_fixtures import (
    available_credential,
    qualified_ask_authority,
    surface_under_test,
)

ENDORSED_PATH = "/endorsed/acme-standards/logging.md"
#: A path that is really in the vendored corpus, at an anchor that really exists. The route
#: calls `load_corpus()`, so an invented path would decline for the right reason and prove
#: nothing about provenance — which is what a first version of these rows did.
PINNED_PATH = "/validated-patterns/vault/vault-agent-approle"
PINNED_ANCHOR = "conclusion"


def _endorsed_document(path: str = ENDORSED_PATH) -> EndorsedDocument:
    sections = {"retention": "Logs are retained for 400 days."}
    return EndorsedDocument(
        path=path,
        url=f"https://git.example.com/acme/standards{path}",
        digest=digest_of_document(sections),
        anchors=frozenset(sections),
        sections=dict(sections),
    )


def _endorsed(synced_at: datetime | None = None) -> Any:
    return build_endorsed_corpus(
        [
            SyncedVersion(
                version_id="v-one",
                tenant_id="acme",
                source="acme-standards",
                upstream_tip="abc123",
                synced_at=synced_at or datetime(2026, 8, 1, tzinfo=UTC),
                synced_by="dan@acme.example",
                state=ADOPTED,
                documents={ENDORSED_PATH: _endorsed_document()},
            )
        ]
    )


def _pinned() -> Corpus:
    return Corpus(
        digest="corpus-digest",
        documents={
            PINNED_PATH: Document(
                path=PINNED_PATH,
                url=f"https://developer.hashicorp.com{PINNED_PATH}",
                digest="d",
                anchors=frozenset({"clustering"}),
                sections={"clustering": "A Vault cluster spans availability zones."},
            )
        },
        synced_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


class _Cites:
    """A provider that cites whatever it is told to, so the row is about resolution."""

    def __init__(self, citations: list[tuple[str, str]], statement: str = "It says so.") -> None:
        self._citations = citations
        self._statement = statement

    def answer(self, question: str, corpus: Any, context: str = "") -> list[dict[str, Any]]:
        return [
            {
                "statement": self._statement,
                "citations": [{"path": path, "anchor": anchor} for path, anchor in self._citations],
            }
        ]


def _ask(citations: list[tuple[str, str]], *, endorsed: Any = None, **over: Any) -> Any:
    """Drive the real ask route with a combined corpus in place."""
    reader = (lambda: endorsed) if endorsed is not None else None
    surface = surface_under_test(
        ask_provider=_Cites(citations),
        ask_model="anthropic/claude-opus@5",
        ask_authority=qualified_ask_authority(),
        credential_source=available_credential(),
        endorsed_reader=reader,
        **over,
    )
    response = TestClient(surface.app).post(
        "/ask", json={"question": "How long are logs retained?"}, headers=surface.bearer()
    )
    return surface, response


# ── E18: a customer-only question is answered, with citations that resolve ────────────────


def test_row_e18_a_question_only_the_customers_documents_answer_is_answered() -> None:
    """The point of the whole feature, and the thing the citation gate would otherwise block.

    Without citability, every answer grounded in customer material declines — the platform
    would have read the documents and been unable to say anything from them.
    """
    _, response = _ask([(ENDORSED_PATH, "retention")], endorsed=_endorsed())

    body = response.json()
    assert response.status_code == 200
    assert body["disposition"] == "answered"
    assert body["citations"][0]["url"].startswith("https://git.example.com")


def test_row_e18_a_path_in_neither_corpus_does_not_resolve() -> None:
    """FR-013. The gate is unchanged for content the platform does not hold.

    An endorsed namespace that made *any* `/endorsed/…` path resolve would be the weakening
    US6 exists to prevent, arriving from the new side rather than the old one.
    """
    _, response = _ask(
        [("/endorsed/acme-standards/nonexistent.md", "retention")], endorsed=_endorsed()
    )

    body = response.json()
    assert body["disposition"] != "answered"


def test_row_e18_an_anchor_that_does_not_exist_does_not_resolve() -> None:
    """A citation into a real document at a section nobody wrote lands nowhere for the reader."""
    _, response = _ask([(ENDORSED_PATH, "no-such-section")], endorsed=_endorsed())

    assert response.json()["disposition"] != "answered"


# ── E19: per-citation provenance, and a mixed answer naming both ──────────────────────────


def test_row_e19_every_citation_carries_its_provenance_as_data() -> None:
    """Clarify Q2. Derivable from the path and emitted anyway — a prefix convention read in
    every consumer is how conventions decay (038's payload table)."""
    _, response = _ask([(ENDORSED_PATH, "retention")], endorsed=_endorsed())

    citation = response.json()["citations"][0]
    assert citation["provenance"] == CUSTOMER_ENDORSED


def test_row_e19_a_validated_design_citation_says_so_too() -> None:
    """Both directions, because a field only ever taking one value asserts nothing."""
    _, response = _ask([(PINNED_PATH, PINNED_ANCHOR)], endorsed=_endorsed())

    citation = response.json()["citations"][0]
    assert citation["provenance"] == VALIDATED_DESIGN


def test_row_e19_a_mixed_answer_names_both_and_each_citation_says_which() -> None:
    """The case a summary alone would flatten.

    An answer resting on both must not let the reader assume either one carries the whole
    weight — so the note names both AND each citation is individually attributable.
    """
    _, response = _ask(
        [(PINNED_PATH, PINNED_ANCHOR), (ENDORSED_PATH, "retention")], endorsed=_endorsed()
    )

    body = response.json()
    kinds = {c["provenance"] for c in body["citations"]}
    assert kinds == {VALIDATED_DESIGN, CUSTOMER_ENDORSED}
    assert "both" in body["grounding_note"]


def test_row_e19_an_answer_from_the_corpus_alone_does_not_claim_endorsed_material() -> None:
    """The note is composed from what was CITED, not from what was configured.

    An answer that could have used endorsed material and did not must not say it did — that is
    a disclosure misleading in the direction of authority, which is the worst direction.
    """
    _, response = _ask([(PINNED_PATH, PINNED_ANCHOR)], endorsed=_endorsed())

    note = response.json()["grounding_note"]
    assert "validated designs" in note
    assert "endorsed" not in note


def test_row_e19_the_response_names_the_endorsed_version_it_rested_on() -> None:
    """An answer a person keeps should name its ground well enough to look at again."""
    _, response = _ask([(ENDORSED_PATH, "retention")], endorsed=_endorsed())

    assert response.json()["endorsed_version"] == "v-one"


def test_provenance_has_exactly_one_reader() -> None:
    """The convention's single point of truth, asserted directly as well as through the route."""
    assert provenance_of(ENDORSED_PATH) == CUSTOMER_ENDORSED
    assert provenance_of(PINNED_PATH) == VALIDATED_DESIGN


# ── E20: a document with no addressable section is not citable ─────────────────────────────


def test_row_e20_a_document_with_no_anchors_resolves_nothing() -> None:
    """FR-011. Never cited whole — a citation to a file as a unit lands where no claim was made.

    The sync reports such documents rather than dropping them silently (asserted in
    `test_sync.py`); this is the other half, that they genuinely cannot be cited.
    """
    empty = EndorsedDocument(
        path=ENDORSED_PATH,
        url="https://git.example.com/acme/standards/logging.md",
        digest="d",
        anchors=frozenset(),
    )
    corpus = build_endorsed_corpus(
        [
            SyncedVersion(
                version_id="v-empty",
                tenant_id="acme",
                source="acme-standards",
                upstream_tip="abc",
                synced_at=datetime(2026, 8, 1, tzinfo=UTC),
                synced_by="dan",
                state=ADOPTED,
                documents={ENDORSED_PATH: empty},
            )
        ]
    )

    assert not corpus.resolves(ENDORSED_PATH, "retention")
    assert not corpus.resolves(ENDORSED_PATH, "")


# ── E21: the age disclosed is the adopted version's ───────────────────────────────────────


def test_row_e21_the_age_disclosed_covers_the_endorsed_material_too() -> None:
    """FR-017b. Customer material can be stale in exactly the way validated designs can.

    The older of the two, so the disclosure describes the staleness a reader could actually be
    affected by — a corpus re-pinned this morning must not vouch for material synced in January.
    """
    combined = CombinedCorpus(
        pinned=_pinned(), endorsed=_endorsed(synced_at=datetime(2026, 1, 1, tzinfo=UTC))
    )

    assert combined.synced_at == datetime(2026, 1, 1, tzinfo=UTC)


def test_row_e21_the_answer_carries_a_ground_note_when_endorsed_material_is_in_use() -> None:
    """Through the route, because a property held by a dataclass and rendered nowhere is 043's
    `relevance_note` defect repeating."""
    _, response = _ask([(ENDORSED_PATH, "retention")], endorsed=_endorsed())

    assert response.json()["ground_note"]


# ── US6 at the surface: with nothing endorsed, nothing changes ────────────────────────────


def test_with_no_endorsed_reader_the_response_is_shaped_exactly_as_before() -> None:
    """The estate every deployment is in until somebody endorses something.

    No `endorsed_version`, no `grounding_note` naming customer material — because the answer
    rests on what it always rested on, and a field that appears everywhere meaning nothing is
    how a disclosure stops being read.
    """
    _, response = _ask([(PINNED_PATH, PINNED_ANCHOR)])

    body = response.json()
    assert body["disposition"] == "answered"
    assert "endorsed_version" not in body
    assert "endorsed" not in body["grounding_note"]
