# SPDX-License-Identifier: Apache-2.0
"""The gates score what the product produced, not what somebody wrote down.

**This file is 024's deliverable.** `citation_accuracy` and `must_decline` were green before this
feature existed, over `recorded` strings described in the suite as *"what a previously-observed run
of this case produced"* — for cases no run had ever produced, because there was no answering path.

Point the same suites at the real path and they fail immediately on a platform that cannot answer.
That is the difference this makes.
"""

from __future__ import annotations

from typing import Any

from core.answering.corpus import Corpus, Document
from core.evals.scoring import AnsweringScorer, FixtureScorer, GovernedSubject
from core.evals.suites import EvalCase

PATH = "/validated-patterns/vault/vault-agent-approle"


def _corpus() -> Corpus:
    return Corpus(
        digest="d",
        documents={
            PATH: Document(
                path=PATH,
                url="https://developer.hashicorp.com" + PATH,
                digest="d",
                anchors=frozenset({"prerequisites"}),
            )
        },
    )


class _Grounded:
    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        return [
            {
                "statement": "Use AppRole for brownfield workloads.",
                "citations": [{"path": PATH, "anchor": "prerequisites"}],
            }
        ]


class _Confabulating:
    def answer(self, question: str, corpus: Corpus) -> list[dict[str, Any]]:
        return [
            {
                "statement": "Confident and unsupported.",
                "citations": [{"path": PATH, "anchor": "invented"}],
            }
        ]


def _subject() -> GovernedSubject:
    """The scorers take one and neither of these rows depends on it."""
    return GovernedSubject(
        agent_definition_id="guidance-agent",
        pack="terraform",
        tier=1,
        role="ask",
        cell="fixture/scripted@1",
    )


def _case(suite: str) -> EvalCase:
    return EvalCase(
        id="c1",
        suite=suite,
        prompt="How should brownfield applications authenticate?",
        expected="cited",
        recorded="an authored string nothing produced",
    )


def test_the_scorer_returns_what_the_path_produced_not_the_recording() -> None:
    """The whole point. `FixtureScorer` hands back the authored string; this does not."""
    case = _case("citation_accuracy")
    assert FixtureScorer().respond(None, case) == "an authored string nothing produced"  # type: ignore[arg-type]

    produced = AnsweringScorer(corpus=_corpus(), provider=_Grounded()).respond(_subject(), case)
    assert produced != case.recorded
    assert "Use AppRole" in produced
    assert "#prerequisites" in produced, "the citation must survive into what is scored"


def test_a_confabulating_model_scores_as_a_decline_not_as_an_answer() -> None:
    """`must_decline`'s subject, reached through the product rather than around it.

    The model produced a confident sentence; every citation under it was invented; the path
    declined. A suite scoring the authored recording could never have observed this.
    """
    produced = AnsweringScorer(corpus=_corpus(), provider=_Confabulating()).respond(
        _subject(), _case("must_decline")
    )
    assert produced.startswith("Declined:")
    assert "does not resolve" in produced


def test_the_scorer_needs_no_vendor_credential() -> None:
    """FR-016. A gate that needs a credential is a gate that stops running.

    Everything above ran against an injected provider. Nothing here reaches a vendor, which is what
    keeps the blocking lane blocking.
    """
    import inspect

    source = inspect.getsource(AnsweringScorer)
    assert "api_key" not in source
    assert "anthropic" not in source.lower()
