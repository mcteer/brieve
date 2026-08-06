# SPDX-License-Identifier: Apache-2.0
"""Intent/result bracket around steps whose effects are not naturally repeatable.

An intent is written before the effect and a result after, so an interruption between
them is *resolvable* — the pair is what turns "we do not know" into "ask the observer".

ADR-0026 puts the implementation difficulty of durable execution here, and getting it
wrong produces exactly the duplicate side effects the bracket exists to prevent. Every
future non-repeatable tool inherits this; it is an ongoing obligation, not a one-time
pass.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from core.authority.clock import Clock
from core.durability.types import DurabilityProvider, IntentRecord, ResultRecord
from core.observation.types import Observation, ObservationOutcome, Observer


def bracket_call[T](
    provider: DurabilityProvider,
    *,
    run_id: str,
    step_index: int,
    tool_name: str,
    idempotency_key: str,
    clock: Clock,
    call: Callable[[], T],
    arguments: Mapping[str, Any] | None = None,
) -> T:
    """Record intent, perform the effect, record result.

    The intent write is *not* wrapped in a try: if it fails the effect must not happen,
    because an unrecorded effect is indistinguishable on resume from one that never
    ran. The result write is likewise allowed to propagate — a missing result leaves an
    open intent, which resume resolves by observation, so failing loudly costs less
    than pretending.

    ``arguments`` is what the call will be made with (040). It travels into the intent so a
    revival re-invokes the **same act** rather than an emptier one: once the arguments come
    from a model rather than from a platform constant, "we were about to run X" is not
    enough to repeat X. Defaulted so every pre-040 construction site is unchanged — and,
    exactly as with ``resume_count``, the default is the trap: a caller that knows its
    arguments and lets this default writes a post-040 record on the pre-040 side of the
    NULL-means-legacy line.
    """
    provider.record_intent(
        IntentRecord(
            run_id=run_id,
            step_index=step_index,
            tool_name=tool_name,
            idempotency_key=idempotency_key,
            arguments=None if arguments is None else dict(arguments),
            recorded_at=clock.now(),
        )
    )
    result = call()
    provider.record_result(
        ResultRecord(
            run_id=run_id,
            step_index=step_index,
            idempotency_key=idempotency_key,
            recorded_at=clock.now(),
        )
    )
    return result


def resolve_open_intents(
    provider: DurabilityProvider,
    *,
    run_id: str,
    observers: dict[str, Observer],
    clock: Clock,
) -> list[tuple[IntentRecord, Observation]]:
    """Ask, for each interrupted step, what actually happened.

    Returns the observations rather than acting on them: the caller decides whether to
    skip, redo, or park, and keeping that decision out of here means the resolution is
    visible in the resume path instead of buried in a helper.

    A tool with no registered observer resolves to ``CANNOT_DETERMINE``. That is the
    honest answer — not having a way to look is not evidence of anything — and it parks
    the run rather than guessing.
    """
    resolved: list[tuple[IntentRecord, Observation]] = []
    for intent in provider.open_intents(run_id):
        observer = observers.get(intent.tool_name)
        if observer is None:
            observation = Observation(
                outcome=ObservationOutcome.CANNOT_DETERMINE,
                detail=f"no observer registered for tool {intent.tool_name!r}",
            )
        else:
            try:
                observation = observer.observe(idempotency_key=intent.idempotency_key)
            except Exception as exc:  # noqa: BLE001 — an unreachable system is not evidence
                observation = Observation(
                    outcome=ObservationOutcome.CANNOT_DETERMINE,
                    detail=f"observation failed: {type(exc).__name__}",
                )
        resolved.append((intent, observation))
        if observation.outcome is ObservationOutcome.HAPPENED:
            # Close the bracket so a later resume does not re-observe a settled step.
            provider.record_result(
                ResultRecord(
                    run_id=intent.run_id,
                    step_index=intent.step_index,
                    idempotency_key=intent.idempotency_key,
                    recorded_at=clock.now(),
                )
            )
    return resolved


__all__ = ["bracket_call", "resolve_open_intents"]
