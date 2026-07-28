# SPDX-License-Identifier: Apache-2.0
"""Resume suspended runs when the dependency they wait on recovers.

**This is the mechanism that keeps humans out of the loop.** A run that cannot reach a
product suspends naming it; the sweeper resumes it on recovery. No run polls, and nobody
is told to press anything — which is the whole of ADR-0049's claim that consent to start a
run is consent to finish it.

Recovery is a platform-level event, so the response is platform-level: **one sweep resumes
every run waiting on that product.** The alternative — each run rediscovering the outage
for itself — is what turns one shared failure into thousands of individual ones.

Three properties worth stating because each is a way this could be subtly wrong:

**The checkpoint is authoritative; ``suspended_runs`` is a candidate list.** Both are
written in one transaction when a run suspends, and the sweeper re-reads the checkpoint
before resuming anything. Two stores that can disagree fail silently in both directions —
a run absent from the index is invisible forever, and a stale row resumes a finished run.

**The sweeper never carries a run's authority.** It asks the dispatcher to start a new
allocation, and that allocation manufactures its own credentials from its own attested
identity. A sweeper forwarding a credential would reintroduce replay through the back
door, after 005 spent a feature making it structurally unavailable.

**Resumption is a dispatch, not an execution.** The sweeper decides *that* a run should
resume; the allocation decides what to do next. Running the work here would put every
resumed run's lifetime inside the service's, and give it the service's identity rather than
its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from core.dependencies.types import HealthState
from core.run import RunState


class SuspendedRunIndex(Protocol):
    """Where suspended runs are listed, by what they wait on.

    A protocol rather than a concrete store, so the sweeper can be exercised without a
    database — the sweeper's logic is what these rows test, and the store has its own.
    """

    def awaiting(self, product: str) -> list[SuspendedRunRecord]:
        """Runs recorded as waiting on this product."""
        ...

    def forget(self, run_id: str) -> None:
        """Drop a run from the index — resumed, or found terminal."""
        ...


@dataclass(frozen=True)
class SuspendedRunRecord:
    """Everything a resume dispatch needs, and nothing that grants anything.

    The subject, tenant, and definition are here because the sweeper dispatches *as* the
    run — a record that only said "run-7 waits on terraform-cloud" would let the sweeper
    know a run should resume and not say as whom. It carries no credential and no
    authority: the resumed allocation manufactures its own from its own attested identity.
    """

    run_id: str
    correlation_id: str
    awaiting: str
    suspended_at: datetime
    step_index: int
    subject_user_id: str = ""
    tenant_id: str = ""
    agent_definition_id: str = ""


@dataclass
class SweepOutcome:
    """What one sweep did, so an operator can see it rather than infer it."""

    resumed: list[str] = field(default_factory=list)
    #: Rows whose checkpoint had moved on. Dropped rather than resumed.
    stale: list[str] = field(default_factory=list)
    #: Rows the sweeper could not act on, with why. Never silently skipped.
    failed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def acted(self) -> int:
        return len(self.resumed) + len(self.stale)


@dataclass
class Sweeper:
    """Resumes runs whose named dependency has recovered."""

    index: SuspendedRunIndex
    health: Callable[[str], HealthState]
    load_checkpoint: Callable[[str], Any]
    dispatch_resume: Callable[[SuspendedRunRecord], None]

    def sweep(self, products: list[str]) -> SweepOutcome:
        """Resume everything waiting on each recovered product.

        Products that are still unhealthy are skipped entirely rather than examined — the
        health checker owns that judgement, and a sweeper that second-guessed it would be
        the second opinion FR-006a exists to prevent.
        """
        outcome = SweepOutcome()
        for product in products:
            if not self.health(product).permits_calls():
                continue
            for record in self.index.awaiting(product):
                self._resume_one(record, outcome)
        return outcome

    def _resume_one(self, record: SuspendedRunRecord, outcome: SweepOutcome) -> None:
        # Re-read the checkpoint. The index is a candidate list, and a candidate whose
        # run has since completed must not be restarted — resuming a finished run is the
        # failure direction nobody would notice, because the run simply runs again.
        try:
            checkpoint = self.load_checkpoint(record.run_id)
        except Exception as exc:  # noqa: BLE001 — a failed candidate must not end the sweep
            outcome.failed.append((record.run_id, f"checkpoint unreadable: {exc}"))
            return

        if checkpoint is None:
            # Nothing to resume from, and nothing that will appear later. Drop it rather
            # than retrying forever against a record that cannot be acted on.
            self.index.forget(record.run_id)
            outcome.stale.append(record.run_id)
            return

        if not _is_suspended(checkpoint):
            # The checkpoint moved on — completed, stopped, or already resumed. The index
            # is behind, which is exactly what an index is allowed to be.
            self.index.forget(record.run_id)
            outcome.stale.append(record.run_id)
            return

        try:
            self.dispatch_resume(record)
        except Exception as exc:  # noqa: BLE001 — one failure must not strand the rest
            outcome.failed.append((record.run_id, f"dispatch failed: {exc}"))
            return

        # Forgotten only after a successful dispatch. Forgetting first would lose the run
        # if the dispatch failed — and a lost suspended run is indistinguishable from a
        # hang, which is the thing this mechanism exists to prevent.
        self.index.forget(record.run_id)
        outcome.resumed.append(record.run_id)


def _is_suspended(checkpoint: Any) -> bool:
    """Whether the authoritative record still says suspended."""
    outcome = getattr(checkpoint, "outcome", None)
    if outcome is not None:
        # A terminal outcome was written. Whatever the index says, this run is done.
        return False
    state = getattr(checkpoint, "run_state", None)
    return state is None or str(state) == RunState.SUSPENDED.value


def now() -> datetime:
    return datetime.now(UTC)


__all__ = ["SuspendedRunIndex", "SuspendedRunRecord", "SweepOutcome", "Sweeper"]
