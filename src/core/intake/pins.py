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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

#: How the current upstream head is obtained. Injected so one pipeline serves a connected
#: estate, a restricted one behind a proxy, and an air-gapped one reading an imported
#: snapshot — ADR-0021's 'one trigger difference' expressed as an argument.
Fetcher = Callable[["Pin"], str]


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


__all__ = [
    "CheckResult",
    "Fetcher",
    "Pin",
    "PinState",
    "check_pin",
    "github_head_fetcher",
    "snapshot_fetcher",
    "read_pin",
    "read_pins",
]


@dataclass(frozen=True)
class CheckResult:
    """What one check of one pin found.

    ``state`` is always set; ``upstream_commit`` and ``detail`` are populated per state. A
    single result type rather than three, so a caller cannot handle two states and silently
    drop the third — which is the specific way UNREACHABLE gets folded into UNMOVED.
    """

    pin: Pin
    state: PinState
    upstream_commit: str = ""
    detail: str = ""


def check_pin(pin: Pin, fetch_head: Fetcher) -> CheckResult:
    """Compare a pin against upstream, or report that upstream could not be reached.

    ``fetch_head`` is injected rather than imported so the same function serves all three
    connectivity tiers (ADR-0021): a connected estate passes a network fetch, a restricted one
    passes a proxy fetch, an air-gapped one passes a snapshot reader. **One pipeline with one
    trigger difference** — the difference is this argument, and nothing downstream knows which
    it got.
    """
    try:
        head = fetch_head(pin)
    except Exception as exc:  # noqa: BLE001 — any failure is unreachability, never "unmoved"
        return CheckResult(
            pin=pin,
            state=PinState.UNREACHABLE,
            detail=f"{type(exc).__name__}: {exc}",
        )
    head = head.strip()
    if not head:
        # An empty answer is not agreement. A fetcher that returned nothing has told us
        # nothing, and reporting that as UNMOVED is how a pin rots while looking maintained.
        return CheckResult(pin=pin, state=PinState.UNREACHABLE, detail="empty response")
    if head == pin.commit:
        return CheckResult(pin=pin, state=PinState.UNMOVED, upstream_commit=head)
    return CheckResult(pin=pin, state=PinState.MOVED, upstream_commit=head)


def github_head_fetcher(open_url: Callable[[str], bytes]) -> Fetcher:
    """A fetcher over a repository host's ref API, for connected and proxied estates.

    ``open_url`` is injected so the transport stays the caller's choice — `urllib` here as
    everywhere else in this repository (no HTTP client enters the tree), or a proxy-aware
    reader in a restricted estate. `core` never opens a socket itself.
    """

    def fetch(pin: Pin) -> str:
        owner_repo = pin.repository.rstrip("/").removeprefix("https://github.com/")
        payload = open_url(f"https://api.github.com/repos/{owner_repo}/commits/HEAD")
        import json

        return str(json.loads(payload).get("sha", ""))

    return fetch


def snapshot_fetcher(snapshot: Mapping[str, str]) -> Fetcher:
    """A fetcher over an imported bundle, for air-gapped estates (FR-001).

    The air-gapped half of ADR-0021's answer, and the half analyze pass 2 found asserted but
    unbuilt. It is deliberately trivial: a snapshot is a recorded mapping of repository to
    head, produced when the bundle was assembled. **The point is that it is the same
    `Fetcher`** — the pipeline downstream cannot tell an imported bundle from a live read,
    which is what makes "one pipeline with one trigger difference" true rather than claimed.

    A repository absent from the snapshot raises, and `check_pin` turns that into
    UNREACHABLE: a bundle that does not mention a pin has not told us the pin is unchanged.
    """

    def fetch(pin: Pin) -> str:
        return snapshot[pin.repository]

    return fetch
