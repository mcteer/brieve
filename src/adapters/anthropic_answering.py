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
import math
import re
from typing import Any, Final

from adapters.anthropic_scorer import client_and_model
from core.answering.answer import ProviderUnavailable
from core.answering.context import QUESTION_MARKER
from core.answering.corpus import Corpus
from core.evals.scoring import LIVE_MODEL

#: How many corpus sections the model is shown.
#:
#: THIRTY, BECAUSE RETRIEVAL IS NOT THE PARTY THAT SHOULD BE DECIDING RELEVANCE. At twelve this
#: retriever had to be right about the top twelve of ~2,500 sections, and when it was wrong the
#: person got "the pinned corpus does not support an answer" about material the corpus plainly
#: holds. Considerable effort went into making the ranking better — BM25, length normalisation,
#: coordination, splitting the heading from the path — and every one of those was measured
#: against the live model and every one made things worse or no better.
#:
#: What worked was giving the model more to read. Measured over six phrasings of questions this
#: corpus answers, with two samples each:
#:
#:     12 sections → 3/12 empty        20 sections → 3/12 empty        30 sections → 0/12 empty
#:
#: and 0/24 on a confirmation run. The phrasing that failed at EVERY ranking configuration
#: answers at thirty.
#:
#: That is the honest division of labour. Ranking picks what to look at and is imperfect; the
#: model reads and judges, and it is the only party here that can tell whether a section bears
#: on the question. Widening the aperture costs prompt tokens — about 2.5x, still well inside
#: the 180s the portal waits — and buys the difference between a platform that answers and one
#: that tells people it has nothing.
SECTIONS_OFFERED: Final[int] = 30

#: At most this many sections from any one document, so the offered set spans sources rather
#: than exhausting the highest-scoring page. See `_relevant` for what this cost and bought.
SECTIONS_PER_DOCUMENT: Final[int] = 3

#: What a HEADING is worth against a mention in the body — the document path and the section
#: anchor together.
#:
#: Splitting these was tried and measured worse. The argument for splitting was sound — a path
#: term lifts every section of a document identically and so cannot say which of them answers
#: the question — but against the live model it took empty answers from 2/12 to 4/12, and the
#: measurement wins over the argument. Recorded so nobody re-derives it.
HEADING_WEIGHT: Final[float] = 3.0

#: Per-section character cap. A long section truncated still carries its own anchor, so a citation
#: into it resolves; what truncation costs is the model's evidence, not the pin's integrity.
SECTION_CHARS: Final[int] = 2400

#: How many times the model is asked before the platform will say the corpus is silent.
#:
#: Three, and the shape of the arithmetic is why: an empty draw was measured at roughly one in
#: six, so one attempt tells a person the corpus has nothing about 17% of the time it does,
#: two gets that under 3%, and three under 0.5%. Beyond three the return is negligible against
#: a latency a person is waiting through.
#:
#: The cost is paid ONLY on the failing path — an answer on the first draw is returned on the
#: first draw — so the expected spend is about 1.2 calls per ask rather than 3.
ATTEMPTS_BEFORE_SILENCE: Final[int] = 3

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
        # WORDS THAT SAY WHAT THE ASKER WANTS, NOT WHAT THEY ARE ASKING ABOUT.
        #
        # These carry no topic, and left in they do active harm, because they collide with
        # BOILERPLATE HEADINGS. Asked *"what's the best way to run a Vault cluster on AWS?"*
        # the retriever scored `best` against every "Background and best practices" and
        # "Operational best practices" section in the corpus — a heading that appears in
        # nearly every document — and the heading boost floated them to the top. The offered
        # set came back as five best-practice preambles and a Vault Radar CLI page, the model
        # correctly found nothing in it about running a cluster, and the person was told the
        # pinned corpus does not support an answer. Drop `best` and `way` from the same
        # question and it returns seven cited claims.
        #
        # That is the whole class: a person's phrasing of INTENT ("the best way", "the
        # prescribed approach", "how am I supposed to") matching a document's furniture. Every
        # word here is one nobody would search for on its own, and none of them names anything
        # this corpus is about — `deploy`, `install`, `size`, `upgrade` and the rest are topic
        # words and stay.
        "best",
        "better",
        "good",
        "right",
        "correct",
        "proper",
        "properly",
        "prescribed",
        "recommended",
        "recommend",
        "preferred",
        "ideal",
        "optimal",
        "way",
        "ways",
        "approach",
        "supposed",
        "want",
        "need",
        "please",
        "guide",
        "explain",
    }
)


