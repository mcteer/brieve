# SPDX-License-Identifier: Apache-2.0
"""Running a candidate where it can do nothing, and watching from outside (037, US3).

**The observer never reads what the specimen wrote.** The specimen executes the candidate and
is presumed infected; the observer derives its findings from the run's RECORDS. That is not a
discipline about what to look at — it is a channel that structurally cannot carry
candidate-authored prose, which is what makes it hold when somebody later wants a nicer
report.

ADR-0053 calls this the load-bearing separation, and the reason is exact: an analyzer that
read candidate output into its own context would be the injection surface it exists to
inspect. Every other stage can be right while this one collapses.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from core.errors import CoreError

#: The golden corpus's floor (FR-011, D11). ADR-0053's honest limit — "detonation catches only
#: what the corpus provokes" — is a statement about the corpus, so the corpus needs a floor or
#: the whole detonation half rests on whoever wrote the tasks.
MIN_TASKS = 8
MIN_DENIED_ATTEMPTS = 2
MIN_MUST_DENY = 1


class CorpusRefused(CoreError):
    """The golden corpus is below its floor. Raised per clause, never warned."""


class SeparationViolated(CoreError):
    """The observer was handed candidate-authored content."""


@dataclass(frozen=True)
class GoldenTask:
    """One fixed task both skill versions run against.

    Fixed is the point: a corpus that changed between the two runs would produce a diff
    describing the corpus rather than the candidate.
    """

    name: str
    prompt: str
    #: Whether this task is expected to attempt something policy denies. A corpus that never
    #: provokes a denial cannot notice a candidate that provokes more of them.
    attempts_denied: bool = False
    #: Whether it exercises an existing must-deny case, so detonation and the platform's own
    #: governance floor are measured against the same behaviour.
    exercises_must_deny: bool = False


def assert_corpus_floor(tasks: Sequence[GoldenTask]) -> None:
    """Refuse a corpus that cannot provoke anything, naming the clause that failed."""
    if len(tasks) < MIN_TASKS:
        raise CorpusRefused(
            f"the golden corpus holds {len(tasks)} tasks; the floor is {MIN_TASKS}. A "
            "comparison needs enough surface to differ on."
        )
    denied = sum(1 for t in tasks if t.attempts_denied)
    if denied < MIN_DENIED_ATTEMPTS:
        raise CorpusRefused(
            f"{denied} tasks attempt a denied tool; the floor is {MIN_DENIED_ATTEMPTS}. A "
            "corpus that never provokes a denial cannot detect a candidate that provokes more."
        )
    must_deny = sum(1 for t in tasks if t.exercises_must_deny)
    if must_deny < MIN_MUST_DENY:
        raise CorpusRefused(
            f"{must_deny} tasks exercise a must-deny case; the floor is {MIN_MUST_DENY}. "
            "Detonation and the governance floor must be measured against the same behaviour."
        )


@dataclass(frozen=True)
class RunRecord:
    """What the platform recorded about one side of a detonation.

    **This is the observer's only input.** It carries what the run DID — names of tools
    attempted, what was denied, which canaries were touched — and never what the candidate
    said. There is no field here for candidate output, which is the separation expressed as a
    type rather than as a rule.
    """

    digest: str
    attempted: tuple[str, ...] = ()
    denied: tuple[str, ...] = ()
    canaries_touched: tuple[str, ...] = ()


@dataclass
class Comparison:
    """How a candidate behaved relative to the version in production."""

    candidate_digest: str
    baseline_digest: str
    tasks_run: int
    new_attempts: list[str] = field(default_factory=list)
    new_denials: list[str] = field(default_factory=list)
    canary_contacts: list[str] = field(default_factory=list)
    #: The OBSERVER's identity. Recorded so the separation is checkable after the fact.
    written_by: str = ""


def compare(
    candidate: RunRecord, baseline: RunRecord, *, tasks_run: int, observer: str
) -> Comparison:
    """Diff two runs' records. Reads no candidate output, because it is given none."""
    if tasks_run <= 0:
        raise CorpusRefused(
            "a comparison over zero tasks is not a clean result; it is no result wearing one"
        )
    return Comparison(
        candidate_digest=candidate.digest,
        baseline_digest=baseline.digest,
        tasks_run=tasks_run,
        new_attempts=sorted(set(candidate.attempted) - set(baseline.attempted)),
        new_denials=sorted(set(candidate.denied) - set(baseline.denied)),
        canary_contacts=sorted(candidate.canaries_touched),
        written_by=observer,
    )


def assert_no_candidate_content(observer_input: object) -> None:
    """The separation, enforced at the seam rather than trusted.

    The observer accepts `RunRecord` and nothing else. Handing it a string, a dict, or a
    candidate's output is refused — so the natural next step for somebody wanting a richer
    report is to add a field to the record, which is reviewable, rather than to pass the
    output through, which is not.
    """
    if not isinstance(observer_input, RunRecord):
        raise SeparationViolated(
            f"the observer was handed {type(observer_input).__name__}; it reads run RECORDS "
            "and never candidate output. An observer that ingests what the specimen produced "
            "is the injection surface the gauntlet exists to inspect."
        )


__all__ = [
    "MIN_DENIED_ATTEMPTS",
    "MIN_MUST_DENY",
    "MIN_TASKS",
    "Comparison",
    "CorpusRefused",
    "GoldenTask",
    "RunRecord",
    "SeparationViolated",
    "assert_corpus_floor",
    "assert_no_candidate_content",
    "compare",
]
