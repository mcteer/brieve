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


def _frame(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


__all__ = ["MAX_STREAM_SECONDS", "POLL_SECONDS", "TERMINAL_STATES", "thread_event_stream"]
