# SPDX-License-Identifier: Apache-2.0
"""Which processes the deployment runs, read from the deployment itself.

**Enumerates every job definition, not the marked ones.** Coverage that a process opts into
is fail-open: a definition added without a declaration is invisible, and the gate cannot
fail for a process it never knew about. The process nobody remembered to enrol is exactly
the one nobody remembered to cover — so every definition on disk must be a declared subject
or an explicitly excluded one, and anything that is neither fails.

That is the whole reason this module reads the directory rather than a list. A list of
*subjects* goes stale silently, which is what 010 lost a feature's rows to. A list of
*exclusions* names files that must exist, so a stale entry fails on the next run. Opposite
failure modes, and only one of them is quiet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JOBS = ROOT / "infra" / "jobs"

#: Definitions deliberately outside the gate's subjects, and why. Checked against the
#: filesystem on every run — an entry naming a file that is gone fails rather than hides.
EXCLUDED = {
    "postgres": "vendor image; no assembly of ours to reach",
    "collector-postgres": "vendor image; no assembly of ours to reach",
    "conformance": "the gate's own runner — asserting against it is circular",
    "harness-probe": (
        "a one-shot readiness probe, not a process with an assembly. It runs, answers, and "
        "exits, and what it proves is already asserted by whatever consumes its answer."
    ),
}

VALID_SHAPES = frozenset({"served", "dispatched"})


class DeclarationError(AssertionError):
    """A job definition the gate cannot place. Never a skip — see FR-005a."""


@dataclass(frozen=True)
class DeclaredProcess:
    """A process the deployment runs, as its own definition declares it."""

    name: str
    shape: str
    covered_by: str
    #: Whether the deployment lane stands this one up. False for processes covered by rows
    #: that live elsewhere — they are already running, or already dispatched, and this lane
    #: asserts that the coverage exists rather than duplicating it.
    lane_starts: bool

    @property
    def covered_by_path(self) -> Path:
        return ROOT / self.covered_by


def _meta(text: str, key: str) -> str | None:
    match = re.search(rf'{key}\s*=\s*"([^"]*)"', text)
    return match.group(1) if match else None


def definitions_on_disk() -> list[str]:
    return sorted(p.name.removesuffix(".nomad.hcl") for p in JOBS.glob("*.nomad.hcl"))


def declared() -> list[DeclaredProcess]:
    """Every declared process, with a malformed declaration raising rather than dropping.

    An unrecognised `harness_shape` fails here instead of defaulting. A typo must not
    silently remove a process from coverage — that is the failure mode this whole feature
    exists to close, and reproducing it inside the mechanism would be its own indictment.
    """
    found: list[DeclaredProcess] = []
    for name in definitions_on_disk():
        text = (JOBS / f"{name}.nomad.hcl").read_text()
        if _meta(text, "harness_surface") != "true":
            continue

        shape = _meta(text, "harness_shape")
        if shape not in VALID_SHAPES:
            raise DeclarationError(
                f"{name} declares harness_shape={shape!r}, which is not one of "
                f"{sorted(VALID_SHAPES)}. Refused rather than defaulted: a typo here would "
                f"drop the process from coverage without anything noticing."
            )

        covered_by = _meta(text, "harness_covered_by")
        if not covered_by:
            raise DeclarationError(f"{name} declares no harness_covered_by")

        found.append(
            DeclaredProcess(
                name=name,
                shape=shape,
                covered_by=covered_by,
                lane_starts=_meta(text, "harness_lane_starts") == "true",
            )
        )
    return found


def unplaced() -> dict[str, str]:
    """Definitions that are neither declared nor excluded, and stale exclusions.

    Both directions, because each is a different way the gate lies about its coverage.
    """
    on_disk = set(definitions_on_disk())
    declared_names = {p.name for p in declared()}
    problems = {
        name: "neither declared nor excluded — enrol it or exclude it with a reason"
        for name in sorted(on_disk - declared_names - EXCLUDED.keys())
    }
    problems.update(
        {
            name: "excluded, but no such job definition exists — a stale exclusion"
            for name in sorted(EXCLUDED.keys() - on_disk)
        }
    )
    return problems


__all__ = [
    "EXCLUDED",
    "DeclarationError",
    "DeclaredProcess",
    "declared",
    "definitions_on_disk",
    "unplaced",
]
