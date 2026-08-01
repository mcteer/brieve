# SPDX-License-Identifier: Apache-2.0
"""The real dispatcher: a run is a Nomad allocation.

Not optional, and not replaceable by the in-process double for anything that matters.
Nomad is inside our boundary — we deploy it — so a run-start path exercised only against a
fake has not been exercised. That is the same rule that put the durability rows on real
Postgres.

**Nothing above this module knows Nomad exists.** The surface depends on
:class:`~surfaces.dispatch.types.RunDispatcher`; this is one implementation of it, and a
Kubernetes one would be another. Principle VII's "the substrate is the only permitted
delta" cannot hold if the layer a customer touches first names the scheduler.

Why an allocation rather than a thread: 005 made a run's identity structural. Resume is a
*new* allocation with a *new* attested workload identity, which is what makes replaying a
pre-disruption credential unavailable rather than merely forbidden. A dispatcher that ran
work in the API's own process would put the run's lifetime inside the surface's, and the
feature that exists to let work outlive a process would be the thing preventing it.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from core.errors import CoreError
from core.run import RunState
from core.runs.index import InMemoryRunIndex, RunIndex, RunIndexEntry
from surfaces.dispatch.types import RunHandle

DEFAULT_NOMAD_ADDR = "http://127.0.0.1:4646"
DEFAULT_JOB_ID = "agent-run"


class DispatchError(CoreError):
    """The run could not be scheduled. Never swallowed — an unscheduled run is not a run."""


#: Nomad allocation client states mapped onto run states.
#:
#: ``pending`` is deliberately ACTIVE rather than a state of its own. A caller polling a
#: handle cares whether the run is still going, and inventing a surface-only "scheduling"
#: state would leak exactly the substrate detail this seam exists to hide.
_STATE_BY_CLIENT_STATUS = {
    "pending": RunState.ACTIVE,
    "running": RunState.ACTIVE,
    "complete": RunState.COMPLETED,
    "failed": RunState.STOPPED,
    "lost": RunState.STOPPED,
}


class NomadDispatcher:
    """Submits a parameterized job dispatch per run."""

    def __init__(
        self,
        *,
        nomad_addr: str = DEFAULT_NOMAD_ADDR,
        job_id: str = DEFAULT_JOB_ID,
        timeout: float = 10.0,
        run_index: RunIndex | None = None,
    ) -> None:
        self._addr = nomad_addr.rstrip("/")
        self._job_id = job_id
        self._timeout = timeout
        # A real deployment passes the Postgres index; the default keeps every existing
        # caller — including the rows that only prove dispatch — compiling and hermetic.
        self._index: RunIndex = run_index if run_index is not None else InMemoryRunIndex()
        self._dispatched: dict[str, str] = {}

    def _request(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self._addr}/v1/{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(  # noqa: S310 — fixed scheme, operator-supplied addr
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:  # noqa: S310
                body = response.read().decode()
        except urllib.error.HTTPError as exc:
            raise DispatchError(f"scheduler refused {path}: {exc.code} {exc.reason}") from exc
        except OSError as exc:
            raise DispatchError(f"scheduler unreachable at {self._addr}: {exc}") from exc
        return json.loads(body) if body else {}

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
        choice_recording: str = "",
    ) -> RunHandle:
        """Schedule the run and return immediately.

        Metadata carries identity and scope; **no credential is passed**. The allocation
        presents its own workload identity to Vault and receives a ceiling-scoped token,
        which is the whole point of ADR-0048's attestation path. A dispatcher that handed
        the job a token would put a static credential in a jobspec — the single thing this
        architecture is built to avoid.
        """
        # Resume state travels as metadata, like everything else the job is told. A
        # resumed allocation still manufactures its own credentials — knowing WHICH run it
        # is resuming grants it nothing.
        payload = {
            "Meta": {
                "correlation_id": correlation_id,
                "subject_user_id": subject_user_id,
                "tenant_id": tenant_id,
                "agent_definition_id": agent_definition_id,
                "requested_tools": ",".join(sorted(requested_tools)),
                # What the surface established about who is asking. Still metadata: the
                # run resolves what these roles MEAN from the trust fabric, so a
                # dispatcher cannot grant authority by writing a scope into a jobspec.
                "subject_roles": ",".join(sorted(subject_roles)),
                # Absent unless asked for. A run given neither behaves exactly as before.
                "steps": str(steps) if steps is not None else "",
                # 013. Empty means none, which is every pre-013 dispatch unchanged.
                "packs": ",".join(sorted(packs)),
                "invoke_tools": "1" if invoke_tools else "",
                # 014, D1: a resume is DECLARED, never inferred.
                #
                # The entrypoint takes the resume path if and only if this is set, and the
                # sweeper's resume dispatch is the only caller that sets it. The
                # alternatives were both worse in the same way — they turn a coincidence
                # into a resume. Inferring from `step_index > 0` misses a run interrupted at
                # step zero; inferring from "a checkpoint exists for this run_id" turns an
                # id collision into a silent resume, which is precisely what the
                # `meta_required` comment in the jobspec warns about for `run_id` itself.
                #
                # The dispatcher KNOWS whether it is resuming, so the knowledge travels as
                # data rather than being reconstructed downstream from evidence that is
                # consistent with two different histories.
                "resume": "1" if resume else "",
                # 020. The answers a `fixture/...` model replays instead of calling a
                # provider, so the merge lane's dispatched rows need no vendor (FR-011).
                #
                # **It grants nothing on its own**, which is the property that keeps this
                # from being a scripted sequence reachable in production. The branch that
                # reads it is chosen by the MATRIX — a cell whose model names the `fixture`
                # provider — so a recording travelling beside an `anthropic/...` binding is
                # ignored entirely. Two operator-authored records have to say so before any
                # of this is reachable, which is the difference between a stand-in and the
                # `_tool_for_step` fallback FR-002 removed.
                "choice_recording": choice_recording,
                "run_id": run_id or correlation_id,
                "step_index": str(step_index if step_index is not None else 0),
            },
        }
        result = self._request(f"job/{self._job_id}/dispatch", payload)
        dispatched_id = str(result.get("DispatchedJobID", "") or "")
        if not dispatched_id:
            raise DispatchError("scheduler accepted the dispatch but named no job")

        self._dispatched[run_id or correlation_id] = dispatched_id

        # Indexed AFTER the scheduler accepted it, and the ordering is a choice between
        # two imperfect failures. Recording first would leave a phantom entry for every
        # REFUSED dispatch — systematic, and a list of runs that never existed. Recording
        # after leaves a real run unlisted only if this process dies in the window between
        # acceptance and insert — rare, self-limiting, and visible in the audit trail,
        # which is what the divergence row watches for.
        #
        # 009 avoided the choice entirely by writing `suspended_runs` and the checkpoint in
        # one transaction. That is unavailable here: the scheduler and the index are
        # different stores, and no transaction spans them.
        self._index.record(
            RunIndexEntry(
                run_id=run_id or correlation_id,
                correlation_id=correlation_id,
                subject_user_id=subject_user_id,
                tenant_id=tenant_id,
                agent_definition_id=agent_definition_id,
                created_at=datetime.now(UTC),
            )
        )
        return RunHandle(
            run_id=run_id or correlation_id,
            correlation_id=correlation_id,
            state=RunState.ACTIVE,
        )

    def dispatched_job_id(self, run_id: str) -> str | None:
        """The scheduler's id for this run's dispatch, if this dispatcher started it.

        Substrate detail, deliberately **not** on :class:`RunHandle` — a caller who can see
        it has learned the scheduler. Exposed here for operators and for the conformance
        row, both of which are already inside the substrate boundary.
        """
        return self._dispatched.get(run_id)

    def state_of(self, run_id: str) -> RunHandle | None:
        dispatched_id = self._dispatched.get(run_id)
        if dispatched_id is None:
            return None
        allocations = self._request(f"job/{dispatched_id}/allocations")
        if not isinstance(allocations, list) or not allocations:
            # Dispatched but not yet placed. Still active — reporting "unknown" here would
            # make a normal scheduling delay look like a failure to a polling caller.
            return RunHandle(run_id=run_id, correlation_id=run_id, state=RunState.ACTIVE)
        latest = max(allocations, key=lambda a: int(a.get("CreateIndex", 0)))
        status = str(latest.get("ClientStatus", "")).lower()
        return RunHandle(
            run_id=run_id,
            correlation_id=run_id,
            state=_STATE_BY_CLIENT_STATUS.get(status, RunState.ACTIVE),
        )


__all__ = ["DispatchError", "NomadDispatcher"]
