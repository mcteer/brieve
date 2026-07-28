# SPDX-License-Identifier: Apache-2.0
"""Refuse a tool call against a dependency the platform knows is unreachable.

**A hook inside the governed pipeline, not a pre-flight before it.** That placement is the
whole design and it is easy to get wrong in a way that works: checking before the pipeline
is cheaper, skips machinery for a call that will be refused anyway, and is a second
refusal path — which is a second authorization path wearing a practical-sounding name
(Principle II). It would also leave a run started through some later transport ignoring a
dependency the platform knows is down.

So the conformance row asserts *placement*, not only behaviour. Otherwise the first person
optimising a hot path moves it and nothing notices.

**No intent record is written.** Attempting a call against a dead dependency writes an
intent that must later be resolved by re-observation — against the same dead dependency.
The bracket that exists to make interrupted steps resolvable becomes the thing that cannot
be resolved, so refusing before execution is not an optimisation but the point.
"""

from __future__ import annotations

from typing import Any

from core.dependencies.types import DenialClass, HealthState
from core.hooks.types import HookContext, HookDecision

DEPENDENCY_HOOK_NAME = "dependency"

#: Reason code for an availability refusal. Distinct from every policy reason code, and
#: the distinction reaches the model rather than only the trail (ADR-0049).
DEPENDENCY_UNAVAILABLE = "dependency_unavailable"


def dependency_pre_hook(ctx: HookContext) -> HookDecision:
    """Deny before execution when the tool's product is not reachable."""
    run = ctx.run
    if run is None:
        return HookDecision(
            outcome="deny",
            reason_code="internal_error",
            message="dependency gate missing run context",
        )

    reader = getattr(run, "dependency_health", None)
    if reader is None:
        # INERT, not failing closed. A run with no dependency mechanism configured is not
        # a run whose dependencies are all unknown — those are different claims, and
        # collapsing them would make every 002-era run refuse every tool call while
        # looking exactly like the gate working.
        return HookDecision(
            outcome="allow",
            reason_code="ok",
            message="no dependency health configured",
        )

    product = _product_of(run, ctx.tool_name)
    if product is None:
        # A tool that reaches no product has no dependency to be down.
        return HookDecision(outcome="allow", reason_code="ok", message="no product")

    state = reader.state_of(product)
    if state.permits_calls():
        return HookDecision(outcome="allow", reason_code="ok", message="dependency healthy")

    # UNKNOWN lands here too, deliberately: guessing reachable is how a dead dependency
    # gets called anyway.
    return HookDecision(
        outcome="deny",
        reason_code=DEPENDENCY_UNAVAILABLE,
        message=_refusal_message(product, state),
    )


def _product_of(run: Any, tool_name: str) -> str | None:
    """Which product this tool reaches, per the registry the run already holds."""
    try:
        registration = run.registry.resolve(tool_name)
    except Exception:
        return None
    product = getattr(registration, "product", None)
    return str(product) if product else None


def _refusal_message(product: str, state: HealthState) -> str:
    """What the agent is told, and it is told deliberately.

    This is the **availability** class, the only one that is model-visible (ADR-0049). It
    names the product and invites a legitimate alternative — write the plan, hand it back
    — rather than implying the call should be retried or routed around.

    A policy denial says none of this. An agent taught that refusals are adaptable will
    look for another route, which is the one behaviour the governance layer exists to
    prevent, and nothing would break visibly while it learned that.
    """
    return (
        f"{product} is not reachable ({state.value}). This is an availability limit, not a "
        f"permission one: complete what does not require {product} and report what was not "
        f"attempted, rather than retrying or seeking another route."
    )


def denial_class_for(reason_code: str) -> DenialClass:
    """Which kind of "no" a reason code represents.

    One function so the two classes cannot drift apart in three places, which is how a
    scope denial eventually starts looking adaptable.
    """
    return DenialClass.AVAILABILITY if reason_code == DEPENDENCY_UNAVAILABLE else DenialClass.POLICY


__all__ = [
    "DEPENDENCY_HOOK_NAME",
    "DEPENDENCY_UNAVAILABLE",
    "denial_class_for",
    "dependency_pre_hook",
]
