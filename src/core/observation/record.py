# SPDX-License-Identifier: Apache-2.0
"""Asking each effect's observer before a run ends, and recording what it said.

**This is 021's Constitution Check, in code.** The first design had a report re-read product
state at request time; `Observer.observe` takes no credential and reads under *ambient* identity,
so at report time that would have been the API surface's — handing a reader an observation they
may hold no authority to make. An agent never exceeds its human; a report must not exceed its
reader.

So the read-back happens **here**, inside the allocation, under the attested identity it already
holds and bounded by the run's own ceiling. The report compiles the answer like any other record
and performs no observation of its own.

**Recording an observation never changes the run's outcome.** A run that did its work and then
found an effect missing completed and produced a *finding*; letting the observation retroactively
fail the run would give a reporting mechanism power over what it reports.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.audit.schema import AuditEventType
from core.observation.types import Observation, ObservationOutcome


def observe_effects(
    run: Any,
    *,
    observers: Mapping[str, Any],
    executed: Mapping[int, str],
    run_id: str,
) -> list[Observation]:
    """Ask each executed effect's observer whether it landed, and record every answer.

    ``executed`` maps step index → tool name for the effects this allocation actually ran. A step
    with no registered observer is skipped **silently here and loudly in the report**: the report
    renders it `unverified_no_observer`, which is a fact about the tool's registration rather
    than about the product, and inventing an observer to fill the gap would turn an honest
    `unverified` into a false `confirmed`.

    **Never raises.** An observer that throws is `CANNOT_DETERMINE` — the protocol says so, and
    the resume path already reads it that way. A run must not fail because a report would have
    liked more evidence, which is the same reasoning that keeps this off the run's outcome.
    """
    recorded: list[Observation] = []
    for step_index, tool in sorted(executed.items()):
        observer = observers.get(tool)
        if observer is None:
            continue

        key = f"{run_id}:{step_index}:{tool}"
        try:
            observation = observer.observe(idempotency_key=key)
        except Exception as exc:  # noqa: BLE001 — unreachable is CANNOT_DETERMINE, never "no"
            observation = Observation(
                outcome=ObservationOutcome.CANNOT_DETERMINE,
                detail=f"observer raised {type(exc).__name__}",
            )

        _record(
            run, run_id=run_id, step_index=step_index, tool=tool, key=key, observation=observation
        )
        recorded.append(observation)
    return recorded


def _record(
    run: Any,
    *,
    run_id: str,
    step_index: int,
    tool: str,
    key: str,
    observation: Observation,
) -> None:
    """Write the observation onto the run's own trail.

    **Not swallowed.** An observation that could not be recorded is one no report can compile,
    and a report would then render the effect `unverified_not_observed` — reporting a run that
    *did* observe as one that never got to. That is a false statement about the platform's own
    behaviour, so the append is allowed to fail the step rather than be best-effort.
    """
    run.audit_sink.append_event(
        correlation_id=run.correlation_id,
        tenant_id=run.tenant_id,
        event_type=AuditEventType.EFFECT_OBSERVED,
        payload={
            "run_id": run_id,
            "step_index": step_index,
            "tool": tool,
            "idempotency_key": key,
            "outcome": str(observation.outcome),
            # The observer's own words about the basis. Bounded and non-secret by the same
            # posture every other payload holds: references and reasons, never values.
            "detail": observation.detail,
        },
    )


__all__ = ["observe_effects"]
