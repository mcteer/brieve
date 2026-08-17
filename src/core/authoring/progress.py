# SPDX-License-Identifier: Apache-2.0
"""User-visible Propose phase progress (047).

Ordered Research → Plan → Write → Judge → Propose. Fail-closed: after a failed phase, later
phases cannot become active or completed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class PhaseName(StrEnum):
    RESEARCH = "research"
    PLAN = "plan"
    WRITE = "write"
    JUDGE = "judge"
    PROPOSE = "propose"


PHASE_ORDER: tuple[PhaseName, ...] = (
    PhaseName.RESEARCH,
    PhaseName.PLAN,
    PhaseName.WRITE,
    PhaseName.JUDGE,
    PhaseName.PROPOSE,
)


class PhaseStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


PROGRESS_KEY = "propose_progress"


@dataclass(frozen=True)
class PhaseState:
    name: PhaseName
    status: PhaseStatus
    reason: str | None = None


@dataclass(frozen=True)
class ProposeProgress:
    phases: tuple[PhaseState, ...]
    current: PhaseName | None

    def to_payload(self) -> dict[str, Any]:
        return {
            "current": self.current.value if self.current else None,
            "phases": [
                {
                    "name": p.name.value,
                    "status": p.status.value,
                    **({"reason": p.reason} if p.reason else {}),
                }
                for p in self.phases
            ],
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> ProposeProgress | None:
        if not payload or not isinstance(payload, dict):
            return None
        raw_phases = payload.get("phases")
        if not isinstance(raw_phases, list):
            return None
        phases: list[PhaseState] = []
        for item in raw_phases:
            if not isinstance(item, dict):
                return None
            phases.append(
                PhaseState(
                    name=PhaseName(str(item["name"])),
                    status=PhaseStatus(str(item["status"])),
                    reason=str(item["reason"]) if item.get("reason") else None,
                )
            )
        current_raw = payload.get("current")
        current = PhaseName(str(current_raw)) if current_raw else None
        return cls(phases=tuple(phases), current=current)


class ProgressRefused(ValueError):
    """An illegal phase transition."""


def initial_progress() -> ProposeProgress:
    """All phases pending; none active until Research advances."""
    return ProposeProgress(
        phases=tuple(PhaseState(name=n, status=PhaseStatus.PENDING) for n in PHASE_ORDER),
        current=None,
    )


def advance(progress: ProposeProgress, *, into: PhaseName) -> ProposeProgress:
    """Mark ``into`` active. Complete priors that already ran; leave skipped ones pending.

    Plan and Judge are not always-green fixtures (047). Jumping Research → Write must not
    paint those unimplemented phases completed. Refuse if a prior phase failed.
    """
    by_name = {p.name: p for p in progress.phases}
    for name in PHASE_ORDER:
        if name == into:
            break
        prior = by_name[name]
        if prior.status == PhaseStatus.FAILED:
            raise ProgressRefused(f"cannot advance to {into}: {name} failed")

    phases: list[PhaseState] = []
    for name in PHASE_ORDER:
        if name == into:
            phases.append(PhaseState(name=name, status=PhaseStatus.ACTIVE))
        elif PHASE_ORDER.index(name) < PHASE_ORDER.index(into):
            prev = by_name[name]
            if prev.status == PhaseStatus.FAILED:
                raise ProgressRefused(f"cannot advance to {into}: {name} failed")
            # Only complete work that actually ran. Auto-completing a still-pending prior
            # (Plan/Judge while Write is live) would paint unimplemented 047 phases green.
            if prev.status in (PhaseStatus.COMPLETED, PhaseStatus.ACTIVE):
                phases.append(
                    PhaseState(name=name, status=PhaseStatus.COMPLETED, reason=prev.reason)
                )
            else:
                phases.append(PhaseState(name=name, status=PhaseStatus.PENDING))
        else:
            phases.append(PhaseState(name=name, status=PhaseStatus.PENDING))
    return ProposeProgress(phases=tuple(phases), current=into)


def complete(progress: ProposeProgress, *, phase: PhaseName) -> ProposeProgress:
    """Mark ``phase`` completed (must be active or already completed)."""
    phases: list[PhaseState] = []
    for p in progress.phases:
        if p.name == phase:
            if p.status == PhaseStatus.FAILED:
                raise ProgressRefused(f"cannot complete failed phase {phase}")
            phases.append(PhaseState(name=phase, status=PhaseStatus.COMPLETED))
        else:
            phases.append(p)
    current = progress.current if progress.current != phase else None
    return ProposeProgress(phases=tuple(phases), current=current)


def fail(progress: ProposeProgress, *, phase: PhaseName, reason: str) -> ProposeProgress:
    """Mark ``phase`` failed; later phases stay pending."""
    safe = (reason or "refused").strip() or "refused"
    phases: list[PhaseState] = []
    for p in progress.phases:
        if p.name == phase:
            phases.append(PhaseState(name=phase, status=PhaseStatus.FAILED, reason=safe))
        elif PHASE_ORDER.index(p.name) > PHASE_ORDER.index(phase):
            phases.append(PhaseState(name=p.name, status=PhaseStatus.PENDING))
        else:
            phases.append(p)
    return ProposeProgress(phases=tuple(phases), current=None)


__all__ = [
    "PHASE_ORDER",
    "PROGRESS_KEY",
    "PhaseName",
    "PhaseState",
    "PhaseStatus",
    "ProgressRefused",
    "ProposeProgress",
    "advance",
    "complete",
    "fail",
    "initial_progress",
]
