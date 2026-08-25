# SPDX-License-Identifier: Apache-2.0
"""Terraform-shaped Propose helpers — plan evidence and judge (047).

Mirrors the product-specific half of ``policy_authoring.py`` without living inside
``core/authoring`` (product impact evidence stays at the surface).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


class PlanGateRefused(RuntimeError):
    """The final Terraform plan oracle failed. No compose, no PR (047 / ADR-0047)."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def plan_evidence_lines(plan_result: dict[str, Any]) -> list[str]:
    """Bounded facts a reviewer can scan. Never includes secret values."""
    if plan_result.get("fixture"):
        raise RuntimeError("fixture plan output cannot become proposal evidence")
    exit_code = plan_result.get("exit_code")
    has_changes = bool(plan_result.get("has_changes"))
    output = str(plan_result.get("output") or "")[-4000:]
    lines: list[str] = [
        f"Measured by `terraform plan` (exit_code={exit_code}, has_changes={has_changes}).",
    ]
    for raw in output.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        lines.append(stripped[:500])
        if len(lines) >= 40:
            lines.append("(plan output truncated)")
            break
    return lines


def compose_plan_evidence(*, plan_result: dict[str, Any]) -> str:
    """Bounded, reviewer-facing plan evidence for a PR body. Never includes secrets."""
    return "\n".join(plan_evidence_lines(plan_result))


def attach_plan_evidence(*, proposal: Any, plan_result: dict[str, Any] | None) -> Any:
    """Mutate the composed proposal with measured plan facts (042's evidence seam).

    Refuses when there is no plan: a PR that looks complete without the oracle is the
    reassurance ADR-0047 forbids.
    """
    if plan_result is None:
        raise PlanGateRefused("no Terraform plan is attached to this proposal")
    proposal.evidence.extend(plan_evidence_lines(plan_result))
    return proposal


def _plan_workdir(workspace: Path, authored_paths: list[str]) -> Path:
    tf_paths = [p for p in authored_paths if p.endswith((".tf", ".tf.json"))]
    if not tf_paths:
        raise PlanGateRefused("no Terraform files to plan")
    parents = {str(Path(path).parent) for path in tf_paths}
    if len(parents) == 1:
        relative = next(iter(parents))
        return workspace if relative in {".", ""} else workspace / relative
    return workspace


def gate_final_plan(*, workspace: Path, authored_paths: list[str]) -> dict[str, Any]:
    """Run the real plan oracle against the authored tree, or refuse.

    ``HARNESS_TERRAFORM_PLAN_FAIL=1`` forces a red gate for hermetic P6. A missing
    binary still refuses (not a green fixture). Always-green is invalid.
    """
    if os.environ.get("HARNESS_TERRAFORM_PLAN_FAIL", "").strip() in {"1", "true", "yes"}:
        raise PlanGateRefused("the Terraform plan failed")
    workdir = _plan_workdir(workspace, authored_paths)
    from surfaces.handlers import terraform_plan

    try:
        result = terraform_plan({"working_directory": str(workdir)})
    except RuntimeError as exc:
        raise PlanGateRefused("the Terraform plan failed") from exc
    if not isinstance(result, dict) or result.get("fixture"):
        raise PlanGateRefused("the Terraform plan failed")
    return result


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
    instruction: str = "",
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
            instruction=instruction,
        )
    except Exception:  # noqa: BLE001 — provider/schema failure is a deny, not a skip
        return False, "could not judge the change"
    return bool(allowed), (reason or "judge denied publish") if not allowed else (reason or "ok")


def usage_notes_for(paths: list[str]) -> str:
    """How a reviewer applies authored Terraform after merge. Empty when not Terraform."""
    tf_paths = [p for p in paths if p.endswith((".tf", ".tfvars")) or p.endswith(".tf.json")]
    if not tf_paths:
        return ""
    dirs = sorted({p.rsplit("/", 1)[0] if "/" in p else "." for p in tf_paths})
    where = dirs[0] if len(dirs) == 1 else "the directory that contains the `.tf` files"
    if where == ".":
        where = "the repository root"
    return (
        "Nothing in this pull request is applied until a person merges it.\n\n"
        f"These files are Terraform. After merge, from {where}:\n\n"
        "1. `terraform init`\n"
        "2. `terraform plan` — read the plan before going further\n"
        "3. `terraform apply` only after you accept that plan\n\n"
        "Set required variables (see `variables.tf` if present) from your own environment "
        "or a tfvars file you already trust. Do not paste credentials into the pull request."
    )


def reviewer_copy(
    *,
    chooser: Any,
    task: str,
    write_plan: str,
    files: dict[str, str],
    instruction: str = "",
) -> tuple[str, str, str]:
    """Title, rationale, usage. Prefer a model description; never fail the publish on copy."""
    from core.authoring.proposal import ProposedFile, title_for

    describer = getattr(chooser, "describe_proposal", None)
    if callable(describer):
        try:
            title, rationale, usage = describer(
                task=task,
                write_plan=write_plan,
                files=files,
                instruction=instruction,
            )
        except Exception:  # noqa: BLE001 — copy is presentation; Judge already gated publish
            title, rationale, usage = "", "", ""
        else:
            title = (title or "").strip()
            rationale = (rationale or "").strip()
            usage = (usage or "").strip()
            if title and rationale:
                return title, rationale, usage or usage_notes_for(list(files))
    listed = [ProposedFile(path=path, body="", is_diff=False) for path in files]
    return (
        title_for(files=listed, task=task, summary=write_plan),
        write_plan,
        usage_notes_for(list(files)),
    )


__all__ = [
    "PlanGateRefused",
    "attach_plan_evidence",
    "compose_plan_evidence",
    "gate_final_plan",
    "judge_may_publish",
    "plan_evidence_lines",
    "quality_judge_may_publish",
    "reviewer_copy",
    "usage_notes_for",
]
