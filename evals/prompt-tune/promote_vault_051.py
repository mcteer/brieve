# SPDX-License-Identifier: Apache-2.0
"""Promote the 051 Vault five-file set (eval-lane → packs/).

**The Vault pack binds nothing, and all five of its files said otherwise.** Each read
*"Practice is this file and the pinned skill `vault-secret-access`"* while the manifest bound
that skill to no phase — the same defect 051 removes from the Terraform pack, in a pack the
spec had recorded as clean.

It was found by the enforcement row rather than by reading: SC-006 says *no phase instruction
in any shipped pack* may name practice it will not receive, enforced rather than audited by
hand, and the row failed on Vault the first time it ran.

**The claim is corrected; the binding is not added.** Vault stays deliberately unbound. It is
the live fixture for "adopted, pinned, and delivered nowhere" — the state US2 must keep
distinguishable from delivery, and the one FR-011 uses to prove an unbound phase is
byte-identical to what it was. Binding it to silence the row would destroy the only evidence
that unbound still works.

Not a GEPA run. The cards are unchanged apart from the removed sentence.
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

CANDIDATES = ROOT / "evals" / "prompt-tune" / "candidates" / "vault-051"
PACK = ROOT / "packs" / "vault"
PHASES = ("research", "plan", "write", "judge", "propose")

#: Vault binds nothing, and that is the point of this pack. Recorded in provenance because a
#: reader of a phase file cannot otherwise tell adopted-and-inert from delivered.
BOUND: set[str] = set()

PROVENANCE = """# Provenance — vault {phase} AGENTS.md

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

Every file claimed `vault-secret-access` as practice. The manifest binds it to no phase, so
no Vault cell has ever received it and none does now. The sentence is removed; the binding is
not added.

Vault stays unbound on purpose. It is the pack that proves adopted-and-inert remains
distinguishable from delivered — `content_pins` records it `@unbound`, and an unbound phase's
instruction is byte-identical to its file. Binding it to satisfy the row would remove the
only evidence that the unbound path still works.

Phase-agent promotion is all-five-or-none, so all five move for one corrected sentence.

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

CLAIM_DROPPED = "Dropped the false claim to `vault-secret-access` (FR-010, SC-006). No binding."
CHANGE = dict.fromkeys(("research", "plan", "write", "judge", "propose"), CLAIM_DROPPED)


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
            bound="None. This pack adopts a skill and binds it to no phase.",
            change=CHANGE[phase],
        )
        versions[phase] = "0.3.0"
    digests = {name: content_digest(body) for name, body in files.items()}

    suites = _qualify()
    try:
        recorded = promote_phase_agents(
            pack="vault",
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
