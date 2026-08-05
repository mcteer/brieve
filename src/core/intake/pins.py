# SPDX-License-Identifier: Apache-2.0
"""What an adopted skill is pinned to, and what "moved" means (037, FR-001/FR-003).

**An absent `[upstream]` table is an answer, not a fault.** `packs/vault/pack.toml` has none
deliberately — its own comment says *"that is what `authored` means"* — and the pack loader
already refuses an `adopted` pack without one. So intake never has to guess: a pack with no
pin is not adopted content and is not this pipeline's business.

**Three outcomes, never two.** Moved, unmoved, and *unreachable* are distinct, because
collapsing the third into the second is how a pin rots while looking maintained. An upstream
nobody could reach is not evidence that nothing changed.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True)
class Pin:
    """Where an adopted skill came from, and exactly which version."""

    pack: str
    repository: str
    commit: str


class PinState(StrEnum):
    """What a check of the upstream found.

    ``UNREACHABLE`` exists because the alternative — reporting a failed check as "no
    change" — makes an unmaintained pin indistinguishable from a maintained one, which is
    precisely the condition this pipeline is built to end.
    """

    UNMOVED = "unmoved"
    MOVED = "moved"
    UNREACHABLE = "unreachable"


def read_pin(manifest: Path) -> Pin | None:
    """The `[upstream]` pin from a pack manifest, or ``None`` for authored content.

    Returns ``None`` rather than raising: an authored pack is a normal thing to encounter
    while walking the packs directory, and treating it as an error would make the poller's
    ordinary path an exception path.
    """
    with manifest.open("rb") as handle:
        document = tomllib.load(handle)

    upstream = document.get("upstream")
    if not isinstance(upstream, dict):
        return None

    repository = str(upstream.get("repository", "")).strip()
    commit = str(upstream.get("commit", "")).strip()
    if not repository or not commit:
        # A partial pin is worse than none: it looks like provenance and establishes
        # nothing. The loader's rule — a supply chain with no pinned commit has nothing to
        # check — applies to half a pin exactly as it applies to none.
        return None

    pack = str(document.get("pack", {}).get("name") or manifest.parent.name)
    return Pin(pack=pack, repository=repository, commit=commit)


def read_pins(packs_root: Path) -> list[Pin]:
    """Every adopted pack's pin. Authored packs are skipped, not reported."""
    found = []
    for manifest in sorted(packs_root.glob("*/pack.toml")):
        pin = read_pin(manifest)
        if pin is not None:
            found.append(pin)
    return found


__all__ = ["Pin", "PinState", "read_pin", "read_pins"]
