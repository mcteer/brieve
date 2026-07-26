# SPDX-License-Identifier: Apache-2.0
"""Sole public entry that executes tool bodies through the hook pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from core.hooks.engine import run_pipeline
from core.run import GovernedRun


class InvokeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    allowed: bool
    decision: Literal["allow", "deny"]
    reason_code: str
    message: str
    correlation_id: str
    executed: bool
    evidential_gap: bool = False
    tool_result: Any = None


def invoke_tool(
    run: GovernedRun,
    tool_name: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    idempotency_key: str | None = None,
) -> InvokeResult:
    """Invoke a tool through the fail-closed pre/post hook pipeline.

    There is no supported path to run a tool handler while skipping pre-hooks.

    Durability concerns attach **here**, on the one governed path, rather than in a
    second wrapper (Principle II). Three of them, in order, each fail-closed:

    1. **Lease.** A superseded holder is rejected before anything executes. Doing this
       first means a zombie cannot produce a side effect while we decide.
    2. **Bounds.** Checked where the run advances, not by a background timer whose
       failure would silently unbound the run.
    3. **Bracket.** A non-repeatable tool is wrapped in intent/result records, so an
       interruption mid-call is resolvable by observation rather than by guessing.
    """
    args: Mapping[str, Any] = arguments if arguments is not None else {}

    if run.lease is not None:
        # Raises LeaseSupersededError — deliberately not converted to a deny, because a
        # zombie's caller needs to stop, not to read a refusal and try the next tool.
        run.lease.assert_held(correlation_id=run.correlation_id)

    if run.bounds is not None:
        run.bounds.check(run.clock, correlation_id=run.correlation_id)

    outcome = run_pipeline(run, tool_name, args)
    if run.bounds is not None and outcome.decision == "allow":
        run.bounds.record_progress(run.clock.now())

    allowed = outcome.decision == "allow" and not outcome.evidential_gap
    return InvokeResult(
        allowed=allowed,
        decision=outcome.decision,  # type: ignore[arg-type]
        reason_code=outcome.reason_code,
        message=outcome.message,
        correlation_id=run.correlation_id,
        executed=outcome.executed,
        evidential_gap=outcome.evidential_gap,
        tool_result=outcome.tool_result,
    )