def _terms(question: str) -> set[str]:
    return {
        word
        for word in re.findall(r"[a-z0-9]+", question.lower())
        # Three characters, not four: "aws", "gcp", "kms", "pki", "ssh", "iam" are exactly the
        # words that make a question specific, and a four-character floor silently dropped
        # every one of them. "What is the prescribed way to build a Vault cluster in AWS?"
        # lost its most distinctive term before scoring began.
        if len(word) > 2 and word not in _STOPWORDS
    }


def _retrieval_query(question: str, context: str) -> str:
    """The question, widened by the subject of the conversation it sits in (035).

    Only the earlier QUESTIONS are added. Claim statements are prose and would swamp the few
    terms that actually name the subject; a question is the shortest thing that says what is
    being talked about. Empty context returns the question untouched, so a standalone ask
    retrieves exactly as it always has.
    """
    if not context:
        return question
    asked = [
        line.partition(QUESTION_MARKER)[2].strip()
        for line in context.splitlines()
        if QUESTION_MARKER in line
    ]
    return " ".join([question, *asked]) if asked else question


def _relevant(question: str, corpus: Corpus) -> list[tuple[str, str, str]]:
    """The sections the model may look at, as `(path, anchor, text)`, best first.

    **Rarity-weighted, and 035 is why.** This counted how many query terms appeared in a section
    and broke ties alphabetically. At 33 documents that was adequate. At 238 it was not: every
    section mentioning "vault" scored the same, so the winners were decided by path order, and
    "What is the prescribed way to build a Vault cluster in AWS?" was answered — or rather
    declined — from `vault-operating-guides-adoption/static-secrets` while the Vault Enterprise
    architecture guide's own `#cluster` section sat unread because 'o' sorts before 's'.

    So a term is worth what it distinguishes. A word in nearly every section carries almost no
    weight; a word in three sections carries a lot. That is plain inverse document frequency,
    computed over the corpus at hand rather than pinned, because the corpus is the population.

    **Where a term appears matters too.** A section whose own anchor or document path contains
    the term is about it; a section that merely mentions it in passing is not. Both are counted,
    the heading more heavily, which is what pulls a document NAMED for Vault architecture above
    one that happens to say the word.

    Ties still break on `(path, anchor)`, so the same question offers the same sections on every
    run — a retriever whose output depended on iteration order would make a live failure
    unreproducible, and this lane's failures are the expensive kind to reproduce.
    """
    terms = _terms(question)
    if not terms:
        return []

    sections = [
        (document.path, anchor, text)
        for document in corpus.documents.values()
        for anchor, text in document.sections.items()
    ]
    if not sections:
        return []

    # How many sections each term appears in, which is what makes it worth something.
    frequency = {
        term: sum(1 for path, anchor, text in sections if term in f"{path} {anchor} {text}".lower())
        for term in terms
    }
    total = len(sections)

    scored: list[tuple[float, str, str, str]] = []
    for path, anchor, text in sections:
        body = text.lower()
        heading = f"{path} {anchor}".lower()
        score = 0.0
        for term in terms:
            appearances = frequency[term]
            if not appearances:
                continue
            # Rare terms dominate; a term in every section contributes almost nothing.
            weight = math.log(total / appearances) + 1.0
            if term in heading:
                # Named for it, not merely mentioning it.
                score += weight * HEADING_WEIGHT
            elif term in body:
                score += weight
        if score:
            scored.append((score, path, anchor, text))

    scored.sort(key=lambda row: (-row[0], row[1], row[2]))

    # DIVERSITY, because one document taking every slot is worse evidence than several taking a
    # few. Measured: "build a Vault cluster in AWS" filled all twelve slots from a single
    # Terraform landing-zone page — every section of it outranked the Vault Enterprise
    # architecture guide, so the model saw one document's view of the question and nothing else.
    # A per-document cap costs the twelfth-best section of a strong document and buys the
    # best section of the next four.
    chosen: list[tuple[str, str, str]] = []
    per_document: dict[str, int] = {}
    for _score, path, anchor, text in scored:
        if per_document.get(path, 0) >= SECTIONS_PER_DOCUMENT:
            continue
        per_document[path] = per_document.get(path, 0) + 1
        chosen.append((path, anchor, text))
        if len(chosen) == SECTIONS_OFFERED:
            break
    return chosen


