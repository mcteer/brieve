# SPDX-License-Identifier: Apache-2.0
"""The hardened untrusted-content isolation tier (037 FR-006, 038 FR-005; ADR-0038).

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
class SubjectMount:
    """A tree the analysis is *about*, mounted for it to read (038, FR-005).

    **Not the platform's tree, which is what `repo_mounted` guards.** 037 delivered its
    subject as payload because a skill delta is kilobytes; a provided application repository
    is not, so 038 mounts it. That looks like a reversal of 037's no-mount rule and is not:
    the rule was *do not hand a redirected analyser the platform's own tree*, and this is
    somebody else's.

    ``source`` is carried rather than only a boolean because the subject differs every run,
    so its path is per-dispatch — and a dispatch naming the platform tree would satisfy every
    other clause here while mounting exactly what the tier exists to keep out. A control
    expressed as a declaration is only as good as whatever validates the declaration; here the
    row checks a *path* rather than a claim about one.
    """

    source: str
    read_only: bool


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
    #: requires but never wrong — and is what 038's analysis step declares, because it reads a
    #: mount and fetches nothing.
    egress_allowlist: frozenset[str]
    #: Whether **the platform's own repository** is mounted. It must not be. 037 delivered its
    #: delta as INPUT, so there was nothing on disk at all; 038 mounts a subject and still
    #: never mounts this one. The name is unchanged because the meaning is unchanged.
    repo_mounted: bool
    #: The tree the analysis is about, when there is one. ``None`` is 037's payload delivery
    #: and passes unchanged; a **writable** subject fails.
    subject_mount: SubjectMount | None = None

    def is_hardened(self) -> tuple[bool, str]:
        """Whether this posture is the hardened tier, and if not, which clause failed."""
        if self.network_mode != "bridge":
            return False, f"network_mode is {self.network_mode!r}, not 'bridge'"
        if self.repo_mounted:
            return False, "the repository is mounted; the delta must be delivered as input"
        if self.subject_mount is not None and not self.subject_mount.read_only:
            return False, (
                f"the subject at {self.subject_mount.source!r} is mounted writable; an "
                f"analysis tier reads its subject and never writes it"
            )
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


__all__ = ["IsolationTier", "SubjectMount", "TierPosture", "TierRefused", "assert_tier"]
