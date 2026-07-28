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


def stop_requested(run: GovernedRun) -> str | None:
    """Whether someone has ended this run, read from the durable record.

    **Called at the step boundary** — after the in-flight step's result is bracketed and
    before the next intent is written — which is where C3's semantics come from. The
    placement *is* the guarantee: a step already begun completes and records its result, no
    further step starts, and no intent is left open. Nothing here enforces that by timeout,
    because a timeout would produce exactly the open intent this ordering avoids.

    A terminal run never resumes, so an intent open at stop time could never be
    re-observed — it would be permanent, which is the single outcome 005's bracketing
    exists to prevent. That is why the stop waits for the bracket rather than the reverse.

    Returns the stop reason, or ``None`` when the run should continue. A read that fails
    returns ``None`` too: the run carries on, which is right, because a database blip must
    not end work nobody asked to end. The stop is durable and will be seen at the next
    boundary.
    """
    provider: DurabilityProvider | None = run.durability
    if provider is None:
        return None
    try:
        blob = provider.load(run.run_id or run.correlation_id)
    except Exception:  # noqa: BLE001 — an unreadable record must not end a healthy run
        return None
    if blob is None or blob.outcome is None:
        return None
    if blob.outcome.state != RunState.STOPPED.value:
        return None
    return blob.outcome.stop_reason or "stopped"


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


def suspend_run(run: GovernedRun, *, awaiting: str, payload: dict[str, Any] | None = None) -> None:
    """Suspend the run pending a named dependency.

    Not written as a terminal outcome: the run must stay resumable once the dependency
    recovers, and marking it terminal would make resume refuse it.

    ``awaiting`` is required and is the whole difference from the ``park_run`` this
    replaced. A run that suspends without naming what it waits on is a run the sweeper
    cannot find work for — it would sit suspended forever, which is exactly the hang
    ADR-0049 exists to prevent, produced by the mechanism meant to prevent it.
    """
    if not awaiting.strip():
        raise ValueError("a suspended run must name the dependency it awaits")
    run.state = RunState.SUSPENDED
    run.stop_reason = f"awaiting:{awaiting}"
    checkpoint_run(run, payload=payload, outcome=None)
