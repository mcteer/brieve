# SPDX-License-Identifier: Apache-2.0
"""The evidence package — the feature's actual product (037, FR-004a/FR-027/FR-027a).

**A detection proposal grows into this; it is not assembled once at the end.** US1 emits a
proposal carrying only what detection produced, and later stages fill it in. That is why
`stages_run` exists: an artifact whose analyzer and detonation sections are simply *absent*
reads as clean, and **"no analysis has run" is a materially different claim from "analysis
found nothing."**

That distinction is the whole reason this module is careful. FR-027's reassurance failure —
a reviewer concluding a candidate is safe because nothing in the package said otherwise —
arrives most easily through the artifact's SHAPE rather than through its wording. An omitted
section and a section reading "not run" are identical to a grep and opposite to a reader, so
absence is rendered explicitly wherever presence would appear.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Stage(StrEnum):
    """The stages a package can carry results from, in the order they run."""

    DETECTION = "detection"
    ANALYSIS = "analysis"
    DETONATION = "detonation"


@dataclass
class EvidencePackage:
    """What the reviewer is handed.

    Every section is present from the start. A section for a stage that has not run says so,
    in the place its result would have appeared.
    """

    skill_name: str
    from_commit: str
    to_commit: str
    candidate_digest: str
    delta: str
    #: Which stages have produced results. Detection alone is the normal early state, not a
    #: degraded one — but it must be legible as such.
    stages_run: set[Stage] = field(default_factory=lambda: {Stage.DETECTION})
    verdict: str | None = None
    findings: list[str] = field(default_factory=list)
    comparison: dict[str, object] | None = None
    canary_contacts: list[str] = field(default_factory=list)
    #: Set when a later candidate has superseded this one (FR-004b). A stale package is not
    #: acceptable, and says so rather than being quietly withdrawn.
    superseded: bool = False

    def limits(self) -> list[str]:
        """What this package does NOT establish, stated stage by stage.

        Two kinds of limit, and keeping them apart is the point:

        * **What has not run.** Named per absent stage, because a reader scanning for a
          finding must not mistake an unrun stage for a clean one.
        * **What running everything still would not establish.** ADR-0053's own honest limit —
          detonation catches only what the corpus provokes, so a payload conditioned on a
          trigger the corpus does not supply behaves cleanly and stays dormant. The runtime
          governance floor remains the backstop, and nothing here makes an adopted skill safe.

        The second is returned even when every stage has run, which is the case where it is
        most needed and most likely to be dropped.
        """
        statements = []
        if Stage.ANALYSIS not in self.stages_run:
            statements.append(
                "No adversarial analysis has run. This is not a clean read — it is the "
                "absence of a read."
            )
        if Stage.DETONATION not in self.stages_run:
            statements.append(
                "No detonation has run. Behaviour against the task corpus is unknown, and "
                "unknown is not unchanged."
            )
        statements.append(
            "Detonation catches only what the corpus provokes: a payload conditioned on a "
            "trigger the corpus does not supply behaves cleanly under test and stays "
            "dormant. The runtime governance floor remains the backstop, and nothing in "
            "this package establishes that this skill is safe."
        )
        if self.superseded:
            statements.append(
                "Upstream has moved since this evidence was produced. It describes bytes "
                "that are no longer the candidate, and cannot be accepted."
            )
        return statements

    def section(self, stage: Stage) -> str:
        """What to render where a stage's result belongs — including when it has none.

        Never returns an empty string: the caller must always have something to place, so a
        template cannot silently omit a section by rendering nothing.
        """
        if stage not in self.stages_run:
            return f"not run: {stage.value}"
        if stage is Stage.ANALYSIS:
            return f"{self.verdict}: {', '.join(self.findings) or 'no findings'}"
        if stage is Stage.DETONATION:
            return f"compared: {self.comparison or 'no differences reported'}"
        return f"{self.from_commit[:8]}..{self.to_commit[:8]}"

    def acceptable(self) -> bool:
        """Whether a human may accept this package.

        Supersession is the only thing this refuses on. **Nothing here decides whether the
        skill promotes** — a clean package is not an approval, and the acceptance is a
        person's act recorded separately (FR-021, FR-022).
        """
        return not self.superseded


__all__ = ["EvidencePackage", "Stage"]
