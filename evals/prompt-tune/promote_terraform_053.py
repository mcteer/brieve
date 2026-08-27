# SPDX-License-Identifier: Apache-2.0
"""Promote the 053 Terraform five-file set (eval-lane → packs/).

**Why the set re-promotes.** 053 delegates the style rules the `plan`, `write` and `judge`
cards had been restating by hand — eighteen, thirteen and eight of them — so all three are
steered by different bytes than the ones their cells were qualified against. FR-010 says the
edit and its passing eval promote together; a card may not ship on the eval that qualified the
previous text.

`research` and `propose` are unchanged and travel because promotion is all-five-or-none.

Not a GEPA run. Nothing here re-optimises a prompt; the cards lost duplicated rules and gained
three declared overrides.
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

CANDIDATES = ROOT / "evals" / "prompt-tune" / "candidates" / "terraform-053"
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
| Source | 0.3.0 card, amended by 053. No GEPA run; no prompt re-optimised. |
| Skills bound | {bound} |
| Change | {change} |
| Promotion | All five or none. Both suites scored over the **assembled** instruction. |

## What 053 changed, and why the whole set moved

051 delivered the pinned guide to `plan`, `write` and `judge` and could not show that
receiving it changed anything. Measured hermetically on 2026-08-27: the Write card stated
**every one** of the guide's prose rules by hand, so removing the binding would have left them
all in force and SC-002 was unmeasurable by construction. Judge and Plan restated thirteen and
eight.

Those rules are now delegated. What stays is what the guide does not cover — estate shape,
minimality, provider-syntax caution, least privilege — and three **declared overrides**, each
saying in the card what it contradicts and why. The known disagreement is version pinning: the
guide shows `required_version = ">= 1.14"` and lists `>=` among its constraint operators, while
this platform refuses a floating constraint. 051's precedence rule resolved that silently at
runtime; it is now visible on the page.

The cards are not much shorter. An override needs its reason stated and a delegation needs to
say what it delegates; the win is one source of truth, not fewer bytes.

`research` and `propose` are byte-identical and move only because promotion is all-five-or-none.

## Injection-lens review

Performed at promotion, 2026-08-27, over the full text of `AGENTS.md`.

Result: clear. The file is product-and-phase practice addressed to the Build cell. It does
not override system instructions, request context exfiltration, or redirect tool use away
from the governed registry.

053 **removes** text and adds three override notices; it introduces no new instruction to the
model beyond pointers to content already lensed on its own path.

The delivered skills are lensed on their own path, at `promote_skill`. Combined content is
therefore lensed in halves; 051 adds no new content, only a new adjacency, so no third pass
is introduced. "We lensed the parts" and "we lensed the whole" are different claims, and this
is the first.
"""

CHANGE = {
    "research": "Unchanged. Travels because promotion is all-five-or-none.",
    "plan": "Delegated 8 restated rules; declares 2 overrides (pinning, lock file).",
    "write": "Delegated 18 restated rules; declares the pinning override.",
    "judge": "Delegated 13 restated rules; declares the pinning override.",
    "propose": "Unchanged. Travels because promotion is all-five-or-none.",
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
        versions[phase] = "0.4.0"
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
