# SPDX-License-Identifier: Apache-2.0
"""Suspending a run from the invoke path, without the core importing durability.

`suspend_run` lives in `core.durability.checkpoint` and needs a durability provider. The
authority hook has neither, and giving it one would put the whole durability seam on the
governance pipeline's import path — a coupling that would make the hook engine untestable
without a checkpoint store.

So this is a small indirection with one job: mark the run suspended and name what it waits
on, letting whoever owns the run's durability persist that on the next checkpoint.

**What the sweeper reads is the INDEX, verified against the checkpoint** — and this docstring
said "the state transition is what the sweeper reads" until 014, which is wrong in a way that
mattered. The sweeper queries `suspended_runs` for a product, then re-reads the checkpoint to
confirm the candidate is still suspended (`Sweeper._resume_one`). A state transition nothing
indexed is invisible to it: the run sits suspended forever, which is the hang ADR-0049 removed
a human to avoid, produced by the mechanism meant to prevent it.

That mattered because the sentence read as a complete account of the contract, and the caller
that suspends mid-run duly did the transition and nothing else — so `record_suspension` had no
caller anywhere in `src/` until 014, and the index was a store with a reader and no writer. A
docstring that understates the contract is how the next feature repeats this one; the writer
is `surfaces.dispatch.entrypoint`, in both of its suspension arms.
"""

from __future__ import annotations

from typing import Any

#: What a run waiting on identity resolution names as its dependency.
#:
#: A constant because the sweeper matches on it, and a string typed twice is a string that
#: will eventually be typed differently — leaving a run suspended on a dependency nothing
#: is watching, which is the hang ADR-0049 exists to prevent, produced by the mechanism
#: meant to prevent it.
TRUST_FABRIC_DEPENDENCY = "trust-fabric"


def suspend_for_dependency(run: Any, *, awaiting: str) -> None:
    """Mark a run suspended pending a named dependency.

    Deliberately tolerant of a run that cannot record it: a run object without the
    suspension fields is one from a caller that predates them, and failing here would turn
    "the trust fabric blinked" into "the process died", which is strictly worse for a
    condition that clears itself.
    """
    from core.run import RunState

    if not awaiting.strip():
        raise ValueError("a suspended run must name the dependency it awaits")
    try:
        run.state = RunState.SUSPENDED
        run.stop_reason = f"awaiting:{awaiting}"
    except Exception:  # noqa: BLE001 — see the docstring; refusing to suspend is worse
        return


__all__ = ["TRUST_FABRIC_DEPENDENCY", "suspend_for_dependency"]
