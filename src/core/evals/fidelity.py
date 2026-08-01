# SPDX-License-Identifier: Apache-2.0
"""Scoring a compiled report against the material events a faithful one must mention.

**Precision and recall, not a boolean**, and the distinction is the whole reason this module is
separate from `scoring.py`. The other four suites ask *did the model say the right kind of thing*
and answer with one verb. This one asks two questions that fail in opposite directions:

* **Recall** — did the report mention everything that mattered? A report that omits a denial is
  the ADR-0018 failure: it terminates the investigation that would have found the problem.
* **Precision** — did it mention anything that did not happen? A report that invents a success
  is the other half, and a single number covering both would let one hide the other.

A boolean "faithful / not faithful" collapses them, and ADR-0018 asks for both by name.

**The corpus is what makes or breaks this gate, and the ADR says so itself**: labelled material
events are "the thing most likely to be skipped under schedule pressure, which would leave the
decision nominally in force and practically unenforced". A corpus of three easy runs passes
exactly as green as one of twenty hard ones — which is why `parse_cases` refuses a fidelity case
that labels no events, and why the per-pack floor in `pack.toml` is set from runs containing the
shapes that are hard.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

#: How much of the labelled set a report must mention, and how little it may invent.
#:
#: **Recall is 1.0 and not negotiable**: every material event must appear. A report allowed to
#: miss one in ten would be allowed to miss the denial, and "usually mentions denials" is not a
#: property anyone can rely on when reading a specific report.
#:
#: Precision is 1.0 for the same reason in the other direction — an invented claim is a
#: fabrication, and there is no acceptable rate of those in an artifact cited as evidence.
MINIMUM_RECALL: Final[float] = 1.0
MINIMUM_PRECISION: Final[float] = 1.0


@dataclass(frozen=True)
class FidelityScore:
    """What a report got right, missed, and invented.

    Both directions are carried separately rather than reduced, because the remediation differs:
    a missing event means the compiler does not understand a record, and an invented one means it
    is asserting something no record supports.
    """

    matched: tuple[str, ...]
    missing: tuple[str, ...]
    invented: tuple[str, ...]

    @property
    def recall(self) -> float:
        expected = len(self.matched) + len(self.missing)
        return 1.0 if expected == 0 else len(self.matched) / expected

    @property
    def precision(self) -> float:
        claimed = len(self.matched) + len(self.invented)
        return 1.0 if claimed == 0 else len(self.matched) / claimed

    @property
    def passed(self) -> bool:
        return self.recall >= MINIMUM_RECALL and self.precision >= MINIMUM_PRECISION

    def explain(self) -> str:
        """Why it failed, in the terms a fix is made in."""
        parts = [f"recall={self.recall:.2f} precision={self.precision:.2f}"]
        if self.missing:
            parts.append(f"missing {sorted(self.missing)} — the report did not mention these")
        if self.invented:
            parts.append(f"invented {sorted(self.invented)} — no record supports these")
        return "; ".join(parts)


def _mentions(report: Any) -> set[str]:
    """The material events a report actually asserts, as comparable keys.

    A claim's *subject* is the key: the tool a step ran, the hook that refused, `authority`. That
    is what a labelled event names, and matching on it rather than on prose keeps the corpus from
    scoring the compiler's wording — which is a template detail, not a governance property.
    """
    return {claim.subject for claim in report.claims if claim.subject}


def score_fidelity(report: Any, expected: Sequence[str]) -> FidelityScore:
    """Compare a compiled report against the material events labelled for its run.

    ``expected`` is the corpus's labelling — what a faithful report of this run must mention.
    Everything the report mentions beyond it is `invented`, which is deliberately strict: the
    corpus author decides what matters, and a compiler adding claims nobody labelled is
    surfacing something the corpus does not describe, which is worth a red row either way.
    """
    mentioned = _mentions(report)
    wanted = set(expected)
    return FidelityScore(
        matched=tuple(sorted(mentioned & wanted)),
        missing=tuple(sorted(wanted - mentioned)),
        invented=tuple(sorted(mentioned - wanted)),
    )


__all__ = ["MINIMUM_PRECISION", "MINIMUM_RECALL", "FidelityScore", "score_fidelity"]
