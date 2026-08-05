# SPDX-License-Identifier: Apache-2.0
"""Walk every adopted pin and report what moved (037, US1).

**Nothing here adopts anything.** The poller reads pins, asks upstream what it has, and prints
what it found. A moved pin becomes a proposal; an unmoved one becomes a recorded check; an
unreachable one becomes a reported failure. All three are outcomes, and only one of them is
work for a person.

`urllib` and nothing else, as `corpus_sync.py` and the enclave readers already do: no HTTP
client enters this tree.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

from core.intake.pins import (
    CheckResult,
    Fetcher,
    PinState,
    github_head_fetcher,
    read_pins,
    snapshot_fetcher,
)


def _open_url(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 — https only
        return bytes(response.read())


def run(packs_root: Path, fetch: Fetcher) -> list[CheckResult]:
    return [check for pin in read_pins(packs_root) for check in (_check(pin, fetch),)]


def _check(pin: object, fetch: Fetcher) -> CheckResult:
    from core.intake.pins import Pin, check_pin

    assert isinstance(pin, Pin)
    return check_pin(pin, fetch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check adopted skill pins against upstream.")
    parser.add_argument("--packs", default="packs", type=Path)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=None,
        help="An imported bundle's repository->head mapping (air-gapped estates).",
    )
    args = parser.parse_args(argv)

    if args.snapshot is not None:
        fetch = snapshot_fetcher(json.loads(args.snapshot.read_text()))
    else:
        fetch = github_head_fetcher(_open_url)

    results = run(args.packs, fetch)
    if not results:
        print("no adopted packs are pinned; nothing to check")
        return 0

    unreachable = 0
    for result in results:
        if result.state is PinState.UNMOVED:
            # RECORDED, not silent. "We looked and nothing had moved" is what distinguishes a
            # maintained pin from an old one (FR-002).
            print(f"  unmoved      {result.pin.pack}  {result.pin.commit[:8]}")
        elif result.state is PinState.MOVED:
            moved = f"{result.pin.commit[:8]} -> {result.upstream_commit[:8]}"
            print(f"  MOVED        {result.pin.pack}  {moved}")
        else:
            unreachable += 1
            print(f"  unreachable  {result.pin.pack}  {result.detail}", file=sys.stderr)

    # An unreachable upstream is a failure, never "no change" (FR-003). Exiting non-zero is
    # what makes the scheduled run visible rather than quietly green.
    return 1 if unreachable else 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
