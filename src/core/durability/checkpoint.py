# SPDX-License-Identifier: Apache-2.0
"""Writing run state, and marking a run finished or stopped.

Kept beside the provider rather than inside it: *what* gets recorded is a harness
guarantee (FR-012), and a provider that could choose the shape could choose whether
terminal state is recorded at all.
"""

from __future__ import annotations

from typing import Any

from core.durability.types import CheckpointBlob, DurabilityProvider, RunOutcome
from core.run import GovernedRun, RunState


def checkpoint_run(
    run: GovernedRun,
    *,
    payload: dict[str, Any] | None = None,
    outcome: RunOutcome | None = None,
) -> CheckpointBlob | None:
    """Persist the run's resume point.

    The lease is checked first: a superseded holder must not overwrite the state of the
    instance that replaced it (FR-009). Write failures propagate — a step that proceeds
    as though it were recorded is indistinguishable on resume from one that never ran,
    which is precisely the ambiguity re-observation exists to remove.
    """
    provider: DurabilityProvider | None = run.durability
    if provider is None:
        return None
    if run.lease is not None:
        run.lease.assert_held(correlation_id=run.correlation_id)

    blob_id = run.run_id or run.correlation_id
    if payload is None:
        # A state transition must not erase progress. Parking a run and losing the work
        # it had done would be the worst possible reading of "waiting, not failed".
        existing = provider.load(blob_id)
        payload = dict(existing.payload) if existing is not None else {}

    blob = CheckpointBlob(
        blob_id=blob_id,
        payload=dict(payload),
        correlation_id=run.correlation_id,
        grant_id=run.grant.grant_id if run.grant else "",
        step_index=run.step_index,
        written_by=run.lease.holder_identity if run.lease else "",
        outcome=outcome,
    )
    provider.save(blob)
    return blob


def complete_run(run: GovernedRun, *, payload: dict[str, Any] | None = None) -> None:
    """Mark the run finished, in memory and in the store.

    Both, not either: the in-memory state is what this process acts on, and the stored
    state is all a resuming process will see. Recording only one leaves a finished run
    that a later resume re-enters.
    """
    run.state = RunState.COMPLETED
    checkpoint_run(run, payload=payload, outcome=RunOutcome(state=RunState.COMPLETED.value))


def stop_run(run: GovernedRun, *, reason: str, payload: dict[str, Any] | None = None) -> None:
    """Halt the run at a bound, recording which one (FR-011, SC-007)."""
    run.state = RunState.STOPPED
    run.stop_reason = reason
    checkpoint_run(
        run,
        payload=payload,
        outcome=RunOutcome(state=RunState.STOPPED.value, stop_reason=reason),
    )


def park_run(run: GovernedRun, *, reason: str, payload: dict[str, Any] | None = None) -> None:
    """Suspend the run awaiting a human.

    Parked is *not* written as a terminal outcome: the run must stay resumable once the
    blocking condition clears, and marking it terminal would make resume refuse it.
    """
    run.state = RunState.PARKED
    run.stop_reason = reason
    checkpoint_run(run, payload=payload, outcome=None)
