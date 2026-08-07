# SPDX-License-Identifier: Apache-2.0
"""A question becomes a cited answer, or a decline. It never becomes an action.

**What this module holds is the governance.** A corpus and a provider. **No tool registry and no
authority grant** — so ADR-0039's rule that *ask answers, it never acts* is satisfied by what is
absent rather than by an instruction a model may ignore. Granting the ability to act later means
*adding* a dependency here, which is visible in review. 021's report compiler uses the same shape:
it holds no query and no credential, so it cannot widen scope.

**Declining is a first-class outcome.** A claim whose citation does not resolve does not ship, and
an answer with no supported claims is a decline. That is not politeness — an unresolvable citation
reads as evidence, and a reader who follows one and finds nothing has been told something false
about what this platform knows.

**A provider failure is not an answer.** It raises. A reader cannot tell "the corpus does not say"
from "we could not reach the model", and one sends them to the corpus while the other sends them to
an operator, so they must not share a shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from core.answering.relevance import RelevanceJudge, RelevanceRefused


class CitableCorpus(Protocol):
    """What this module actually needs from a corpus — three members, structurally (045).

    `Corpus` satisfies it, and so does the composition of the pinned corpus with a customer's
    endorsed material. The Protocol is stated here rather than imported from the endorsed
    package because the dependency must run the other way: the answering logic declares its
    contract, and a second reader satisfies it. That is what makes research R1's "a second
    corpus, never a modified first one" true of the types as well as of the code.
    """

    @property
    def digest(self) -> str: ...

    def resolves(self, path: str, anchor: str) -> bool: ...

    def url_for(self, path: str, anchor: str) -> str: ...


class ProviderUnavailable(Exception):
    """The model could not be reached, or answered unusably.

    Distinct from a decline by type, not by a field — see the module docstring.
    """


class AnswerProvider(Protocol):
    """The seam. A fixture replays; a live provider asks a vendor.

    **Injected, never constructed here.** The blocking eval lane drives this very path with a
    fixture, which is the only arrangement under which the gates score what the product produced
    rather than a recording someone authored. A path that could only reach a vendor would force
    those gates back onto authored material.
    """

    def answer(self, question: str, corpus: Any, context: str = "") -> list[dict[str, Any]]:
        """Candidate claims, each with the citations it rests on.

        **`corpus` is `Any` rather than `CitableCorpus`, and that is about variance.** A
        Protocol's parameter type is a *requirement on implementers*, and every existing
        provider double annotates `Corpus` — narrower, so declaring the wider type here would
        make each of them stop satisfying this Protocol. That would mean editing conformance
        rows 043 wrote, to accommodate an annotation, with no behaviour changing anywhere; the
        045 diff row exists precisely to stop that happening quietly. Nothing is lost: a
        provider that understood only the pinned corpus is not a thing that exists, and what
        gets handed here is decided by the surface.


        `context` is earlier conversation, supplied so a follow-up has a subject (035). It is
        **not material**: nothing in it may be cited, and citation resolution below is
        unchanged by its presence. Optional and defaulted so a provider that predates
        conversations is still a provider — `answer_question` passes it only when there is
        some, so every existing two-argument implementation keeps working untouched.
        """
        ...


@dataclass(frozen=True)
class Citation:
    path: str
    anchor: str

    def url(self, corpus: CitableCorpus) -> str:
        return corpus.url_for(self.path, self.anchor)


@dataclass(frozen=True)
class Claim:
    statement: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class Answer:
    """Answered or declined. **Never `failed`** — a provider failure raises instead."""

    disposition: str
    corpus_digest: str
    claims: tuple[Claim, ...] = ()
    declined_reason: str = ""
    dropped: tuple[str, ...] = field(default_factory=tuple)
    #: How old the material behind this answer is (033), composed by the surface.
    #:
    #: **Carried on every disposition, like the estate answer's `window_note`.** A decline
    #: rests on the same corpus an answer would have, and a reader deciding whether to go
    #: looking elsewhere is exactly who needs to know the ground's age.
    #:
    #: Empty only when nobody composed one — `answer_question` does not, because the core has
    #: no clock and should not grow one. The surfaces do, and a conformance row asserts they
    #: did rather than trusting this default.
    ground_note: str = ""
    #: Statements the RELEVANCE gate dropped (043) — distinct from `dropped`, which keeps
    #: meaning "a citation did not resolve". Two grounds, two fields: they send a reader to
    #: different places, and one bucket would make them indistinguishable in the record.
    irrelevant: tuple[str, ...] = field(default_factory=tuple)
    #: That a MODEL judged relevance, carried on answers and declines alike (FR-007).
    #:
    #: Never phrased as a platform fact. Principle IX distinguishes a model gate from a human
    #: approval, and a note reading "this answer is relevant" would assert as the platform what
    #: a model decided.
    relevance_note: str = ""


ANSWERED = "answered"
DECLINED = "declined"

#: The third decline ground (043). Distinguishable from "citations did not resolve" because the
#: two send a reader to different places: one to what the model invented, one to what the corpus
#: does not cover.
NOT_COVERED = "the corpus does not cover what was asked"

#: Carried on every answer and decline the gate touched. Phrased as a model's judgement rather
#: than the platform's finding — Principle IX keeps those distinct.
_MODEL_JUDGED = "relevance to the question was judged by a model, not by the platform"

#: What an answer says when an administrator has switched the gate off (044, FR-011).
#:
#: **Disclosed, never suppressed** — 033's rule, and the reason the alternatives were
#: rejected: answering silently reintroduces gap 0g by configuration, and declining outright
#: would mean an administrator who turns off a check has turned off answering. This is the
#: third option, and it is the one this platform's precedent points at.
#:
#: It names WHO decided. "Relevance was not checked" alone reads as a platform failure; an
#: administrator's decision is a fact about the estate, and the reader should be able to go
#: and ask them.
RELEVANCE_DISABLED = (
    "relevance was NOT checked: an administrator has disabled the relevance gate, so these "
    "claims are grounded in the corpus but nothing has confirmed they answer what was asked"
)


def answer_question(
    *,
    question: str,
    corpus: CitableCorpus,
    provider: AnswerProvider,
    context: str = "",
    relevance: RelevanceJudge | None = None,
) -> Answer:
    """Ask, keep only what the corpus supports, and decline if that is nothing.

    **`context` changes what is ASKED, never what is KEPT.** Everything below this call is
    untouched by it: a claim ships only when every citation resolves against the pin, and
    conversation history has no citations in it to resolve (they are stripped upstream in
    `core.answering.context`). So a follow-up gets its subject and the corpus keeps its
    monopoly on what is true.

    Passed to the provider only when there is some, which is what keeps every two-argument
    provider — including the fixtures the blocking eval lane drives this path with — working
    exactly as before.
    """
    try:
        candidates = (
            provider.answer(question, corpus, context)
            if context
            else provider.answer(question, corpus)
        )
    except ProviderUnavailable:
        raise
    except Exception as exc:  # noqa: BLE001 — any provider fault is a provider fault
        raise ProviderUnavailable(f"the model could not be reached: {type(exc).__name__}") from exc

    kept: list[Claim] = []
    dropped: list[str] = []
    for candidate in candidates:
        statement = str(candidate.get("statement", "")).strip()
        cites = tuple(
            Citation(path=str(c["path"]), anchor=str(c["anchor"]))
            for c in candidate.get("citations", [])
            if isinstance(c, dict) and "path" in c and "anchor" in c
        )
        # A claim ships only if EVERY citation resolves. One unresolvable citation among several
        # is still a claim resting partly on something that does not exist.
        if not statement or not cites or not all(corpus.resolves(c.path, c.anchor) for c in cites):
            if statement:
                dropped.append(statement)
            continue
        kept.append(Claim(statement=statement, citations=cites))

    if not kept:
        return Answer(
            disposition=DECLINED,
            corpus_digest=corpus.digest,
            declined_reason=(
                "the pinned corpus does not support an answer to this question"
                if not dropped
                else "every candidate claim rested on a citation that does not resolve"
            ),
            dropped=tuple(dropped),
        )

    # THE RELEVANCE GATE (043, ROADMAP gap 0g). Everything above asks whether a claim's
    # citations EXIST; this asks whether what survived answers the question that was asked.
    # Until 035 widened the pin the two were close enough to pass for each other — after it, a
    # question about this platform's audit retention could be answered from another product's
    # retention pages, every citation resolving and every claim true.
    #
    # **Only when something survived** (FR-018): an ask already declining pays nothing.
    #
    # **Optional here, mandatory at the caller.** Requiring it would force edits to the recorded
    # eval scorers whose suites this feature promises not to touch — so the production surface
    # always supplies one and a row drives the SURFACE to prove it, rather than trusting a
    # default. A gate nothing calls is the defect 041 spent a feature closing.
    if relevance is not None:
        try:
            verdict = relevance.assess(question, [claim.statement for claim in kept])
        except RelevanceRefused as refusal:
            # Fail closed. A gate that could not run must never read as one that passed.
            return Answer(
                disposition=DECLINED,
                corpus_digest=corpus.digest,
                declined_reason=f"relevance could not be established: {refusal.reason_code}",
                dropped=tuple(dropped),
                relevance_note=_MODEL_JUDGED,
            )

        relevant = [claim for index, claim in enumerate(kept) if index in verdict.relevant]
        irrelevant = [
            claim.statement for index, claim in enumerate(kept) if index not in verdict.relevant
        ]
        if not relevant:
            return Answer(
                disposition=DECLINED,
                corpus_digest=corpus.digest,
                declined_reason=NOT_COVERED,
                dropped=tuple(dropped),
                irrelevant=tuple(irrelevant),
                relevance_note=_MODEL_JUDGED,
            )
        return Answer(
            disposition=ANSWERED,
            corpus_digest=corpus.digest,
            claims=tuple(relevant),
            dropped=tuple(dropped),
            irrelevant=tuple(irrelevant),
            relevance_note=_MODEL_JUDGED,
        )

    return Answer(
        disposition=ANSWERED,
        corpus_digest=corpus.digest,
        claims=tuple(kept),
        dropped=tuple(dropped),
    )


class RecordedProvider:
    """Replays a case's recorded model output **into the product path**.

    **This is what moves a recording from the scorer to the provider**, and it is the whole of
    024's Phase 5. `FixtureScorer` returned `case.recorded` as the answer, so nothing the product
    does — resolving citations, dropping unsupported claims, deciding to decline — ever ran. Here
    the recording is what the *model* said, and the path then does its work over it.

    So the suite still scores deterministically with no vendor, and what it scores is the product's
    output rather than the fixture's.
    """

    def __init__(self, recorded: str) -> None:
        self._recorded = recorded

    def answer(
        self, question: str, corpus: CitableCorpus, context: str = ""
    ) -> list[dict[str, Any]]:
        # `context` is accepted and IGNORED, deliberately. A recording is a recording: replaying
        # it under different conversation history would produce the same claims while implying
        # the history mattered, and the eval lane's determinism rests on it not mattering.
        import re as _re

        urls = _re.findall(
            r"https://developer\.hashicorp\.com(/[\w\-/]+)#([\w\-]+)", self._recorded
        )
        if not urls:
            # A model that cited nothing. The path will decline, which is correct and is what
            # `must_decline` exists to observe.
            return [{"statement": self._recorded.strip(), "citations": []}]
        return [
            {
                "statement": self._recorded.strip(),
                "citations": [{"path": path, "anchor": anchor} for path, anchor in urls],
            }
        ]


__all__ = [
    "ANSWERED",
    "NOT_COVERED",
    "RELEVANCE_DISABLED",
    "RecordedProvider",
    "DECLINED",
    "Answer",
    "AnswerProvider",
    "Citation",
    "Claim",
    "ProviderUnavailable",
    "answer_question",
]
