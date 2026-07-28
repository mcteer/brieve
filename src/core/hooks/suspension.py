# SPDX-License-Identifier: Apache-2.0
"""Suspending a run from the invoke path, without the core importing durability.

`suspend_run` lives in `core.durability.checkpoint` and needs a durability provider. The
authority hook has neither, and giving it one would put the whole durability seam on the
governance pipeline's import path — a coupling that would make the hook engine untestable
without a checkpoint store.

So this is a small indirection with one job: mark the run suspended and name what it waits
on, letting whoever owns the run's durability persist that on the next checkpoint. The
state transition is what the sweeper reads; the checkpoint write is what makes it durable,
and the two happen in different places because they always have.
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
