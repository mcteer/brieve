# SPDX-License-Identifier: Apache-2.0
"""Governance pre-hook: entitlement mirroring for product-tagged tools."""

from __future__ import annotations

from typing import Any

from core.audit.schema import AuditEventType
from core.audit.sink import build_next_entry
from core.authority.errors import AuditAppendFailed
from core.hooks.types import HookContext, HookDecision

MIRRORING_HOOK_NAME = "mirroring"


def _append(run: Any, payload: dict[str, Any]) -> None:
    sink = run.audit_sink
    cid = run.correlation_id
    entry = build_next_entry(
        sink,
        correlation_id=cid,
        event_type=AuditEventType.MIRRORING_DECISION,
        payload=payload,
    )
    try:
        sink.append(entry)
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
        # Entitlement membership already checked before any shared-grain wield.
        material = fabric.get_brokered_material(authority.credential_id)
        if material is None:
            try:
                fabric.issue_brokered_material(
                    authority.credential_id,
                    "HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET",
                )
            except Exception as exc:
                code = getattr(exc, "reason_code", "exchange_failed")
                _append(
                    run,
                    {
                        "outcome": "deny",
                        "reason_code": "exchange_failed",
                        "tool_name": ctx.tool_name,
                    },
                )
                return HookDecision(
                    outcome="deny",
                    reason_code="exchange_failed",
                    message="brokered exchange failed",
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
