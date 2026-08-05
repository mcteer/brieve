# SPDX-License-Identifier: Apache-2.0
"""The hardened untrusted-content isolation tier (037, FR-006; ADR-0038).

**A ceiling is not a tier, and conflating them was this feature's first CRITICAL.** A ceiling
bounds what a definition may *call*; a tier bounds what the process can *reach*. An analysis
agent with the narrowest ceiling in the fleet, running in an allocation that shares the host's
network namespace and mounts the repository, satisfies every ceiling assertion while sitting
one library call away from everything the ceiling was protecting.

ADR-0038 named this tier in 2026 — "repository analysis runs in the hardened untrusted-content
isolation tier, with injection-lens hooks... application code is adversarial input, and the
platform treats it that way regardless of who supplied it" — and nothing implemented it. This
is the declaration half: a definition can *require* the tier, and dispatch refuses a definition
that asks for it into an allocation that does not provide it.

**A tier nothing checks is a comment in a jobspec.** The posture lives in the jobspec; this is
what makes the posture load-bearing rather than aspirational.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from core.errors import CoreError


class TierRefused(CoreError):
    """A definition requiring the hardened tier was dispatched somewhere that is not one."""


class IsolationTier(StrEnum):
    """Where a definition's work is permitted to run."""

    #: The ordinary substrate every other agent runs on.
    STANDARD = "standard"
    #: Untrusted-content analysis: no host network, no repository, allowlisted egress only.
    HARDENED = "hardened"


@dataclass(frozen=True)
class TierPosture:
    """What an allocation actually provides, read from its own configuration.

    Each field is a *tier* property — something about what the process can reach — and none
    of them is expressible as a ceiling. That is the distinction this dataclass exists to
    make concrete.
    """

    #: `bridge`, never `host`. Host mode shares the machine's network namespace, which is the
    #: defect `portal.nomad.hcl` records finding for the opposite reason (a surface nobody
    #: could reach). Here the consequence runs the other way: a workload reading hostile
    #: content would sit on the same network as everything else.
    network_mode: str
    #: Where egress is permitted at all. Empty means nowhere, which is stricter than the tier
    #: requires but never wrong.
    egress_allowlist: frozenset[str]
    #: Whether the repository is mounted. It must not be: the delta is delivered as INPUT, so
    #: there is nothing on disk for a redirected analyzer to read or write.
    repo_mounted: bool

    def is_hardened(self) -> tuple[bool, str]:
        """Whether this posture is the hardened tier, and if not, which clause failed."""
        if self.network_mode != "bridge":
            return False, f"network_mode is {self.network_mode!r}, not 'bridge'"
        if self.repo_mounted:
            return False, "the repository is mounted; the delta must be delivered as input"
        return True, ""


def assert_tier(required: IsolationTier, provided: TierPosture) -> None:
    """Refuse a definition that requires the hardened tier outside one.

    Fail-closed and by *clause*: the refusal names which property was missing, because
    "isolation failed" tells an operator nothing about what to fix, and a tier that fails
    opaquely is one people route around.
    """
    if required is not IsolationTier.HARDENED:
        return
    hardened, why = provided.is_hardened()
    if not hardened:
        raise TierRefused(
            f"this definition requires the hardened untrusted-content tier and the "
            f"allocation does not provide it: {why}"
        )


__all__ = ["IsolationTier", "TierPosture", "TierRefused", "assert_tier"]
