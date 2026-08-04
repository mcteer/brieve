# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed, GATE:correlation — an answer is cited, or it is a decline.

**Every row here would have failed before this feature**, because there was nothing to ask. Four
eval suites were green over authored recordings of runs that never happened; these are the rows
that make the difference between a capability and a claim about one.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Any

import pytest

from core.answering.answer import (
    ANSWERED,
    DECLINED,
    ProviderUnavailable,
    answer_question,
)
from core.answering.corpus import Corpus, CorpusUnavailable, Document, load_corpus
from core.answering.streams import ask_stream_for

REAL_PATH = "/validated-patterns/vault/vault-agent-approle"


def _corpus() -> Corpus:
    return Corpus(
        digest="digest-under-test",
        documents={
            REAL_PATH: Document(
                path=REAL_PATH,
                url="https://developer.hashicorp.com" + REAL_PATH,
                digest="d",
                anchors=frozenset({"prerequisites", "conclusion"}),
            )
        },
    )


class _Provider:
    def __init__(self, claims: list[dict[str, Any]]) -> None:
        self._claims = claims

    def answer(self, question: str, corpus: Corpus, context: str = "") -> list[dict[str, Any]]:
        return self._claims


class _Unreachable:
    def answer(self, question: str, corpus: Corpus, context: str = "") -> list[dict[str, Any]]:
        raise ConnectionError("no route to provider")


def _claim(anchor: str, statement: str = "A supported statement.") -> dict[str, Any]:
    return {"statement": statement, "citations": [{"path": REAL_PATH, "anchor": anchor}]}


# ---------------------------------------------------------------- a cited answer


def test_an_answer_carries_resolvable_citations() -> None:
    """FR-002. Every claim rests on a section that exists."""
    result = answer_question(
        question="How does Vault Agent use AppRole?",
        corpus=_corpus(),
        provider=_Provider([_claim("prerequisites")]),
    )
    assert result.disposition == ANSWERED
    assert len(result.claims) == 1
    assert result.claims[0].citations[0].anchor == "prerequisites"
    assert result.corpus_digest == "digest-under-test"


def test_a_claim_whose_citation_does_not_resolve_does_not_ship() -> None:
    """**The single most important row in this feature.**

    An unresolvable citation is worse than none: it reads as evidence, and a reader who follows it
    and finds nothing has been told something false about what this platform knows.
    """
    result = answer_question(
        question="anything",
        corpus=_corpus(),
        provider=_Provider([_claim("a-section-that-does-not-exist", "Confident and unsupported.")]),
    )
    assert result.disposition == DECLINED
    assert "Confident and unsupported." in result.dropped
    assert result.claims == ()


def test_one_bad_citation_sinks_its_whole_claim() -> None:
    """A claim resting partly on something that does not exist rests partly on nothing."""
    mixed = {
        "statement": "Half-supported.",
        "citations": [
            {"path": REAL_PATH, "anchor": "prerequisites"},
            {"path": REAL_PATH, "anchor": "invented"},
        ],
    }
    result = answer_question(question="q", corpus=_corpus(), provider=_Provider([mixed]))
    assert result.disposition == DECLINED


def test_declining_names_what_was_missing() -> None:
    """FR-003. Declining beats confabulating, and says which kind of nothing it found."""
    empty = answer_question(question="q", corpus=_corpus(), provider=_Provider([]))
    assert empty.disposition == DECLINED
    assert "does not support" in empty.declined_reason

    unresolvable = answer_question(
        question="q", corpus=_corpus(), provider=_Provider([_claim("nope")])
    )
    assert "does not resolve" in unresolvable.declined_reason


# ---------------------------------------------------------------- GATE:fail-closed


def test_an_unreachable_provider_fails_rather_than_declining() -> None:
    """FR-011. A reader cannot tell "I can't help" from "the corpus does not say".

    One sends them to an operator and the other to the corpus, so they must not share a shape.
    """
    with pytest.raises(ProviderUnavailable):
        answer_question(question="q", corpus=_corpus(), provider=_Unreachable())


def test_there_is_no_answer_without_the_model() -> None:
    """FR-011a. No fallback path that omits the provider.

    A second path no gate scores is exactly how four suites came to be green over material nothing
    produced. `answer_question` takes the provider as a required argument — there is no call that
    omits it.
    """
    import inspect

    from core.answering.answer import answer_question as fn

    provider = inspect.signature(fn).parameters["provider"]
    assert provider.default is inspect.Parameter.empty


def test_a_corpus_that_does_not_match_its_pin_is_refused() -> None:
    """FR-014. A digest mismatch is a refusal, never a silent fallback."""
    with pytest.raises(CorpusUnavailable):
        load_corpus(manifest=pathlib.Path("/nonexistent/manifest.json"))


