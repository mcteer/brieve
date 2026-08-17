# SPDX-License-Identifier: Apache-2.0
"""Terraform-shaped Propose helpers — plan evidence and judge (047).

Mirrors the product-specific half of ``policy_authoring.py`` without living inside
``core/authoring`` (product impact evidence stays at the surface).
"""

from __future__ import annotations

import os
from typing import Any


def compose_plan_evidence(*, plan_result: dict[str, Any]) -> str:
    """Bounded, reviewer-facing plan evidence for a PR body. Never includes secrets."""
    if plan_result.get("fixture"):
        raise RuntimeError("fixture plan output cannot become proposal evidence")
    exit_code = plan_result.get("exit_code")
    has_changes = bool(plan_result.get("has_changes"))
    output = str(plan_result.get("output") or "")
    # Bound again at compose time — handlers already truncate, but evidence is a second gate.
    clipped = output[-4000:]
    return (
        "## Terraform plan\n\n"
        f"- exit_code: {exit_code}\n"
        f"- has_changes: {has_changes}\n\n"
        "```\n"
        f"{clipped}\n"
        "```\n"
    )


def judge_may_publish(*, authored_paths: list[str], task: str) -> tuple[bool, str]:
    """Fail-closed publish gate. Deny when there is nothing to propose or when forced.

    ``HARNESS_JUDGE_DENY=1`` forces deny for hermetic rows (P5). Always-allow is invalid.
    """
    if os.environ.get("HARNESS_JUDGE_DENY", "").strip() in {"1", "true", "yes"}:
        return False, "judge denied publish"
    if not authored_paths:
        return False, "judge denied publish: no authored files"
    if not (task or "").strip():
        return False, "judge denied publish: empty task"
    return True, "ok"


def quality_judge_may_publish(
    *,
    authored_paths: list[str],
    task: str,
    write_plan: str,
    files: dict[str, str],
    write_model: str,
    judge_chooser: Any,
) -> tuple[bool, str]:
    """Structural pre-check, then a language-model quality gate when the writer is live.

    A fixture write cell keeps the structural check only — hermetic rows must not call a
    vendor. A live write cell MUST be judged by a distinct model (ADR-0067); missing or
    failing judgement denies publish. Always-allow after a live write is invalid (FR-010).
    """
    allowed, reason = judge_may_publish(authored_paths=authored_paths, task=task)
    if not allowed:
        return allowed, reason
    write_is_live = bool(write_model) and not write_model.startswith("fixture/")
    if not write_is_live:
        return True, reason
    judger = getattr(judge_chooser, "judge_authored_work", None)
    if not callable(judger):
        return False, "could not judge the change"
    try:
        allowed, reason = judger(
            task=task,
            write_plan=write_plan,
            files=files,
        )
    except Exception:  # noqa: BLE001 — provider/schema failure is a deny, not a skip
        return False, "could not judge the change"
    return bool(allowed), (reason or "judge denied publish") if not allowed else (reason or "ok")


__all__ = ["compose_plan_evidence", "judge_may_publish", "quality_judge_may_publish"]
