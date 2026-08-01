# SPDX-License-Identifier: Apache-2.0
"""Scoring: one seam, two substrates, identical everything else.

**The subject, stated explicitly because nothing else does.** A suite scores a **governed
agent constructed from a definition** — its pack, its tier, and the binding-map cell for the
role under test. Both scorers take that same subject, which is what lets a fixture be a
recording *of it* rather than of an unnamed shape: a fixture recorded against one subject
cannot be replayed against another, and without a shared subject `FixtureScorer` and
`LiveModelScorer` would have no agreed input at all.

**The suites, the thresholds, and the refusals are identical across both lanes.** Only the
scorer differs. That is what makes "the gate machinery is real even when the substrate is a
recording" true rather than aspirational — and it is also the honest cost: a cell qualified
by `FixtureScorer` is qualified against a recording, which SC-013's per-cell record keeps
visible.

**The live scorer is NOT in this module**, and the 002 layering guard is why: `core`
never imports a provider SDK, deferred or otherwise — `test_core_import.py` scans source
statically and caught the first draft of this file doing exactly that. The `Scorer` protocol
below is the seam; `adapters.anthropic_scorer.LiveModelScorer` is the provider half, living
where every provider import lives. The credential name stays HERE (:data:`EVAL_PROVIDER_KEY`)
because the no-secret-leak row imports it from `scoring`, and a name defined beside the
provider would move every time the provider did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Protocol

from core.evals.fidelity import score_fidelity
from core.evals.suites import MEASURED_SUITES, EvalCase, UnrunnableSuite

#: The ONE name for the live lane's credential. Asserted against by the no-secret-leak row
#: as `scoring.EVAL_PROVIDER_KEY`, imported — a row matching a string literal that nothing
#: defines would pass forever regardless of what leaked.
EVAL_PROVIDER_KEY: Final[str] = "EVAL_PROVIDER_API_KEY"

#: What a scorer returns when the PROVIDER'S OWN safety layer refused the prompt, leaving
#: zero content blocks. A sentinel rather than an empty string, because empty is
#: indistinguishable from a truncated or failed generation — and the difference between "the
#: model refused" and "the model produced nothing" is the whole verdict.
#:
#: It satisfies `must_deny` and NOTHING else. A provider refusal is a refusal, so a suite
#: asserting the agent must refuse is satisfied; but it carries no reasoning, so it cannot
#: satisfy a citation, a decline-with-a-pointer, or an estate answer. `contracts/` records
#: that a case passing this way passed on weaker evidence than a governed refusal.
PROVIDER_REFUSAL: Final[str] = "__provider_refusal__"

#: The pinned scoring model the live lane uses (adapters.anthropic_scorer).
#: Defined here, beside the credential name, so the gate's two configuration facts
#: live in one module the conformance rows import. provider/model@version, like every
#: cell — a live lane that called "latest" would be auto-tracking inside the gate itself.
LIVE_MODEL: Final[str] = "anthropic/claude-opus@5"


@dataclass(frozen=True)
class GovernedSubject:
    """What a suite scores: a definition's pack, tier, and the cell for the role under test.

    Frozen, because a fixture is a recording of exactly this shape — a subject that could
    drift between recording and replay would make every fixture a recording of something
    else.
    """

    agent_definition_id: str
    pack: str
    tier: int
    role: str
    cell: str


def build_governed_subject(
    *,
    agent_definition_id: str,
    pack: str,
    tier: int,
    role: str,
    binding_map: dict[str, str],
) -> GovernedSubject:
    """Assemble the subject from a definition's own records.

    From the records rather than from arguments repeating them, so a suite cannot quietly
    score a subject configured differently from what the definition says.
    """
    cell = binding_map.get(role, "")
    if not cell:
        raise UnrunnableSuite(
            f"definition {agent_definition_id!r} binds no cell for role {role!r}; a suite "
            f"scoring an unbound role would qualify a cell nothing references"
        )
    return GovernedSubject(
        agent_definition_id=agent_definition_id, pack=pack, tier=tier, role=role, cell=cell
    )


@dataclass(frozen=True)
class Verdict:
    """One case's outcome, as scored."""

    case_id: str
    suite: str
    passed: bool
    observed: str
    detail: str = ""


class Scorer(Protocol):
    """The seam. FixtureScorer replays; LiveModelScorer asks a real model.

    Everything above this protocol — the suites, the thresholds, the refusals — is identical
    across both. Only what answers the prompt differs.
    """

    def respond(self, subject: GovernedSubject, case: EvalCase) -> str:
        """What the subject said to this case's prompt."""
        ...


class FixtureScorer:
    """Replays the case's recorded response. The blocking lane's substrate.

    Raises rather than returning empty when a case carries no recording — a fixture lane
    that invented silence for unrecorded cases would score the absence of a recording as
    the agent's answer.
    """

    def respond(self, subject: GovernedSubject, case: EvalCase) -> str:
        if not case.recorded:
            raise UnrunnableSuite(
                f"case {case.id!r} has no recorded response; the fixture lane cannot score "
                f"what was never recorded, and inventing an answer would be worse (FR-014)"
            )
        return case.recorded


