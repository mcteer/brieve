# SPDX-License-Identifier: Apache-2.0
"""Server-sent events: a delivery cadence for reads the catalogue already exposes.

**This adds no capability, and that claim is structural rather than asserted.** Every byte
emitted here comes from `get_run` and `get_run_result`, relayed with the requesting
person's own token. The stream computes nothing, decides nothing, and ends the moment the
API refuses — so a person watching a stream can see exactly what they could see by asking,
and nothing else.

Why this is not a `watch` operation on the catalogue: it would grow the operation set for
*cadence* rather than for capability, and bind parity across transports for something MCP
clients already do by polling. The line this feature holds is that the portal exposes no
capability the API does not — a page that refreshes itself is not a capability.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

#: 009's declared exemption from the no-blocking check, claimed here on the record.
#:
#: This module IS a service loop: it holds a connection open on purpose, for a bounded
#: time, so a person does not refresh. The check's own note says a marker is preferable to
#: narrowing the rule — narrowing is where coverage gets lost silently — so the claim is
#: made explicitly rather than by teaching the check that `asyncio.sleep` is fine.
#:
#: What the exemption is NOT covering: this loop `await`s rather than blocks, so it holds
#: no worker while it waits. If that ever becomes `time.sleep`, this marker would hide a
#: real defect — which is the cost of every exemption and the reason this one names the
#: distinction it relies on.
__service_loop__ = True

#: How often the portal asks the API for a run's state.
#:
#: Server-side, so a hundred open tabs are still one poll per run. Two seconds is chosen
#: for a person watching a page rather than for a machine: fast enough that a state change
#: feels immediate, slow enough that nothing here is a load source.
POLL_SECONDS = 2.0

#: How long one stream may live before the browser must reconnect.
#:
#: Bounded so an abandoned tab cannot hold a poll loop open indefinitely — the same
#: reasoning as the rate window, applied to reads.
MAX_STREAM_SECONDS = 300.0

#: Run states after which there is nothing further to report.
TERMINAL_STATES = frozenset({"completed", "failed", "stopped"})


def thread_event_stream(*, relay: Any, token: str, thread_id: str) -> StreamingResponse:
    """Stream state changes for a thread's runs until they finish or the budget expires."""
    return StreamingResponse(
        _events(relay=relay, token=token, thread_id=thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            # Without this, a reverse proxy may buffer the stream into uselessness.
            "X-Accel-Buffering": "no",
        },
    )


def propose_event_stream(*, relay: Any, token: str, run_id: str) -> StreamingResponse:
    """Stream run state + propose_progress for one Propose run (047). Cadence only."""
    return StreamingResponse(
        _propose_events(relay=relay, token=token, run_id=run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
        },
    )


async def _events(*, relay: Any, token: str, thread_id: str) -> AsyncIterator[str]:
    deadline = time.monotonic() + MAX_STREAM_SECONDS
    last: dict[str, str] = {}

    while time.monotonic() < deadline:
        detail = relay.request("GET", f"/threads/{thread_id}", token=token)
        if not detail.ok:
            # A refusal ends the stream, and says so. Narrowed authority mid-stream must
            # stop the flow of information immediately — a stream that kept emitting after
            # a 403 would be the one place the portal outlived a person's access.
            yield _frame("closed", {"reason": "refused", "status": detail.status})
            return

        run_ids = [t["run_id"] for t in (detail.payload or {}).get("turns", []) if t.get("run_id")]
        live = 0
        for run_id in run_ids:
            state = relay.request("GET", f"/runs/{run_id}", token=token)
            if not state.ok:
                yield _frame("closed", {"reason": "refused", "status": state.status})
                return
            current = str((state.payload or {}).get("state", ""))
            if current not in TERMINAL_STATES:
                live += 1
            if last.get(run_id) != current:
                last[run_id] = current
                yield _frame("run", {"run_id": run_id, "state": current})

        if live == 0:
            # Nothing left to watch. Closing beats holding a socket open to say nothing.
            yield _frame("closed", {"reason": "settled"})
            return
        # `asyncio.sleep`, never `time.sleep`. 009's guard forbids blocking primitives in
        # a surface module and is right to: a blocking sleep here holds a worker for the
        # stream's whole life, so a handful of open tabs would starve the server. This
        # yields to the event loop instead, which is what makes the wait free.
        await asyncio.sleep(POLL_SECONDS)

    yield _frame("closed", {"reason": "budget"})


def _access_ended(response: Any) -> bool:
    """A 401/403 ends the stream. A blip (5xx, unreachable, not-yet-indexed) does not."""
    return getattr(response, "status", 0) in {401, 403}


async def _propose_events(*, relay: Any, token: str, run_id: str) -> AsyncIterator[str]:
    deadline = time.monotonic() + MAX_STREAM_SECONDS
    last_state = ""
    last_progress = ""

    while time.monotonic() < deadline:
        state = relay.request("GET", f"/runs/{run_id}", token=token)
        if _access_ended(state):
            yield _frame("closed", {"reason": "refused", "status": state.status})
            return
        if not state.ok:
            # Keep the socket alive; the next poll may see the run. Closing here as
            # `refused` is what left the Build page silent after an API restart.
            yield ": keepalive\n\n"
            await asyncio.sleep(POLL_SECONDS)
            continue
        current = str((state.payload or {}).get("state", ""))
        result = relay.request("GET", f"/runs/{run_id}/result", token=token)
        if _access_ended(result):
            yield _frame("closed", {"reason": "refused", "status": result.status})
            return
        progress = None
        pr_url: str | None = None
        ended_reason: str | None = None
        if result.ok and isinstance(result.payload, dict):
            body = result.payload.get("result")
            if isinstance(body, dict):
                progress = body.get("propose_progress")
                raw_pr = body.get("pr_url")
                pr_url = str(raw_pr) if raw_pr else None
                if not pr_url:
                    ended_reason = str(body.get("reason") or "") or None
            if progress is None:
                progress = result.payload.get("propose_progress")
            if not ended_reason:
                ended_reason = str(result.payload.get("stop_reason") or "") or None
        progress_key = json.dumps(
            {"progress": progress, "pr_url": pr_url, "ended_reason": ended_reason},
            sort_keys=True,
        )
        if current != last_state or progress_key != last_progress:
            last_state = current
            last_progress = progress_key
            payload: dict[str, Any] = {"run_id": run_id, "state": current}
            if progress is not None:
                payload["propose_progress"] = progress
            if pr_url:
                payload["pr_url"] = pr_url
            if ended_reason and not pr_url:
                payload["ended_reason"] = ended_reason
            elif current in TERMINAL_STATES and not pr_url:
                payload["ended_reason"] = ended_reason or "Ended without a pull request."
            yield _frame("run", payload)
        else:
            # Comment frame: EventSource ignores it, proxies and browsers do not
            # treat the socket as idle during a long model step.
            yield ": keepalive\n\n"
        if current in TERMINAL_STATES:
            yield _frame("closed", {"reason": "settled"})
            return
        await asyncio.sleep(POLL_SECONDS)

    yield _frame("closed", {"reason": "budget"})


def _frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


__all__ = [
    "MAX_STREAM_SECONDS",
    "POLL_SECONDS",
    "TERMINAL_STATES",
    "propose_event_stream",
    "thread_event_stream",
]
