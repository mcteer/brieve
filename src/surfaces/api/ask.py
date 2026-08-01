# SPDX-License-Identifier: Apache-2.0
"""The ask operation — an API operation rather than portal logic (ADR-0034).

**Transport-independent, so MCP reaches this rather than reimplementing it.** ADR-0033 asks for the
same verdict on every transport, and two implementations agreeing by inspection would make that a
measure of how carefully they were written.

**Holds no tool and no grant.** Never-acts is a property of what this path can reach, not of an
instruction given to a model — see `core.answering.answer`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from core.answering.answer import ANSWERED, ProviderUnavailable, answer_question
from core.answering.corpus import Corpus, CorpusUnavailable
from core.answering.record import record_ask
from core.audit.sink import AuditSink
from core.identity.types import AuthenticatedSubject
from surfaces.api.dependencies import AuditDep, SubjectDep


def ask_for(
    *,
    question: str,
    subject: AuthenticatedSubject,
    corpus: Corpus,
    provider: Any,
    audit: AuditSink,
    model: str,
) -> dict[str, Any]:
    """Answer or decline, and record that someone asked.

    A provider failure and a corpus failure both **raise**. Neither arrives shaped like a decline,
    because a reader cannot tell "the corpus does not say" from "we could not reach the model", and
    those send them to different places.
    """
    answer = answer_question(question=question, corpus=corpus, provider=provider)

    # Recorded before the answer is returned. An answer delivered while its record failed is the
    # state 022 spent a feature removing.
    record_ask(
        audit=audit,
        subject=subject,
        corpus_digest=answer.corpus_digest,
        model=model,
        disposition=answer.disposition,
    )

    if answer.disposition != ANSWERED:
        return {
            "disposition": answer.disposition,
            "declined_reason": answer.declined_reason,
            "corpus_digest": answer.corpus_digest,
        }
    return {
        "disposition": answer.disposition,
        "corpus_digest": answer.corpus_digest,
        "claims": [
            {
                "statement": claim.statement,
                "citations": [c.url(corpus) for c in claim.citations],
            }
            for claim in answer.claims
        ],
    }


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: No corpus and no model parameter. Which corpus is pinned and which model the binding names
    #: are not the caller's to choose — a parameter for either would be a request to widen scope.
    question: str


def build_router(*, provider: Any = None, model: str = "unconfigured") -> APIRouter:
    """The provider is a **parameter**, so a deployment can supply one and a test can share one.

    An earlier draft read it off the router with `getattr`, which meant nothing could ever set it:
    the operation was permanently 503 in every assembly, and the parity rows could only compare two
    surfaces failing. A collaborator that cannot be injected is a collaborator the surfaces cannot
    be shown to share — the exact asymmetry `surface_under_test` exists to prevent.
    """
    router = APIRouter(tags=["ask"])

    @router.post("/ask")
    def ask(body: AskRequest, subject: SubjectDep, audit: AuditDep) -> dict[str, Any]:
        """Answer from the pinned corpus, or decline. Never act.

        **The provider is resolved per deployment and may be absent.** A surface with no model
        configured fails here rather than answering from the corpus alone — FR-011a forbids a
        model-less path, because a second path no gate scores is how this feature's own gates
        reached the state it was written to fix.
        """
        from core.answering.corpus import load_corpus

        try:
            corpus = load_corpus()
        except CorpusUnavailable as unavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unavailable)
            ) from unavailable

        if provider is None:
            # RECORDED ANYWAY. Someone asked; the platform could not attempt it. 022 established
            # that a refusal records — a boundary a caller can probe without trace is the thing
            # that prevents — and repeated asks against a surface with no model is exactly the
            # shape a trail should show rather than swallow.
            record_ask(
                audit=audit,
                subject=subject,
                corpus_digest=corpus.digest,
                model="unconfigured",
                disposition="provider_unavailable",
            )
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "no model is configured for `ask`; the corpus alone is not an answer",
            )
        try:
            return ask_for(
                question=body.question,
                subject=subject,
                corpus=corpus,
                provider=provider,
                audit=audit,
                model=model,
            )
        except ProviderUnavailable as unreachable:
            # NOT a decline. A reader cannot tell "the corpus does not say" from "we could not
            # reach the model", and those send them to different people.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, str(unreachable)
            ) from unreachable

    return router


__all__ = ["AskRequest", "CorpusUnavailable", "ProviderUnavailable", "ask_for", "build_router"]
