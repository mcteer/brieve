# SPDX-License-Identifier: Apache-2.0
"""Promote the production-shaped Vault five-file set (eval-lane → packs/)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = _SCRIPT_DIR.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(_SCRIPT_DIR))

from _common import refinement_available  # noqa: E402

from core.evals.promotion import promote_phase_agents  # noqa: E402
from core.packs.loader import content_digest  # noqa: E402

CANDIDATES = ROOT / "evals" / "prompt-tune" / "candidates" / "vault"
PHASES = ("research", "plan", "write", "judge", "propose")

PROVENANCE = """# Provenance — vault {phase} AGENTS.md

Authored in this repository for 049. These bytes are executed Build instructions, not
consulted skills.{judge_note}

| Field | Value |
| --- | --- |
| Authorship date | 2026-08-24 |
| Form | Pack phase AGENTS.md (not repository-root contributor AGENTS.md) |
| Source | Individual GEPA, then production-shaped (no FILE protocol, no grading overlay). |
| Write | `AGENTS.production.md`. Vault Write GEPA uses phase needles (authoring gates are Terraform). |
| Joint compile | Not run. Joint metric is needles. |

## Injection-lens review

Performed at promotion, 2026-08-24, over the full text of `AGENTS.md`.

Result: clear. The file is product-and-phase practice addressed to the Build cell. It does
not override system instructions, request context exfiltration, or redirect tool use away
from the governed registry.
"""


def main() -> int:
    if not refinement_available():
        print("refinement_unavailable", file=sys.stderr)
        return 2
    files: dict[str, bytes] = {}
    provenance: dict[str, str] = {}
    versions: dict[str, str] = {}
    for phase in PHASES:
        path = CANDIDATES / phase / "AGENTS.production.md"
        body = path.read_bytes()
        files[phase] = body
        judge_note = " Judge is not Write (ADR-0039)." if phase == "judge" else ""
        provenance[phase] = PROVENANCE.format(phase=phase, judge_note=judge_note)
        versions[phase] = "0.2.0"
    digests = {name: content_digest(body) for name, body in files.items()}
    recorded = promote_phase_agents(
        pack="vault",
        files=files,
        provenance=provenance,
        expected_digests=digests,
        versions=versions,
        suites_passed=("phase_agents", "build_agents"),
        packs_root=ROOT / "packs",
        refinement_available=True,
    )
    for phase in PHASES:
        print(f"{phase} {recorded[phase]} {recorded[f'{phase}.version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