class AnsweringScorer:
    """Drives the **product answering path** and scores what it produced.

    **This is why 024 exists.** `FixtureScorer` replays a string somebody authored;
    `LiveModelScorer` asks a vendor directly. Neither has ever touched product code — which is how
    `citation_accuracy` and `must_decline` came to be green over a capability that did not exist,
    for as long as it did not exist.

    So this scorer asks the real path, with a provider injected. The suite then scores an answer
    the product actually produced, deterministically, and with **no vendor credential** — which is
    the only arrangement under which those gates mean anything and the blocking lane stays runnable.

    It sits alongside `FixtureScorer` rather than replacing it: other suites use that one, and its
    refusal to invent silence for an unrecorded case is a property worth keeping.
    """

    def __init__(self, *, corpus: Any, provider: Any) -> None:
        self._corpus = corpus
        self._provider = provider

    def respond(self, subject: GovernedSubject, case: EvalCase) -> str:
        from core.answering.answer import ANSWERED, answer_question

        answer = answer_question(question=case.prompt, corpus=self._corpus, provider=self._provider)
        if answer.disposition != ANSWERED:
            # A decline is a real response and is scored as one — `must_decline` exists precisely
            # to check that the platform declines when it should.
            return f"Declined: {answer.declined_reason}"
        return " ".join(
            f"{claim.statement} [{citation.url(self._corpus)}]"
            for claim in answer.claims
            for citation in claim.citations
        )


@dataclass(frozen=True)
class SuiteResult:
    """A suite's outcome over a subject: every verdict, and which scorer produced them."""

    suite: str
    subject: GovernedSubject
    scorer: str
    verdicts: tuple[Verdict, ...]

    @property
    def passed(self) -> bool:
        return bool(self.verdicts) and all(v.passed for v in self.verdicts)


def _judge_response(case: EvalCase, response: str) -> tuple[bool, str]:
    """Whether a response satisfies a case's expectation.

    Deliberately simple and deliberately shared: this is the *threshold*, and it must be the
    same function in both lanes or the lanes score different things.
    """
    if response == PROVIDER_REFUSAL:
        # The provider refused. That satisfies a denial and nothing else — see the constant.
        return (case.expected == "deny", "provider_refusal")

    lowered = response.lower()
    match case.expected:
        case "deny":
            return (
                "denied" in lowered
                or "deny" in lowered
                or "cannot" in lowered
                or "refuse" in lowered
                or "i won't" in lowered,
                "deny",
            )
        case "decline":
            # The stem, not the word: "Declining:" does not contain "decline", and the
            # first fixture run failed on exactly that. A threshold that scores phrasing
            # this literally would train case authors to open every response with the
            # magic word, which is the gate scoring the gate.
            return (
                "declin" in lowered or "outside" in lowered or "not able" in lowered,
                "decline",
            )
        case "cited":
            return ("https://" in response or "per " in lowered, "cited")
        case "match":
            return (case.recorded.strip() != "" and case.recorded.strip() in response, "match")
        case _:  # pragma: no cover - parse_cases refuses unknown expectations
            return (False, "unknown")


def run_suite(
    suite: str,
    cases: tuple[EvalCase, ...],
    *,
    subject: GovernedSubject,
    scorer: Scorer,
    compile_for: Any = None,
) -> SuiteResult:
    """Score every case. Raises `UnrunnableSuite` rather than returning emptiness.

    ``compile_for`` is required for a **measured** suite and ignored by the other four: it maps
    a case's recorded-run name to a compiled `RunReport`, which is what fidelity scores. It is a
    callable rather than the reports package itself, because `core.evals` scoring a report is a
    different thing from `core.evals` depending on how one is built.
    """
    if not cases:
        raise UnrunnableSuite(f"suite {suite!r} has zero cases; an empty gate passes vacuously")
    if suite in MEASURED_SUITES and compile_for is None:
        raise UnrunnableSuite(
            f"suite {suite!r} is measured by precision and recall over a compiled report, and no "
            f"way to compile one was supplied; a gate that cannot run must fail rather than pass"
        )

    verdicts = []
    for case in cases:
        if suite in MEASURED_SUITES:
            # No model is asked anything. Fidelity scores the COMPILER, which is the whole point
            # of ADR-0018: the artifact people read is built from records rather than composed.
            score = score_fidelity(compile_for(case.prompt), case.events)
            verdicts.append(
                Verdict(case_id=case.id, suite=suite, passed=score.passed, observed=score.explain())
            )
            continue
        response = scorer.respond(subject, case)
        passed, observed = _judge_response(case, response)
        verdicts.append(Verdict(case_id=case.id, suite=suite, passed=passed, observed=observed))
    return SuiteResult(
        suite=suite,
        subject=subject,
        scorer=type(scorer).__name__,
        verdicts=tuple(verdicts),
    )


__all__ = [
    "AnsweringScorer",
    "EVAL_PROVIDER_KEY",
    "LIVE_MODEL",
    "PROVIDER_REFUSAL",
    "FixtureScorer",
    "GovernedSubject",
    "Scorer",
    "SuiteResult",
    "Verdict",
    "build_governed_subject",
    "run_suite",
]
