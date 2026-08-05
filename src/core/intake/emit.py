# SPDX-License-Identifier: Apache-2.0
"""Emitting the proposal — the artifact US1 exists to produce (037, FR-004/FR-004a).

Analyze pass 2 found this missing: FR-004 said what a proposal must carry, a conformance row
asserted one appears, and nothing wrote it. The gap hid because a scheduled workflow implies a
pull request and a reader supplies the missing step mentally. 033 kept its poller and its
PR-proposal half as separate, deliberate pieces of work for exactly this reason.

**What is emitted is a detection proposal**, not a partial evidence package. Every section is
present from the start; the ones whose stage has not run say so where their result would have
appeared. An omitted section and a section reading "not run" are identical to a grep and
opposite to a reader — and *"no analysis has run"* is a materially different claim from
*"analysis found nothing."*
"""

from __future__ import annotations

from core.intake.package import EvidencePackage, Stage
from core.intake.pins import CheckResult, PinState

#: 033's accepted limitation, carried in the proposal body rather than worked around. A PR
#: opened with the default token triggers no workflows (GitHub's recursion guard); the usual
#: fix is a personal access token, which is the standing credential Principle IV refuses. So
#: the proposal explains its own missing checks instead of the platform acquiring one.
_NO_CHECKS_NOTE = (
    "CI does not run on this proposal. It was opened by the scheduled poller using the "
    "default token, and a token-created pull request does not trigger workflows. The usual "
    "fix is a personal access token; this platform does not hold one, because a long-lived "
    "credential is exactly what Principle IV refuses. Run the gauntlet's stages locally or "
    "re-open this pull request by hand to get checks."
)


def detection_proposal(
    result: CheckResult, *, candidate_digest: str, delta: str
) -> EvidencePackage:
    """Build the package a moved pin produces, with detection alone filled in."""
    if result.state is not PinState.MOVED:
        raise ValueError(
            f"a proposal describes a moved pin; this one is {result.state.value!r}. "
            "An unmoved or unreachable check proposes nothing (FR-002, FR-003)."
        )
    return EvidencePackage(
        skill_name=result.pin.pack,
        from_commit=result.pin.commit,
        to_commit=result.upstream_commit,
        candidate_digest=candidate_digest,
        delta=delta,
        stages_run={Stage.DETECTION},
    )


def render(package: EvidencePackage) -> str:
    """The proposal body a reviewer reads.

    Sections are rendered for **every** stage, run or not, because the shape of this artifact
    is where FR-027's reassurance failure arrives most easily. The limits statement is last
    and unconditional.
    """
    lines = [
        f"# Skill intake proposal: {package.skill_name}",
        "",
        f"- **From**: `{package.from_commit}`",
        f"- **To**: `{package.to_commit}`",
        f"- **Candidate digest**: `{package.candidate_digest}`",
        "",
        "## What changed",
        "",
        package.delta or "_(empty delta)_",
        "",
    ]
    for stage in Stage:
        lines += [f"## {stage.value.title()}", "", package.section(stage), ""]
    lines += ["## What this does not establish", ""]
    lines += [f"- {statement}" for statement in package.limits()]
    lines += ["", "---", "", _NO_CHECKS_NOTE, ""]
    return "\n".join(lines)


__all__ = ["detection_proposal", "render"]
