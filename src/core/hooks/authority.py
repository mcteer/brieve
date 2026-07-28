# SPDX-License-Identifier: Apache-2.0
"""Governance pre-hook: expiry + live_effective tool/product_action bounds."""

from __future__ import annotations

from typing import Any

from core.audit.schema import AuditEventType
from core.authority.errors import AuditAppendFailed
from core.authority.intersection import live_effective
from core.hooks.suspension import TRUST_FABRIC_DEPENDENCY, suspend_for_dependency
from core.hooks.types import HookContext, HookDecision

AUTHORITY_HOOK_NAME = "authority"


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
            _append(
                run,
                AuditEventType.AUTHORITY_DENIED,
                {
                    "reason_code": "authority_insufficient",
                    "tool_name": ctx.tool_name,
                },
            )
            return HookDecision(
                outcome="deny",
                reason_code="authority_insufficient",
                message="tool outside live effective authority",
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
