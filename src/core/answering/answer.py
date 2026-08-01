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

from core.answering.corpus import Corpus


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

    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        """Candidate claims, each with the citations it rests on."""
        ...


@dataclass(frozen=True)
class Citation:
    path: str
    anchor: str

    def url(self, corpus: Corpus) -> str:
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


ANSWERED = "answered"
DECLINED = "declined"


def answer_question(*, question: str, corpus: Corpus, provider: AnswerProvider) -> Answer:
    """Ask, keep only what the corpus supports, and decline if that is nothing."""
    try:
        candidates = provider.answer(question, corpus)
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
    return Answer(
        disposition=ANSWERED,
        corpus_digest=corpus.digest,
        claims=tuple(kept),
        dropped=tuple(dropped),
    )


__all__ = [
    "ANSWERED",
    "DECLINED",
    "Answer",
    "AnswerProvider",
    "Citation",
    "Claim",
    "ProviderUnavailable",
    "answer_question",
]
