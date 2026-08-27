# SPDX-License-Identifier: Apache-2.0
"""Promote the 051 Terraform five-file set (eval-lane → packs/).

**Why the set re-promotes at all.** 051 binds `terraform-style-guide` and
`terraform-style-guide-security` to `plan`, `write` and `judge`, so those three phases are
now steered by instruction *plus* skill — different bytes than the ones their cells were
qualified against. FR-013 says a binding and its passing eval promote together.

`research` and `propose` change for the opposite reason: they claimed both skills as practice
and receive neither, so the sentence comes out (FR-012a). Phase-agent promotion is
all-five-or-none, which is why correcting two files and binding three costs one promotion
rather than two.

Not a GEPA run. The 0.2.0 cards are unchanged apart from the precedence section and the two
corrected claims; nothing here re-optimises a prompt.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = _SCRIPT_DIR.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(_SCRIPT_DIR))

from _common import refinement_available  # noqa: E402

from core.evals.phase_agents_corpus import (  # noqa: E402
    load_build_agents_cases,
    load_phase_agents_cases,
    score_build_agents_case,
    score_phase_agents_case,
)
from core.evals.promotion import PromotionRefused, promote_phase_agents  # noqa: E402
from core.evals.suites import BUILD_AGENTS_QUALIFICATION, PHASE_AGENTS_QUALIFICATION  # noqa: E402
from core.packs.loader import content_digest  # noqa: E402

CANDIDATES = ROOT / "evals" / "prompt-tune" / "candidates" / "terraform-051"
PACK = ROOT / "packs" / "terraform"
PHASES = ("research", "plan", "write", "judge", "propose")

#: Which phases the manifest binds. Recorded in provenance because a reader of a phase file
#: cannot otherwise tell whether the skills below it were delivered or merely adopted.
BOUND = {"plan", "write", "judge"}

PROVENANCE = """# Provenance — terraform {phase} AGENTS.md

Authored in this repository. These bytes are executed Build instructions, not consulted
skills.

| Field | Value |
| --- | --- |
| Authorship date | 2026-08-27 |
| Form | Pack phase AGENTS.md (not repository-root contributor AGENTS.md) |
| Source | 0.2.0 card, amended by 051. No GEPA run; no prompt re-optimised. |
| Skills bound | {bound} |
| Change | {change} |
| Promotion | All five or none. Both suites scored over the **assembled** instruction. |

## What 051 changed, and why the whole set moved

`terraform-style-guide` and `terraform-style-guide-security` are pinned and digest-verified,
and until 051 no phase received either. All five files nonetheless read *"Practice is this
file and the pinned skills …"*, which was false everywhere.

Binding `plan`, `write` and `judge` changes what those cells are steered by, so they are
re-qualified against instruction plus skill rather than instruction alone (FR-013).
`research` and `propose` stop claiming practice they will not receive (FR-012a). Phase-agent
promotion is all-five-or-none, so both corrections travel together.

Plan is bound because its output is Write's instruction. The paths and intent Plan names are
what Write works from, so a plan formed without the skills can direct Write toward something
the skills would not sanction — and Write receiving them does not undo a direction it was
told to take.

## Injection-lens review

Performed at promotion, 2026-08-27, over the full text of `AGENTS.md`.

Result: clear. The file is product-and-phase practice addressed to the Build cell. It does
not override system instructions, request context exfiltration, or redirect tool use away
from the governed registry.

The delivered skills are lensed on their own path, at `promote_skill`. Combined content is
therefore lensed in halves; 051 adds no new content, only a new adjacency, so no third pass
is introduced. "We lensed the parts" and "we lensed the whole" are different claims, and this
is the first.
"""

CHANGE = {
    "research": "Dropped the false claim to both skills (FR-012a). No binding.",
    "plan": "Bound to both skills; precedence section added (FR-012, FR-014, FR-014a).",
    "write": "Bound to both skills; precedence section added (FR-012, FR-014, FR-014a).",
    "judge": "Bound to both skills; precedence section added (FR-012, FR-014, FR-014a).",
    "propose": "Dropped the false claim to both skills (FR-012a). No binding.",
}


def _qualify() -> tuple[str, ...]:
    """Run both suites over the candidate set. Returns the suites that passed.

    Scored through `score_*_case`, which assembles instruction plus bound skills — so a cell
    is qualified against the bytes its model will actually receive, not against the
    instruction file alone (SC-007).
    """
    passed: list[str] = []

    phase_cases = load_phase_agents_cases(PACK)
    if all(score_phase_agents_case(c, repo_root=ROOT) == c.expected for c in phase_cases):
        passed.append(PHASE_AGENTS_QUALIFICATION)

    build_cases = load_build_agents_cases(PACK)
    if all(score_build_agents_case(c, repo_root=ROOT) == c.expected for c in build_cases):
        passed.append(BUILD_AGENTS_QUALIFICATION)

    return tuple(passed)


def main() -> int:
    if not refinement_available():
        print("refinement_unavailable", file=sys.stderr)
        return 2

    files: dict[str, bytes] = {}
    provenance: dict[str, str] = {}
    versions: dict[str, str] = {}
    for phase in PHASES:
        body = (CANDIDATES / phase / "AGENTS.md").read_bytes()
        files[phase] = body
        provenance[phase] = PROVENANCE.format(
            phase=phase,
            bound="`terraform-style-guide`, `terraform-style-guide-security`"
            if phase in BOUND
            else "None.",
            change=CHANGE[phase],
        )
        versions[phase] = "0.3.0"
    digests = {name: content_digest(body) for name, body in files.items()}

    suites = _qualify()
    try:
        recorded = promote_phase_agents(
            pack="terraform",
            files=files,
            provenance=provenance,
            expected_digests=digests,
            versions=versions,
            suites_passed=suites,
            packs_root=ROOT / "packs",
            refinement_available=True,
        )
    except PromotionRefused as exc:
        print(f"refused: {exc.reason_code} — {exc}", file=sys.stderr)
        return 1

    for phase in PHASES:
        print(f"{phase:9} {recorded[phase][:16]}… v{recorded[f'{phase}.version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
