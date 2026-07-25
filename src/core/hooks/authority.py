# SPDX-License-Identifier: Apache-2.0
"""Governance pre-hook: expiry + live_effective tool/product_action bounds."""

from __future__ import annotations

from typing import Any

from core.audit.schema import AuditEventType
from core.audit.sink import build_next_entry
from core.authority.errors import AuditAppendFailed
from core.authority.intersection import live_effective
from core.hooks.types import HookContext, HookDecision

AUTHORITY_HOOK_NAME = "authority"


def _append(run: Any, event_type: AuditEventType, payload: dict[str, Any]) -> None:
    sink = run.audit_sink
    cid = run.correlation_id
    entry = build_next_entry(sink, correlation_id=cid, event_type=event_type, payload=payload)
    try:
        sink.append(entry)
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
            policy = fabric.resolve_policy()
        except Exception:
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
