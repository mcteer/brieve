# SPDX-License-Identifier: Apache-2.0
"""Has the vendored skills' upstream moved? — report, never vendor (033).

**This script adds no provenance record, because one already exists.** Every adopted pack
carries `[upstream]` — repository, commit, licence, retrieved — which `core/packs/loader.py`
requires and parses into `UpstreamPin`; ADR-0004 put it there so provenance would be
"checkable rather than asserted". The planning draft proposed a second table and the analysis
pass caught it: two provenance records drift apart exactly when a bump happens, which is when
they matter. So this reads the existing pin and writes at most one line of it.

**It reports drift; it never adopts it.** When upstream has moved, the recorded commit and
the new HEAD are printed for a human to act on — and nothing is downloaded, nothing is
vendored, no digest changes. Adopting third-party content is a reviewed act: ADR-0004's
injection-lens review for first imports, `core/evals/promotion.py` for bumps. A weekly script
that quietly pulled new instructions into an agent's skill set would be the supply-chain
failure the whole pack mechanism exists to prevent, wearing automation's clothes.

**Authored packs are refused, by the field the loader already enforces.** `packs/vault` is
`provenance = "authored"` — `vault-secret-access` was written here and is intended as a PR to
hashicorp/agent-skills. "Refreshing" it from an upstream path that happens to collide would
overwrite our own authorship with somebody else's file.

Exit codes: 0 nothing to do or `retrieved` moved; 0 with drift reported (drift is news, not
failure — the proposal carries it to a human); non-zero only when the check itself could not
run.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PACKS = REPO / "packs"


def _upstream_head(repository: str) -> str:
    """The default branch's commit at `repository`, without cloning anything.

    `git ls-remote` is one round trip and downloads no content — which is the whole posture:
    this script may learn that upstream moved, and may not learn what it says.
    """
    result = subprocess.run(  # noqa: S603 — fixed binary, argument built from a pinned manifest
        ["git", "ls-remote", repository, "HEAD"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"could not reach {repository}: {result.stderr.strip()[:200]}")
    head = result.stdout.split("\t", 1)[0].strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise RuntimeError(f"{repository} answered with no usable commit: {result.stdout[:120]!r}")
    return head


def _set_retrieved(manifest: Path, when: str) -> None:
    """Rewrite the ONE line, never the file.

    `tomllib` reads and does not write, and a TOML writer would be a new dependency that
    re-serializes — erasing pack.toml's comments, which carry the reasoning that makes the
    manifest reviewable. A targeted substitution keeps the record intact.
    """
    text = manifest.read_text()
    updated, count = re.subn(
        r'(?m)^(retrieved\s*=\s*)"[^"]*"$', lambda m: f'{m.group(1)}"{when}"', text
    )
    if count != 1:
        raise RuntimeError(
            f"{manifest} has {count} `retrieved` lines; expected exactly one to update"
        )
    manifest.write_text(updated)


def check_pack(manifest: Path, *, today: str) -> tuple[str, bool]:
    """One pack. Returns (report line, whether upstream has moved)."""
    data = tomllib.loads(manifest.read_text())
    pack = data.get("pack", {})
    name = str(pack.get("name") or manifest.parent.name)

    if str(pack.get("provenance", "")) != "adopted":
        return (
            f"  {name}: authored here — not checked. Its content is ours to publish upstream, "
            f"not upstream's to publish to us.",
            False,
        )

    upstream = data.get("upstream") or {}
    repository = str(upstream.get("repository", ""))
    recorded = str(upstream.get("commit", ""))
    if not repository or not recorded:
        raise RuntimeError(
            f"{name} declares provenance 'adopted' with no [upstream] pin — the loader refuses "
            f"this manifest, and so does this check"
        )

    head = _upstream_head(repository)
    if head == recorded:
        _set_retrieved(manifest, today)
        return (f"  {name}: unchanged at {recorded[:12]} — checked {today}.", False)

    return (
        f"  {name}: UPSTREAM MOVED. Recorded {recorded[:12]}, upstream now {head[:12]}.\n"
        f"    Nothing was vendored. Adopting the change is a reviewed act — read the diff at "
        f"{repository}/compare/{recorded}...{head}, then bump through the promotion path.",
        True,
    )


def main() -> int:
    today = datetime.now(UTC).date().isoformat()
    manifests = sorted(PACKS.glob("*/pack.toml"))
    if not manifests:
        print("no packs found", file=sys.stderr)
        return 1

    drifted = False
    print("Vendored skills provenance:")
    for manifest in manifests:
        try:
            line, moved = check_pack(manifest, today=today)
        except RuntimeError as exc:
            print(f"  {manifest.parent.name}: CHECK FAILED — {exc}", file=sys.stderr)
            return 2
        print(line)
        drifted = drifted or moved

    if drifted:
        print("\nUpstream moved for at least one pack. Reported, not adopted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