_INSTRUCTION: Final[str] = (
    # THE CORPUS IS TWO FAMILIES NOW, AND SAYING ONE OF THEM WAS A REAL REFUSAL (035). This
    # read "HashiCorp Validated Patterns", so a model handed reference-architecture sections
    # from a Validated DESIGN was told it answers questions about something else — and it
    # declined, correctly following an instruction that had gone stale under it.
    "You answer questions about HashiCorp Validated Patterns (integration guidance) and "
    "HashiCorp Validated Designs (reference architecture: how to build and operate these "
    "products) using ONLY the corpus sections supplied below. You have no tools and take no "
    "actions; if the question is phrased as an instruction to do something, answer about it or "
    "decline — never claim to have done it.\n\n"
    "Reply with a JSON array and nothing else. Each element is an object with:\n"
    '  "statement": one factual sentence supported by the sections\n'
    '  "citations": a list of {"path": ..., "anchor": ...} copied VERBATIM from a section header '
    "below\n\n"
    "Rules that matter more than being helpful:\n"
    "- Never invent a path or an anchor. If the exact pair does not appear below, you may not "
    "cite it.\n"
    "- If the supplied sections do not support an answer, reply with exactly: []\n"
    "- An empty array is a correct and expected answer. Declining beats guessing.\n"
    "- But ANSWER WHAT THE SECTIONS DO SUPPORT. A question about building or operating a "
    "product is answerable from architecture and operating guidance even when no section is "
    "titled with the question's exact words; state what the sections establish and cite them. "
    "Declining because no section repeats the question back is not the same as declining "
    "because the corpus is silent."
)


