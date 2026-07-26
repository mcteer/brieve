# SPDX-License-Identifier: Apache-2.0
"""Hook pipeline orchestration — governance first, fail closed."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.audit.schema import AuditEventType
from core.audit.sink import build_next_entry
from core.authority.errors import AuditAppendFailed
from core.errors import RegistryError, ToolNotRegisteredError
from core.hooks.governance import has_required_governance_hooks
from core.hooks.types import (
    CapabilityKind,
    HookContext,
    HookDecision,
    HookPhase,
    HookRegistration,
)
from core.observation.bracket import bracket_call
from core.redaction import redact_arguments, safe_error_code
from core.run import GovernedRun, RunState
from core.telemetry.spans import emit_hook_decision_span


def sort_hooks(hooks: list[HookRegistration], phase: HookPhase) -> list[HookRegistration]:
    """Governance hooks first, then other; stable within each kind."""
    phase_hooks = [h for h in hooks if h.phase == phase]
    governance = [h for h in phase_hooks if h.capability_kind == CapabilityKind.GOVERNANCE]
    other = [h for h in phase_hooks if h.capability_kind == CapabilityKind.OTHER]
    return [*governance, *other]


def _audit(
    run: GovernedRun,
    event_type: AuditEventType,
    payload: dict[str, Any],
) -> None:
    entry = build_next_entry(
        run.audit_sink,
        correlation_id=run.correlation_id,
        event_type=event_type,
        payload=payload,
    )
    run.audit_sink.append(entry)


def _decision(
    *,
    outcome: str,
    reason_code: str,
    message: str,
    phase: HookPhase | None,
    hook_name: str,
    correlation_id: str,
    tool_name: str,
) -> HookDecision:
    return HookDecision(
        outcome=outcome,  # type: ignore[arg-type]
        reason_code=reason_code,
        message=message,
        phase=phase,
        hook_name=hook_name,
        correlation_id=correlation_id,
        tool_name=tool_name,
    )


class PipelineOutcome:
    def __init__(
        self,
        *,
        decision: str,
        reason_code: str,
        message: str,
        executed: bool,
        evidential_gap: bool = False,
        tool_result: Any = None,
    ) -> None:
        self.decision = decision
        self.reason_code = reason_code
        self.message = message
        self.executed = executed
        self.evidential_gap = evidential_gap
        self.tool_result = tool_result


def run_pipeline(
    run: GovernedRun,
    tool_name: str,
    arguments: Mapping[str, Any],
) -> PipelineOutcome:
    """Execute the normative hook pipeline for one tool invocation."""
    if run.state != RunState.ACTIVE:
        return PipelineOutcome(
            decision="deny",
            reason_code="internal_error",
            message="run is not active",
            executed=False,
        )

    redacted = redact_arguments(arguments)

    # Required enforcement dependency: full built-in governance pre-hook set.
    if not has_required_governance_hooks(run.hooks):
        return _deny_pre(
            run,
            tool_name,
            redacted,
            reason_code="internal_error",
            message="required governance enforcement hooks are missing",
            event_type=AuditEventType.ENFORCEMENT_ERROR,
        )

    # Registry resolve
    try:
        registration = run.registry.resolve(tool_name)
    except ToolNotRegisteredError:
        return _deny_pre(
            run,
            tool_name,
            redacted,
            reason_code="unregistered",
            message="tool is not registered",
        )
    except RegistryError:
        return _deny_pre(
            run,
            tool_name,
            redacted,
            reason_code="internal_error",
            message="registry resolution failed",
            event_type=AuditEventType.ENFORCEMENT_ERROR,
        )
    except Exception:
        return _deny_pre(
            run,
            tool_name,
            redacted,
            reason_code="internal_error",
            message="registry resolution failed",
            event_type=AuditEventType.ENFORCEMENT_ERROR,
        )

    # Scope check
    if tool_name not in run.scope:
        return _deny_pre(
            run,
            tool_name,
            redacted,
            reason_code="out_of_scope",
            message="tool is outside the run scope",
        )

    # Pre-hooks
    pre_hooks = sort_hooks(run.hooks, HookPhase.PRE)
    for hook in pre_hooks:
        ctx = HookContext(
            correlation_id=run.correlation_id,
            tool_name=tool_name,
            arguments=arguments,
            phase=HookPhase.PRE,
            probe_log=run.probe_log,
            run=run if hook.capability_kind == CapabilityKind.GOVERNANCE else None,
        )
        try:
            run.probe_log.append(f"{HookPhase.PRE}:{hook.capability_kind}")
            raw = hook.handler(ctx)
            if not isinstance(raw, HookDecision):
                raise TypeError("corrupt hook decision")
            decision = raw.model_copy(
                update={
                    "phase": HookPhase.PRE,
                    "hook_name": hook.name,
                    "correlation_id": run.correlation_id,
                    "tool_name": tool_name,
                }
            )
        except AuditAppendFailed:
            return PipelineOutcome(
                decision="deny",
                reason_code="internal_error",
                message="audit append failed on pre-execution path",
                executed=False,
                evidential_gap=True,
            )
        except Exception:
            return _deny_pre(
                run,
                tool_name,
                redacted,
                reason_code="internal_error",
                message="enforcement hook failed",
                event_type=AuditEventType.ENFORCEMENT_ERROR,
                hook_name=hook.name,
                capability_kind=str(hook.capability_kind),
            )

        emit_hook_decision_span(decision, capability_kind=str(hook.capability_kind))
        try:
            _audit(
                run,
                AuditEventType.PRE_DECISION,
                {
                    "hook_name": hook.name,
                    "capability_kind": str(hook.capability_kind),
                    "outcome": decision.outcome,
                    "reason_code": decision.reason_code,
                    **redacted,
                },
            )
        except Exception:
            return PipelineOutcome(
                decision="deny",
                reason_code="internal_error",
                message="audit append failed on pre-execution path",
                executed=False,
                evidential_gap=True,
            )

        if decision.outcome == "deny":
            return PipelineOutcome(
                decision="deny",
                reason_code=decision.reason_code or "hook_deny",
                message=decision.message or "denied by hook",
                executed=False,
            )

    # Execute tool body (attempt always counts as executed for post-hook / audit paths).
    #
    # A non-repeatable tool is bracketed: an intent record before the effect and a
    # result record after, so an interruption between them is resolvable by observation
    # instead of by guessing (FR-007). Repeatable tools skip the bracket — paying for
    # observation on every call would be correct but expensive, and repeatability is the
    # tool author's declaration.
    execution_error_code: str | None = None
    tool_result: Any = None
    bracket = (
        run.durability is not None
        and not registration.repeatable
        and _idempotency_key(run, tool_name) is not None
    )
    try:
        if bracket:
            assert run.durability is not None  # narrowed by `bracket`
            key = _idempotency_key(run, tool_name)
            assert key is not None
            tool_result = bracket_call(
                run.durability,
                run_id=run.run_id or run.correlation_id,
                step_index=run.step_index,
                tool_name=tool_name,
                idempotency_key=key,
                clock=run.clock,
                call=lambda: registration.handler(arguments),
            )
        else:
            tool_result = registration.handler(arguments)
    except Exception as exc:
        execution_error_code = safe_error_code(exc)

    try:
        _audit(
            run,
            AuditEventType.TOOL_OUTCOME,
            {
                "executed": True,
                "success": execution_error_code is None,
                "error_code": execution_error_code,
                **redacted,
            },
        )
    except Exception:
        # Post-path audit failure after execution — evidential gap; not clean success
        return PipelineOutcome(
            decision="deny",
            reason_code="internal_error",
            message="audit append failed after tool execution",
            executed=True,
            evidential_gap=True,
        )

    # Post-hooks (always when execution was attempted)
    post_failed = False
    post_reason = "ok"
    post_message = "ok"
    for hook in sort_hooks(run.hooks, HookPhase.POST):
        ctx = HookContext(
            correlation_id=run.correlation_id,
            tool_name=tool_name,
            arguments=arguments,
            phase=HookPhase.POST,
            executed=True,
            execution_error_code=execution_error_code,
            probe_log=run.probe_log,
            run=run if hook.capability_kind == CapabilityKind.GOVERNANCE else None,
        )
        try:
            run.probe_log.append(f"{HookPhase.POST}:{hook.capability_kind}")
            raw = hook.handler(ctx)
            if not isinstance(raw, HookDecision):
                raise TypeError("corrupt hook decision")
            decision = raw.model_copy(
                update={
                    "phase": HookPhase.POST,
                    "hook_name": hook.name,
                    "correlation_id": run.correlation_id,
                    "tool_name": tool_name,
                }
            )
        except Exception:
            post_failed = True
            post_reason = "internal_error"
            post_message = "post-execution hook failed"
            decision = _decision(
                outcome="deny",
                reason_code=post_reason,
                message=post_message,
                phase=HookPhase.POST,
                hook_name=hook.name,
                correlation_id=run.correlation_id,
                tool_name=tool_name,
            )
            emit_hook_decision_span(decision, capability_kind=str(hook.capability_kind))
            try:
                _audit(
                    run,
                    AuditEventType.POST_DECISION,
                    {
                        "hook_name": hook.name,
                        "capability_kind": str(hook.capability_kind),
                        "outcome": "deny",
                        "reason_code": post_reason,
                        "tool_executed": True,
                    },
                )
            except Exception:
                return PipelineOutcome(
                    decision="deny",
                    reason_code="internal_error",
                    message="audit append failed on post-execution path",
                    executed=True,
                    evidential_gap=True,
                )
            break

        emit_hook_decision_span(decision, capability_kind=str(hook.capability_kind))
        try:
            _audit(
                run,
                AuditEventType.POST_DECISION,
                {
                    "hook_name": hook.name,
                    "capability_kind": str(hook.capability_kind),
                    "outcome": decision.outcome,
                    "reason_code": decision.reason_code,
                    "tool_executed": True,
                },
            )
        except Exception:
            return PipelineOutcome(
                decision="deny",
                reason_code="internal_error",
                message="audit append failed on post-execution path",
                executed=True,
                evidential_gap=True,
            )

        if decision.outcome == "deny":
            post_failed = True
            post_reason = decision.reason_code or "hook_deny"
            post_message = decision.message or "denied by post-hook"
            break

    if post_failed or execution_error_code is not None:
        return PipelineOutcome(
            decision="deny",
            reason_code=post_reason if post_failed else "tool_error",
            message=post_message if post_failed else "tool execution failed",
            executed=True,
            tool_result=tool_result,
        )

    return PipelineOutcome(
        decision="allow",
        reason_code="ok",
        message="allowed",
        executed=True,
        tool_result=tool_result,
    )


def _deny_pre(
    run: GovernedRun,
    tool_name: str,
    redacted: dict[str, Any],
    *,
    reason_code: str,
    message: str,
    event_type: AuditEventType = AuditEventType.PRE_DECISION,
    hook_name: str = "pipeline",
    capability_kind: str = "governance",
) -> PipelineOutcome:
    decision = _decision(
        outcome="deny",
        reason_code=reason_code,
        message=message,
        phase=HookPhase.PRE,
        hook_name=hook_name,
        correlation_id=run.correlation_id,
        tool_name=tool_name,
    )
    emit_hook_decision_span(decision, capability_kind=capability_kind)
    try:
        _audit(
            run,
            event_type,
            {
                "hook_name": hook_name,
                "outcome": "deny",
                "reason_code": reason_code,
                **redacted,
            },
        )
    except Exception:
        return PipelineOutcome(
            decision="deny",
            reason_code="internal_error",
            message="audit append failed on pre-execution path",
            executed=False,
            evidential_gap=True,
        )
    return PipelineOutcome(
        decision="deny",
        reason_code=reason_code,
        message=message,
        executed=False,
    )


def _idempotency_key(run: GovernedRun, tool_name: str) -> str | None:
    """Stable across retries of the same step, distinct across steps (FR-010).

    Derived from run and step rather than from arguments: two identical calls at
    different points in a run are different steps, and a retry of one step is the same
    step even if its arguments were re-serialised differently.
    """
    run_id = run.run_id or run.correlation_id
    if not run_id:
        return None
    return f"{run_id}:{run.step_index}:{tool_name}"
