# SPDX-License-Identifier: Apache-2.0
"""What an analyzer concluded, and what it may never conclude (037, FR-008/FR-010).

**Three values, because an analysis that could not complete is not a clean one.** Two would
force an outage to be recorded as an opinion, and a stage that failed to run would enter the
evidence package as reassurance.

**No value here approves anything.** ADR-0043 and Principle IX: a model verdict may gate a
step and never satisfies an approval policy assigns to a person. That is structural rather
than promised — there is no `approved` member, so the type itself cannot express one, and the
human's acceptance lives in a different record entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Verdict(StrEnum):
    """What an analysis concluded. Note what is absent: nothing that means "promote"."""

    #: The analyzer found nothing. **Not the same as "this is safe"** — see the evidence
    #: package's limits statement, which says so where a reader will see it.
    CLEAN = "clean"
    #: Something was found. Short-circuits to the human with findings attached (FR-010).
    FLAGGED = "flagged"
    #: The analysis could not complete. Blocks, exactly as a flag does — a stage that did not
    #: run has said nothing, and "nothing" must not read as "nothing wrong" (FR-024).
    INCONCLUSIVE = "inconclusive"

    @property
    def blocks(self) -> bool:
        """Whether this verdict stops the candidate reaching later stages.

        Only `CLEAN` proceeds. Both other values block, and they are kept distinct because
        *found something* and *could not look* send a reviewer to different places.
        """
        return self is not Verdict.CLEAN


@dataclass(frozen=True)
class AnalysisResult:
    """An analyzer's structured output — the only thing it is permitted to emit.

    **Findings are CODES, never quoted candidate text.** The subject of an analysis is
    hostile-by-assumption instruction content; a result that quoted it would carry the payload
    into the trail, the proposal, and the reviewer's screen — turning the report into a
    delivery mechanism for the thing it was written to describe.
    """

    candidate_digest: str
    verdict: Verdict
    #: Stable identifiers like `redirection_attempt`, never prose from the candidate.
    findings: tuple[str, ...] = ()
    #: Which qualified matrix cell produced this, so a later re-qualification can identify
    #: what it invalidates.
    analyzer_cell: str = ""

    def __post_init__(self) -> None:
        if self.verdict is Verdict.FLAGGED and not self.findings:
            raise ValueError(
                "a flagged verdict must name what it found; a flag with no finding sends a "
                "reviewer looking for something nobody recorded"
            )


#: The delimiter the candidate's text is wrapped in before it reaches the analyzer. Candidate
#: content enters as DATA, never as instruction (FR-008) — and the containment does not rest
#: on this marker: the analyzer's ceiling contains nothing to be redirected TO, so a
#: successful redirection has no reachable effect (FR-009). The delimiter makes the boundary
#: legible; the ceiling makes it hold.
CANDIDATE_OPEN = "<<<INTAKE-CANDIDATE-BEGIN>>>"
CANDIDATE_CLOSE = "<<<INTAKE-CANDIDATE-END>>>"


def as_data(delta: str) -> str:
    """Wrap a candidate delta for delivery to the analyzer.

    Any occurrence of the delimiters inside the candidate is neutralised, because a candidate
    that could close its own envelope could append text that reads as instruction — the
    oldest trick against exactly this shape of boundary.
    """
    neutralised = delta.replace(CANDIDATE_OPEN, "<<<begin>>>").replace(CANDIDATE_CLOSE, "<<<end>>>")
    return f"{CANDIDATE_OPEN}\n{neutralised}\n{CANDIDATE_CLOSE}"


__all__ = [
    "CANDIDATE_CLOSE",
    "CANDIDATE_OPEN",
    "AnalysisResult",
    "Verdict",
    "as_data",
]
