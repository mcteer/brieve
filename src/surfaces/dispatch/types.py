# SPDX-License-Identifier: Apache-2.0
"""The run dispatch seam.

Starting a run returns a handle rather than blocking. Runs are durable and long by design
(005), so an API that held a connection open for a run's duration would contradict the
feature that exists to let work outlive a process.

The seam is what keeps Principle VII true at the layer a customer touches first. Under the
enclave a run is a Nomad allocation; the surface does not know that, and must not — "the
substrate is the only permitted delta" cannot hold if the surface names the substrate.
Same shape ADR-0024 established for durability, for the same reason.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from core.run import RunState


class RunHandle(BaseModel):
    """What starting a run returns.

    Deliberately absent: anything naming an allocation, a container, or a scheduler. The
    caller must not learn the substrate any more than the surface does.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    correlation_id: str
    state: RunState


class RunDispatcher(Protocol):
    """Starts runs and reports their state. Never executes one inline."""

    def dispatch(
        self,
        *,
        correlation_id: str,
        subject_user_id: str,
        tenant_id: str,
        agent_definition_id: str,
        requested_tools: frozenset[str],
        run_id: str | None = None,
        step_index: int | None = None,
        subject_roles: frozenset[str] = frozenset(),
        steps: int | None = None,
        packs: frozenset[str] = frozenset(),
        invoke_tools: bool = False,
        resume: bool = False,
    ) -> RunHandle:
        """Start a run and return immediately with a handle.

        ``run_id`` and ``step_index`` are **resume state, and optional**. A resumed run
        keeps its identity and picks up where it stopped; a fresh one supplies neither.
        ``resume`` says which of those two this dispatch is: it is declared here rather than
        inferred downstream, because the dispatcher is the only party that knows (014, D1).

        Optional is not a style choice. 008's ``POST /runs`` calls this with exactly five
        keyword arguments, so required parameters would stop the API route compiling —
        which is the rule this feature adopted after finding the same shape three times:
        **optional-by-default wherever a prior caller exists.**

        **``steps``, ``packs``, and ``invoke_tools`` are catch-up rather than new.** They
        have been on ``NomadDispatcher.dispatch()`` since 010 and 013 and have travelled to
        the jobspec ever since, but they were never added *here* — so the seam described
        less than every implementation of it did. Nothing caught the drift because the only
        consumer typed against this protocol, the sweeper's resume dispatch, happened to
        pass just the subset the protocol knew. 014 needed all of them (a resumed run
        without its packs re-suspends on every pack tool; without its steps it completes
        trivially), and the type checker found the gap the moment a caller wanted the whole
        set. Recorded because the shape recurs: a seam stays honest only while something
        type-checks against it.
        """
        ...

    def state_of(self, run_id: str) -> RunHandle | None:
        """Return the run's current handle, or None if no such run exists."""
        ...


__all__ = ["RunDispatcher", "RunHandle"]
