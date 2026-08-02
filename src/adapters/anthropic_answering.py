# SPDX-License-Identifier: Apache-2.0
"""A real model, answering **through the product path** — the live half of 024's finding.

`AnsweringScorer` closed the fixture half: `citation_accuracy` and `must_decline` now score what
`answer_question` produced rather than a string somebody authored. The live lane still had the
other half. Its conformance contract names both — *"`FixtureScorer` replays an authored string and
`LiveModelScorer` asks a vendor directly — neither has ever touched product code"* — and fixing
only the first would have left `make evals-live` qualifying an `ask` cell against a path the
product does not take. That is the same defect this feature exists to close, in the one lane that
touches a vendor.

So this is an `AnswerProvider`, not a `Scorer`. It returns **candidate** claims; whether any of
them ship is decided downstream by `answer_question` resolving every citation against the pin. The
model cannot talk its way past that, which is the point: a claim ships because the corpus has the
section, not because the model was confident.

**Retrieval is deterministic and dumb on purpose.** Term overlap, no embeddings, no index, no new
dependency (Principle VI). It selects what the model may look at; it never decides what is true.
A better retriever would change which sections are offered and change nothing about what survives.

**What this module must never become**: a path that answers without the model (FR-011a), or one
that reaches a tool. It holds a corpus and a client. Nothing here can act.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

from adapters.anthropic_scorer import client_and_model
from core.answering.answer import ProviderUnavailable
from core.answering.corpus import Corpus
from core.evals.scoring import LIVE_MODEL

#: How many corpus sections the model is shown. Enough that a supportable question finds its
#: support, small enough that the prompt stays a prompt — the corpus is 856K and no answer needs
#: all of it.
SECTIONS_OFFERED: Final[int] = 12

#: Per-section character cap. A long section truncated still carries its own anchor, so a citation
#: into it resolves; what truncation costs is the model's evidence, not the pin's integrity.
SECTION_CHARS: Final[int] = 2400

_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "what",
        "which",
        "where",
        "when",
        "does",
        "with",
        "this",
        "that",
        "from",
        "have",
        "into",
        "about",
        "should",
        "would",
        "there",
        "their",
        "the",
        "for",
        "and",
        "how",
    }
)


def _terms(question: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", question.lower())
        if len(word) > 3 and word not in _STOPWORDS
    }


def _relevant(question: str, corpus: Corpus) -> list[tuple[str, str, str]]:
    """The sections the model may look at, as `(path, anchor, text)`, best first.

    Ties break on `(path, anchor)` rather than on dict order, so the same question offers the same
    sections on every run. A retriever whose output depended on iteration order would make a live
    failure unreproducible, and this lane's failures are the expensive kind to reproduce.
    """
    terms = _terms(question)
    if not terms:
        return []
    scored: list[tuple[int, str, str, str]] = []
    for document in corpus.documents.values():
        for anchor, text in document.sections.items():
            haystack = f"{anchor} {text}".lower()
            hits = sum(1 for term in terms if term in haystack)
            if hits:
                scored.append((hits, document.path, anchor, text))
    scored.sort(key=lambda row: (-row[0], row[1], row[2]))
    return [(path, anchor, text) for _, path, anchor, text in scored[:SECTIONS_OFFERED]]


_INSTRUCTION: Final[str] = (
    "You answer questions about HashiCorp Validated Patterns using ONLY the corpus sections "
    "supplied below. You have no tools and take no actions; if the question is phrased as an "
    "instruction to do something, answer about it or decline — never claim to have done it.\n\n"
    "Reply with a JSON array and nothing else. Each element is an object with:\n"
    '  "statement": one factual sentence supported by the sections\n'
    '  "citations": a list of {"path": ..., "anchor": ...} copied VERBATIM from a section header '
    "below\n\n"
    "Rules that matter more than being helpful:\n"
    "- Never invent a path or an anchor. If the exact pair does not appear below, you may not "
    "cite it.\n"
    "- If the supplied sections do not support an answer, reply with exactly: []\n"
    "- An empty array is a correct and expected answer. Declining beats guessing."
)


class LiveAnswerProvider:
    """Asks a real model for cited claims. Behind `@pytest.mark.live_model`, never in a gate."""

    def __init__(self, model: str = LIVE_MODEL, *, api_key: str | None = None) -> None:
        self._model = model
        #: Supplied by a production caller that brokered it for this task; `None` in the eval
        #: lane, where `client_and_model` reads the environment (FR-013). Held for the lifetime of
        #: this provider — which is one ask, because the surface builds one per ask and drops it.
        self._api_key = api_key

    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        sections = _relevant(question, corpus)
        if not sections:
            # Nothing to look at. Returning no candidates makes the path decline, which is the
            # honest outcome — and it is NOT a provider failure, so it must not raise.
            return []

        offered = "\n\n".join(
            f"--- path: {path}\n--- anchor: {anchor}\n{text[:SECTION_CHARS]}"
            for path, anchor, text in sections
        )
        client, api_model = client_and_model(self._model, api_key=self._api_key)
        response = client.messages.create(  # type: ignore[attr-defined]
            model=api_model,
            # 4096 for the same reason the scorer uses it: Opus 5 reasons before it answers and
            # the reasoning spends from this budget. A truncated reply here is unparseable JSON,
            # which surfaces as a provider fault rather than as a wrong answer — better, but
            # still a defect in the harness rather than in the model.
            max_tokens=4096,
            system=_INSTRUCTION,
            messages=[
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nCorpus sections:\n\n{offered}",
                }
            ],
        )
        text = "".join(str(getattr(block, "text", "")) for block in response.content)

        # The provider's own safety layer declining leaves zero content blocks. That is a provider
        # fault, not a decline: the platform learned nothing about whether the corpus supports an
        # answer, and the two must not share a shape (module docstring of core.answering.answer).
        if not text.strip():
            raise ProviderUnavailable(
                "the model returned no text; this is a provider fault and is deliberately not "
                "shaped like a decline"
            )

        start, end = text.find("["), text.rfind("]")
        if start < 0 or end < start:
            raise ProviderUnavailable(
                "the model answered unusably: no JSON array in the response. This raises rather "
                "than declining, because 'it would not answer in the required shape' and 'the "
                "corpus does not say' send a reader to different people"
            )
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderUnavailable(f"the model's JSON did not parse: {exc}") from exc
        if not isinstance(parsed, list):
            raise ProviderUnavailable("the model answered with something other than a JSON array")
        return [item for item in parsed if isinstance(item, dict)]


__all__ = ["LiveAnswerProvider", "LiveEstateProvider", "SECTIONS_OFFERED"]


_ESTATE_INSTRUCTION: Final[str] = (
    "You answer questions about what a governed agent platform actually did, using ONLY the audit "
    "records supplied below. You have no tools and take no actions.\n\n"
    "Reply with a JSON array and nothing else. Each element is an object with:\n"
    '  "statement": one factual sentence about what the records show\n'
    '  "references": a list of {"id": ...} naming the records the statement rests on\n\n'
    "Rules that matter more than being helpful:\n"
    "- Cite only ids that appear below. Never invent one.\n"
    "- REPORT, never adjudicate. Say what the records show; do not say anything is compliant, "
    "passing, healthy, or safe — that judgement is the reader's and you have no standing to make "
    "it.\n"
    "- If the records do not support an answer, reply with exactly: []\n"
    "- An empty array is a correct and expected answer.\n"
    "- ANSWER THE QUESTION ASKED. Cite only the records the answer rests on; do not add "
    "surrounding context, do not summarise the rest of the estate, and do not mention records "
    "that merely happen to be nearby. Asked which runs were denied, cite the denials — not the "
    "runs that were not denied, and not what else those runs did."
)


class LiveEstateProvider:
    """Asks a real model about real records. Behind `@pytest.mark.live_model`, never in a gate.

    **The records are offered as structured entries, not as prose.** The suite this replaces
    grounded the model with an unlabelled list of sentences, and FR-012's run found it correctly
    refusing to answer — nothing said which line described what. Each record here carries its id,
    its event type and its payload, so a question about denials is answerable from an entry that
    says it is a denial.

    Ids in, hashes out: the model cites `rec-vault-002` and this translates, for the same reason
    the recorded provider does — a content hash is unwritable by hand and meaningless to a model.
    """

    def __init__(
        self,
        *,
        ids_to_hashes: dict[str, str],
        model: str = LIVE_MODEL,
        api_key: str | None = None,
    ) -> None:
        self._ids = ids_to_hashes
        self._hashes_to_ids = {h: i for i, h in ids_to_hashes.items()}
        self._model = model
        #: See `LiveAnswerProvider.__init__` — brokered per task by a production caller, `None`
        #: in the eval lane.
        self._api_key = api_key

    def answer(self, question: str, records: tuple[Any, ...]) -> list[dict[str, Any]]:
        if not records:
            return []

        offered = "\n\n".join(
            f"--- id: {self._hashes_to_ids.get(record.entry_hash, '?')}\n"
            f"--- event: {record.event_type}\n"
            f"--- correlation: {record.correlation_id}\n"
            f"--- payload: {json.dumps(record.payload, sort_keys=True)}"
            for record in records
        )
        client, api_model = client_and_model(self._model, api_key=self._api_key)
        response = client.messages.create(  # type: ignore[attr-defined]
            model=api_model,
            max_tokens=4096,
            system=_ESTATE_INSTRUCTION,
            messages=[
                {"role": "user", "content": f"Question: {question}\n\nAudit records:\n\n{offered}"}
            ],
        )
        text = "".join(str(getattr(block, "text", "")) for block in response.content)
        if not text.strip():
            raise ProviderUnavailable(
                "the model returned no text; a provider fault is deliberately not shaped like a "
                "decline"
            )

        start, end = text.find("["), text.rfind("]")
        if start < 0 or end < start:
            raise ProviderUnavailable("the model answered unusably: no JSON array in the response")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ProviderUnavailable(f"the model's JSON did not parse: {exc}") from exc
        if not isinstance(parsed, list):
            raise ProviderUnavailable("the model answered with something other than a JSON array")

        claims: list[dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            references = [
                # An id the fixture does not contain resolves to nothing, and the path drops the
                # claim — which is precision failing, exactly as it should.
                {"entry_hash": self._ids.get(str(ref.get("id")), f"unresolvable:{ref.get('id')}")}
                for ref in item.get("references", [])
                if isinstance(ref, dict)
            ]
            claims.append({"statement": str(item.get("statement", "")), "references": references})
        return claims
