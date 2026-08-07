# SPDX-License-Identifier: Apache-2.0
"""Governance pre-hook: expiry + live_effective tool/product_action bounds."""

from __future__ import annotations

from typing import Any

from core.audit.schema import AuditEventType
from core.authority.errors import AuditAppendFailed
from core.authority.intersection import (
    OUTSIDE_CEILING,
    OUTSIDE_POLICY,
    OUTSIDE_TASK_SCOPE,
    OUTSIDE_USER_SCOPE,
    live_effective,
)
from core.hooks.suspension import TRUST_FABRIC_DEPENDENCY, suspend_for_dependency
from core.hooks.types import HookContext, HookDecision

AUTHORITY_HOOK_NAME = "authority"

#: What each refusal means, phrased as the thing to go and look at. The reason code is for a
#: machine; this is for the person the code sent somewhere.
_DENIAL_MESSAGES = {
    OUTSIDE_USER_SCOPE: "tool outside the subject's own authority; an agent never exceeds a human",
    OUTSIDE_CEILING: "tool outside the definition's ceiling; the ceiling record decides this",
    OUTSIDE_TASK_SCOPE: "tool inside the ceiling but not requested by this run's task scope",
    OUTSIDE_POLICY: "tool narrowed by live policy after authority was issued",
}


def _append(run: Any, event_type: AuditEventType, payload: dict[str, Any]) -> None:
    sink = run.audit_sink
    cid = run.correlation_id
    try:
        sink.append_event(
            correlation_id=cid,
            tenant_id=run.tenant_id,
            event_type=event_type,
            payload=payload,
        )
    except Exception as exc:
        raise AuditAppendFailed(
            f"authority audit append failed: {type(exc).__name__}",
            correlation_id=cid,
        ) from exc


def authority_pre_hook(ctx: HookContext) -> HookDecision:
    """Deny on expiry or outside live_effective; allow otherwise."""
    run = ctx.run
    if run is None:
        return HookDecision(
            outcome="deny",
            reason_code="internal_error",
            message="authority hook missing run context",
        )

    authority = getattr(run, "authority", None)
    clock = getattr(run, "clock", None)
    fabric = getattr(run, "identity_fabric", None)
    if authority is None or clock is None or fabric is None:
        return HookDecision(
            outcome="deny",
            reason_code="internal_error",
            message="authority dependencies unavailable",
        )

    try:
        now = clock.now()
        if now >= authority.expires_at:
            _append(
                run,
                AuditEventType.AUTHORITY_EXPIRED,
                {"reason_code": "authority_expired", "tool_name": ctx.tool_name},
            )
            return HookDecision(
                outcome="deny",
                reason_code="authority_expired",
                message="task authority expired",
            )

        try:
            policy = fabric.resolve_policy(run.agent_definition_id)
        except Exception as exc:  # noqa: BLE001 — an unresolvable policy must never permit
            code = getattr(exc, "reason_code", "identity_unavailable")
            if code in {"fabric_unreachable", "fabric_timeout"}:
                # The trust fabric is unreachable and this run already holds a grant, so
                # there is something to come back to. **Suspend naming it** rather than
                # denying the step (FR-008a): a denial would end the run's work on a
                # transient outage that a product outage would have survived, and ADR-0049
                # is explicit that a run may wait on a machine condition.
                #
                # The asymmetry with run START is not a special case — a run that cannot
                # resolve identity before it begins has no grant and no checkpoint, so
                # there is nothing to suspend. It falls out of the run existing or not.
                suspend_for_dependency(run, awaiting=TRUST_FABRIC_DEPENDENCY)
                return HookDecision(
                    outcome="deny",
                    reason_code=code,
                    message="trust fabric unreachable; run suspended awaiting it",
                )
            return HookDecision(
                outcome="deny",
                reason_code="identity_unavailable",
                message="policy resolution failed",
            )

        effective = live_effective(authority.effective, policy)
        # stash for mirroring / tests
        run.live_effective = effective

        if ctx.tool_name not in effective.tool_names:
            # WHICH bound excluded it, when manufacture could tell (041, FR-019). An operator
            # reading `authority_insufficient` learns only that something said no; the four
            # specific codes each name a different record to go and read. Falls back to the
            # umbrella when the map is silent — a run whose authority was supplied rather than
            # manufactured has no terms to have compared, and guessing a specific bound would
            # be worse than declining to name one.
            excluded = run.authority_exclusions.get(ctx.tool_name)
            reason = excluded or "authority_insufficient"
            _append(
                run,
                AuditEventType.AUTHORITY_DENIED,
                {
                    "reason_code": reason,
                    "tool_name": ctx.tool_name,
                },
            )
            return HookDecision(
                outcome="deny",
                reason_code=reason,
                message=_DENIAL_MESSAGES.get(reason, "tool outside live effective authority"),
            )

        registration = run.registry.resolve(ctx.tool_name)
        mode = getattr(registration, "product_mode", "none") or "none"
        if mode != "none":
            action = getattr(registration, "product_action", None) or ""
            if action not in effective.product_actions:
                _append(
                    run,
                    AuditEventType.AUTHORITY_DENIED,
                    {
                        "reason_code": "authority_insufficient",
                        "tool_name": ctx.tool_name,
                        "product_action": action,
                    },
                )
                return HookDecision(
                    outcome="deny",
                    reason_code="authority_insufficient",
                    message="product action outside live effective authority",
                )

        return HookDecision(outcome="allow", reason_code="ok", message="authority allow")
    except AuditAppendFailed:
        raise
    except Exception:
        return HookDecision(
            outcome="deny",
            reason_code="internal_error",
            message="authority enforcement failed",
        )
