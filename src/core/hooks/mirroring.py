# SPDX-License-Identifier: Apache-2.0
"""Governance pre-hook: entitlement mirroring for product-tagged tools."""

from __future__ import annotations

from typing import Any

from core.audit.schema import AuditEventType
from core.authority.entitlements import require_brokered_material
from core.authority.errors import AuditAppendFailed
from core.hooks.types import HookContext, HookDecision

MIRRORING_HOOK_NAME = "mirroring"


def _append(run: Any, payload: dict[str, Any]) -> None:
    sink = run.audit_sink
    cid = run.correlation_id
    try:
        sink.append_event(
            correlation_id=cid,
            tenant_id=run.tenant_id,
            event_type=AuditEventType.MIRRORING_DECISION,
            payload=payload,
        )
    except Exception as exc:
        raise AuditAppendFailed(
            f"mirroring audit append failed: {type(exc).__name__}",
            correlation_id=cid,
        ) from exc


def mirroring_pre_hook(ctx: HookContext) -> HookDecision:
    """Enforce live entitlements for federate/broker tools before shared-grain wield."""
    run = ctx.run
    if run is None:
        return HookDecision(
            outcome="deny",
            reason_code="internal_error",
            message="mirroring hook missing run context",
        )

    try:
        registration = run.registry.resolve(ctx.tool_name)
    except Exception:
        return HookDecision(
            outcome="deny",
            reason_code="internal_error",
            message="tool resolution failed in mirroring",
        )

    mode = getattr(registration, "product_mode", "none") or "none"
    if mode == "none":
        return HookDecision(outcome="allow", reason_code="ok", message="no product mode")

    fabric = getattr(run, "identity_fabric", None)
    authority = getattr(run, "authority", None)
    if fabric is None or authority is None:
        return HookDecision(
            outcome="deny",
            reason_code="internal_error",
            message="mirroring dependencies unavailable",
        )

    product = getattr(registration, "product", None) or ""
    action = getattr(registration, "product_action", None) or ""
    subject = authority.subject_user_id

    try:
        entitlements = fabric.resolve_product_entitlements(subject, product)
    except Exception as exc:
        code = getattr(exc, "reason_code", "identity_unavailable")
        if code not in {"identity_unavailable", "exchange_failed"}:
            code = "identity_unavailable"
        _append(
            run,
            {
                "outcome": "deny",
                "reason_code": code,
                "tool_name": ctx.tool_name,
                "product": product,
            },
        )
        return HookDecision(
            outcome="deny",
            reason_code=code,
            message="entitlement resolution failed",
        )

    if not entitlements or action not in entitlements:
        _append(
            run,
            {
                "outcome": "deny",
                "reason_code": "mirroring_denied",
                "tool_name": ctx.tool_name,
                "product": product,
            },
        )
        return HookDecision(
            outcome="deny",
            reason_code="mirroring_denied",
            message="product action not in user entitlements",
        )

    if mode == "broker":
        # Entitlement membership is already checked above, and the order is load-bearing:
        # a call the user is not entitled to make was denied for THAT reason, which is a
        # decision about their permissions. Only a call that passed reaches this point, so
        # anything refused here is a platform gap rather than a policy answer — and the
        # trail must say which, or whoever reads it investigates the wrong system.
        #
        # This used to call two identity-fabric methods documented "(fake only)" and pass
        # a hard-coded fixture string, then allow. A deployment configuring a brokered
        # product had its calls permitted against material that was never obtained.
        try:
            require_brokered_material(
                getattr(run, "brokered_material_source", None),
                authority.credential_id,
            )
        except Exception as exc:
            code = getattr(exc, "reason_code", "exchange_failed")
            if code not in {"broker_not_implemented", "exchange_failed"}:
                code = "exchange_failed"
            _append(
                run,
                {
                    "outcome": "deny",
                    "reason_code": code,
                    "tool_name": ctx.tool_name,
                    "product": product,
                },
            )
            return HookDecision(
                outcome="deny",
                reason_code=code,
                message=str(exc),
            )

    _append(
        run,
        {
            "outcome": "allow",
            "reason_code": "ok",
            "tool_name": ctx.tool_name,
            "product": product,
            "mode": mode,
        },
    )
    return HookDecision(outcome="allow", reason_code="ok", message="mirroring allow")