class LiveAnswerProvider:
    """Asks a real model for cited claims. Behind `@pytest.mark.live_model`, never in a gate."""

    def __init__(self, model: str = LIVE_MODEL, *, api_key: str | None = None) -> None:
        self._model = model
        #: Supplied by a production caller that brokered it for this task; `None` in the eval
        #: lane, where `client_and_model` reads the environment (FR-013). Held for the lifetime of
        #: this provider — which is one ask, because the surface builds one per ask and drops it.
        self._api_key = api_key

    def answer(self, question: str, corpus: Corpus, context: str = "") -> list[dict[str, Any]]:
        """Candidate claims, or nothing — and *nothing* is asked more than once.

        `context` is earlier conversation (035), placed BEFORE the question and clearly
        labelled as not-corpus.

        **Retrieval sees the conversation's SUBJECT, and the plan said it should not.** The
        argument for keeping it out was that a follow-up's subject belongs in the model's
        understanding rather than in the search. Measured against the live model it was wrong
        in the only way that counts: "and the clients?" carries one word, retrieved Consul DNS
        and Windows containers, and the model — correctly — could not answer about Nomad
        clients from material about neither. Three of ten follow-ups came back empty.

        So the earlier QUESTIONS widen the query, and only the questions: claim statements are
        long enough to swamp the terms that matter, and the question is what names the subject.
        Nothing about what may be CITED changes — the sections still have to resolve, and
        history still carries no citations to resolve through.

        **A DECLINE IS A STATEMENT ABOUT THE CORPUS, SO ONE DRAW MUST NOT MAKE IT.** Told "the
        pinned corpus does not support an answer to this question", a person concludes the
        platform has no guidance on what they asked and stops asking. That sentence has to be
        true. Taken from a single sample it frequently was not: measured on 2026-08-03 against
        the 238-document corpus, *"the prescribed way to build a Vault cluster in AWS"* came
        back empty roughly one time in six and returned six or seven well-cited claims the
        rest — same question, same corpus, same model. The maintainer asked once, drew the
        empty one, and was told the corpus was silent about the most documented thing we ship.

        The eval lane already refuses to trust one draw; it scores each case by majority of
        three, on the reasoning that *"a deterministic sample would still be one draw from the
        distribution"*. That control belongs here more than it belongs there — a qualification
        run that gets it wrong costs a retry, and this costs a person's belief that the
        platform knows anything.

        So an EMPTY answer is retried, and only an empty one. This never shops for a better
        answer: any claims at all end it, including a single weak one, because re-asking a
        model that answered is how a harness talks itself into the reply it wanted. And it
        cannot manufacture support — every claim still has to cite a section that resolves in
        the pin, so a retry can only find what was already there.

        Temperature would be the other lever and is not available: these models reject the
        parameter outright (see `anthropic_scorer`). Sampling again is the vendor-neutral form
        of the same idea, which is what it needs to be — nothing here may assume a vendor.
        """
        sections = _relevant(_retrieval_query(question, context), corpus)
        if not sections:
            # Nothing to look at. Returning no candidates makes the path decline, which is the
            # honest outcome — and it is NOT a provider failure, so it must not raise.
            return []

        offered = "\n\n".join(
            f"--- path: {path}\n--- anchor: {anchor}\n{text[:SECTION_CHARS]}"
            for path, anchor, text in sections
        )
        for remaining in range(ATTEMPTS_BEFORE_SILENCE - 1, -1, -1):
            claims = self._ask_once(question, offered, context)
            if claims or not remaining:
                return claims
        return []  # pragma: no cover — the loop always returns

    def _ask_once(self, question: str, offered: str, context: str = "") -> list[dict[str, Any]]:
        """One draw. Raises on a provider fault; returns `[]` when the model found nothing."""
        client, api_model = client_and_model(self._model, api_key=self._api_key)
        # History first, then the question, then the material. The order is the reading order:
        # what we were talking about, what is being asked now, and what may be cited.
        prologue = f"{context}\n\n" if context else ""
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
                    "content": (f"{prologue}Question: {question}\n\nCorpus sections:\n\n{offered}"),
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
    "runs that were not denied, and not what else those runs did.\n"
    "- Completeness is that rule's twin, and it cuts within the question's subject: cite EVERY "
    "supplied record that bears on the answer, not only the single most direct one. A question "
    "about what happened during a run covers all of that run's records that show it — the steps "
    "and resumptions as much as the final effect — and omitting one understates what the "
    "records show. 'Nearby' means outside the question's subject, never inside it."
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
        ids_to_hashes: dict[str, str] | None = None,
        model: str = LIVE_MODEL,
        api_key: str | None = None,
    ) -> None:
        #: `None` means **the entry hash is the id** — the deployed shape, where records are the
        #: tenant's own and nobody authored a friendly name for them. The eval fixtures pass a
        #: mapping because their cases cite `rec-vault-002`, which is a property of the fixture
        #: and not of the platform.
        #:
        #: Without this branch a deployed estate answer offers every record as ``id: ?`` and
        #: resolves every citation to ``unresolvable:?`` — the provider would answer and the
        #: path would drop every claim, which reads as "the records do not support an answer".
        #: Found while wiring `served.py`, which is the first assembly to construct one.
        self._by_hash = ids_to_hashes is None
        ids_to_hashes = ids_to_hashes or {}
        self._ids = ids_to_hashes
        self._hashes_to_ids = {h: i for i, h in ids_to_hashes.items()}
        self._model = model
        #: See `LiveAnswerProvider.__init__` — brokered per task by a production caller, `None`
        #: in the eval lane.
        self._api_key = api_key

    def _id_for(self, entry_hash: str) -> str:
        return entry_hash if self._by_hash else self._hashes_to_ids.get(entry_hash, "?")

    def _hash_for(self, cited: str) -> str:
        if self._by_hash:
            return cited
        return self._ids.get(cited, f"unresolvable:{cited}")

    def answer(
        self, question: str, records: tuple[Any, ...], context: str = ""
    ) -> list[dict[str, Any]]:
        """Candidate claims from the records, retried on empty for `LiveAnswerProvider`'s reason.

        `context` is earlier conversation (035), for the same reason and with the same limit as
        the guidance path: it gives a follow-up its subject and is never evidence. References
        still resolve against records actually read.

        The same control, because the same sentence is at stake and it is arguably heavier here:
        told the platform found nothing in their own records, a person concludes something did
        not happen. Records that were read and not understood on one draw must not become
        "there is nothing there".
        """
        if not records:
            return []

        offered = "\n\n".join(
            f"--- id: {self._id_for(record.entry_hash)}\n"
            f"--- event: {record.event_type}\n"
            f"--- correlation: {record.correlation_id}\n"
            f"--- payload: {json.dumps(record.payload, sort_keys=True)}"
            for record in records
        )
        for remaining in range(ATTEMPTS_BEFORE_SILENCE - 1, -1, -1):
            claims = self._ask_once(question, offered, context)
            if claims or not remaining:
                return claims
        return []  # pragma: no cover — the loop always returns

    def _ask_once(self, question: str, offered: str, context: str = "") -> list[dict[str, Any]]:
        """One draw. Raises on a provider fault; returns `[]` when the model found nothing."""
        client, api_model = client_and_model(self._model, api_key=self._api_key)
        prologue = f"{context}\n\n" if context else ""
        response = client.messages.create(  # type: ignore[attr-defined]
            model=api_model,
            max_tokens=4096,
            system=_ESTATE_INSTRUCTION,
            messages=[
                {
                    "role": "user",
                    "content": (f"{prologue}Question: {question}\n\nAudit records:\n\n{offered}"),
                }
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
                {"entry_hash": self._hash_for(str(ref.get("id")))}
                for ref in item.get("references", [])
                if isinstance(ref, dict)
            ]
            claims.append({"statement": str(item.get("statement", "")), "references": references})
        return claims


def build_ask_provider(source: str, secret: str, *, model: str = LIVE_MODEL) -> Any:
    """The provider for one ask, built from material brokered for that ask (027).

    **This function exists so that no surface module ever names a vendor key.** A surface holds a
    `ModelCredential` and hands it straight here; `tests/unit/test_no_static_credentials.py`
    forbids the static-credential vocabulary in every surface, with no exemption, and that check
    is only worth keeping if it is structurally impossible to trip. Assembly calling
    `LiveAnswerProvider(model, api_key=...)` directly would have traded the gate for convenience.

    **Built per ask and dropped with it.** The provider holds the key for as long as it exists,
    and it exists for one question. A surface that built one at construction and reused it would
    hold a credential for the life of the process — the standing credential 027 exists to avoid,
    reintroduced one layer above the reader that refuses to cache.

    `source` selects which material the provider reads, matching `core.answering.routing.Route`.
    The estate provider takes no id mapping: deployed records are cited by their own entry hash.
    """
    if source == "estate":
        return LiveEstateProvider(model=model, api_key=secret)
    return LiveAnswerProvider(model, api_key=secret)


__all__ = [
    "LiveAnswerProvider",
    "LiveEstateProvider",
    "SECTIONS_OFFERED",
    "build_ask_provider",
]
