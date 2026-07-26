# SPDX-License-Identifier: Apache-2.0
"""Execution bounds — a run cannot consume authority indefinitely (FR-011).

Checked **where the run advances**, not by a background timer. A bound enforced by a
separate timer is a bound that fails when the timer does, and its failure is silent:
the run simply keeps going. Checking at the point of progress means the check cannot be
skipped by the work proceeding.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.authority.clock import Clock
from core.errors import CoreError

DEFAULT_MAX_DURATION = timedelta(hours=1)
DEFAULT_MAX_STEPS = 100
DEFAULT_STUCK_WAIT = timedelta(minutes=10)


class ExecutionBoundExceeded(CoreError):
    """A bound stopped the run. ``reason`` names which one."""

    def __init__(self, reason: str, *, correlation_id: str | None = None) -> None:
        super().__init__(f"execution bound exceeded: {reason}", correlation_id=correlation_id)
        self.reason = reason
        self.reason_code = "bound_exceeded"


@dataclass(frozen=True)
class ExecutionBounds:
    max_duration: timedelta = DEFAULT_MAX_DURATION
    max_steps: int = DEFAULT_MAX_STEPS
    stuck_wait_timeout: timedelta = DEFAULT_STUCK_WAIT


@dataclass
class BoundsTracker:
    """Mutable progress against the bounds, advanced by the invoke path."""

    bounds: ExecutionBounds
    started_at: datetime
    steps_taken: int = 0
    last_progress_at: datetime | None = None

    def record_progress(self, now: datetime) -> None:
        self.steps_taken += 1
        self.last_progress_at = now

    def check(self, clock: Clock, *, correlation_id: str | None = None) -> None:
        """Raise :class:`ExecutionBoundExceeded` if any bound has been reached.

        Order matters only for which reason is reported first; all three are checked
        on every advance so none can be starved by another tripping late.
        """
        now = clock.now()
        if now - self.started_at >= self.bounds.max_duration:
            raise ExecutionBoundExceeded("max_duration", correlation_id=correlation_id)
        if self.steps_taken >= self.bounds.max_steps:
            raise ExecutionBoundExceeded("max_steps", correlation_id=correlation_id)
        since = self.last_progress_at or self.started_at
        if now - since >= self.bounds.stuck_wait_timeout:
            raise ExecutionBoundExceeded("stuck_wait", correlation_id=correlation_id)