# ---------------------------------------------------------------- GATE:never-acts


def test_the_answering_path_reaches_no_tool_or_authority_module() -> None:
    """FR-006/FR-008, asserted on **imports** rather than on prose.

    A first version of this row searched the source text and failed on the docstring saying the
    path holds no tool registry — matching documentation instead of behaviour. This reads the
    module's actual imports, so it cannot pass because of what the file says about itself.

    Never-acts is satisfied by what the path does not hold. Granting the ability to act means
    *adding* an import here, which is visible in review.
    """
    tree = ast.parse(pathlib.Path("src/core/answering/answer.py").read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    forbidden = {"registry", "authority", "tools", "hooks", "invoke"}
    offending = [m for m in imported if any(word in m for word in forbidden)]
    assert not offending, (
        f"the answering path imports {offending} — never-acts is meant to hold because this "
        "module cannot reach a tool, not because it was told not to"
    )


# ---------------------------------------------------------------- GATE:correlation


def test_the_ask_stream_is_stable_per_tenant() -> None:
    """FR-012a. An ask has no run and no thread, so it needed a placement of its own.

    Stable rather than per-ask, for the reason `evidence-access` already records: a fresh
    correlation id each time makes every record a chain of one, linked to nothing and removable
    without trace.
    """
    assert ask_stream_for("tenant-a") == "ask:tenant-a"
    assert ask_stream_for("tenant-a") == ask_stream_for("tenant-a")
    assert ask_stream_for("tenant-a") != ask_stream_for("tenant-b")


# ---------------------------------------------------------------- the real corpus


def test_the_pinned_corpus_has_the_properties_the_design_assumes() -> None:
    """T004a. Three claims carried from prior context, none checkable here until now.

    If anchors were unstable, section-level citations would not work and this feature would have a
    different shape — far cheaper to learn from a row than from an implementation.
    """
    corpus = load_corpus(verify=False)

    # A FLOOR AND THE PROPERTIES, not a count. This asserted exactly 33 — true of the corpus
    # 024 pinned and false the moment 035 added Validated Designs. The claims worth holding are
    # that the pin is not empty or collapsed, that every document carries usable anchors, and
    # that page chrome stays out; the size is a fact about today's corpus, not a design property.
    assert len(corpus.documents) >= 33, "the corpus shrank — a pin this small answers nothing"
    assert all(doc.anchors for doc in corpus.documents.values())
    # Chrome is excluded structurally: `sidebar-label` appeared in all 33 before the fix.
    assert not any("sidebar-label" in doc.anchors for doc in corpus.documents.values())

    # BOTH FAMILIES, which is 035's whole claim. Patterns tell you how to integrate two things;
    # designs tell you how to build one. A corpus holding only the first declines every question
    # about architecture — correctly, and uselessly.
    paths = set(corpus.documents)
    assert any("/validated-patterns/" in p for p in paths), "no integration guidance is pinned"
    assert any("/validated-designs/" in p for p in paths), (
        "no reference architecture is pinned — this is the gap that made 'how do I build a "
        "Vault cluster in AWS' unanswerable"
    )


def test_an_ask_record_carries_shape_and_never_content() -> None:
    """FR-012, GATE:no-secret-leak.

    The corpus is somebody else's copyrighted documentation. Copying a passage into an append-only
    trail that does not egress by default would be both a leak and a licensing problem — so the
    record names which corpus was consulted, not what it said.
    """
    from datetime import UTC, datetime

    from core.answering.record import record_ask
    from core.audit.sink import InMemoryAuditSink
    from core.identity.types import AuthenticatedSubject, SubjectKind

    sink = InMemoryAuditSink()
    subject = AuthenticatedSubject(
        subject_user_id="alice",
        tenant_id="tenant-a",
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    record_ask(
        audit=sink,
        subject=subject,
        corpus_digest="f854d621",
        evidence_stream="",
        model="anthropic/claude-opus@5",
        disposition="answered",
        source="guidance",
        cell="vault:anthropic/claude-opus@5:ask",
        bound_cell="vault:anthropic/claude-opus@5:ask",
        cell_disposition="pinned",
        model_authority="vault:model-credentials/anthropic@v3",
    )

    entries = sink.list_by_correlation_id(ask_stream_for("tenant-a"))
    assert len(entries) == 1
    payload = entries[0].payload
    assert payload["subject_user_id"] == "alice"
    assert payload["corpus_digest"] == "f854d621"
    # 025 adds `source`. The set is EXACT rather than a superset check, which is why this row
    # fires on a deliberate change as loudly as on an accidental one — a payload contract nobody
    # is forced to look at is a payload contract that grows a content field eventually.
    # 026 adds cell/bound_cell/cell_disposition. EXACT set, still — the row fires on a
    # deliberate change as loudly as on an accidental one, which is why it keeps catching these.
    # 027 adds `model_authority`, the fifth feature in five to extend this payload. The exactness
    # is what makes each of those a decision somebody had to write down.
    assert set(payload) == {
        "subject_user_id",
        "corpus_digest",
        "model",
        "disposition",
        "source",
        "evidence_stream",
        "cell",
        "bound_cell",
        "cell_disposition",
        "model_authority",
    }
    assert payload["source"] == "guidance"
    assert payload["cell_disposition"] == "pinned"
    # A REFERENCE, never a value — the property the whole field exists for. `vault:` and a version
    # generation, and nothing that could be presented to a vendor.
    assert payload["model_authority"] == "vault:model-credentials/anthropic@v3"
    assert "question" not in payload and "answer" not in payload


# ------------------------------------------------------------------ 035: retrieval at scale


def test_short_but_distinctive_terms_survive_extraction() -> None:
    """The four-character floor dropped exactly the words that make a question specific.

    "AWS", "PKI", "KMS", "IAM", "SSH" — every one is the most informative token in the question
    it appears in, and every one was discarded before scoring began. Measured on the question
    that started 035: "build a Vault cluster in AWS" lost "aws" and retrieved landing-zone pages
    for other clouds.
    """
    from adapters.anthropic_answering import _terms

    assert "aws" in _terms("How do I build a Vault cluster in AWS?")
    assert "pki" in _terms("What is the PKI guidance?")
    # Still no noise: two-character and stopword tokens stay out.
    assert _terms("What is it in the a?") == set()


def test_a_rare_term_outranks_a_common_one() -> None:
    """Rarity weighting, asserted on a corpus where the answer is obvious.

    Counting how many query terms appear treats "vault" — in nearly every section — as worth
    the same as the one word that distinguishes the question. At 33 documents that was
    survivable; at 238 it meant ties everywhere, broken alphabetically, so the winner was
    decided by path order rather than by relevance.
    """
    from adapters.anthropic_answering import _relevant
    from core.answering.corpus import Corpus, Document

    common = Document(
        path="/a-common",
        url="https://example.test/a",
        digest="d" * 64,
        anchors=frozenset({"s"}),
        sections={"s": "vault vault vault"},
    )
    rare = Document(
        path="/z-rare",
        url="https://example.test/z",
        digest="e" * 64,
        anchors=frozenset({"s"}),
        sections={"s": "vault autopilot redundancy zones"},
    )
    filler = {
        f"/filler-{n}": Document(
            path=f"/filler-{n}",
            url=f"https://example.test/{n}",
            digest="f" * 64,
            anchors=frozenset({"s"}),
            sections={"s": "vault"},
        )
        for n in range(20)
    }
    corpus = Corpus(
        digest="c" * 64,
        documents={common.path: common, rare.path: rare, **filler},
    )

    best = _relevant("vault autopilot", corpus)[0]

    assert best[0] == "/z-rare", (
        "the section sharing the RARE term lost to one repeating the common term — which is "
        "what alphabetical tie-breaking did across the whole corpus"
    )


def test_no_single_document_takes_every_offered_slot() -> None:
    """Diversity. One document's twelve sections are worse evidence than four documents' three.

    Measured: "build a Vault cluster in AWS" filled every slot from a single Terraform
    landing-zone page, so the model saw one document's view of the question and the Vault
    architecture guide never reached it.
    """
    from adapters.anthropic_answering import SECTIONS_PER_DOCUMENT, _relevant
    from core.answering.corpus import Corpus, Document

    hog = Document(
        path="/hog",
        url="https://example.test/hog",
        digest="d" * 64,
        anchors=frozenset(f"s{n}" for n in range(20)),
        sections={f"s{n}": "vault cluster architecture" for n in range(20)},
    )
    other = Document(
        path="/other",
        url="https://example.test/other",
        digest="e" * 64,
        anchors=frozenset({"s"}),
        sections={"s": "vault cluster architecture"},
    )
    corpus = Corpus(digest="c" * 64, documents={hog.path: hog, other.path: other})

    offered = _relevant("vault cluster architecture", corpus)
    from_hog = [row for row in offered if row[0] == "/hog"]

    assert len(from_hog) <= SECTIONS_PER_DOCUMENT
    assert any(row[0] == "/other" for row in offered), "a second source never got a slot"
