# SPDX-License-Identifier: Apache-2.0
"""US4 — the interrupt mapping binds to the approval hook and defaults deny (FR-009)."""

from __future__ import annotations

from adapters.pydantic_ai.approvals import request_approval
from adapters.pydantic_ai.run_context import AdapterRunContext
from core.approvals import DenyAllApprovalHook, InjectedApprovalHook
from core.run import RunState


class _Run:
    state = RunState.ACTIVE
    correlation_id = "corr-approval"
    subject_user_id = "user-1"
    agent_definition_id = "agent-def-1"


def _deps(hook: object) -> AdapterRunContext:
    return AdapterRunContext(governed_run=_Run(), approval_hook=hook)  # type: ignore[arg-type]


def test_default_hook_denies() -> None:
    deps = _deps(DenyAllApprovalHook())
    assert request_approval(deps, tool_name="echo", arguments={}) is False


def test_injected_allow_is_honoured() -> None:
    deps = _deps(InjectedApprovalHook(allow=True))
    assert request_approval(deps, tool_name="echo", arguments={}) is True


def test_hook_error_denies_rather_than_propagating() -> None:
    """An approver that cannot answer has not approved (Principle III)."""
    deps = _deps(InjectedApprovalHook(raises=True))
    assert request_approval(deps, tool_name="echo", arguments={}) is False


def test_request_carries_the_run_correlation_id() -> None:
    hook = InjectedApprovalHook(allow=True)
    deps = _deps(hook)

    request_approval(deps, tool_name="echo", arguments={"a": 1})

    assert hook.requests == [("echo", "corr-approval")]


def test_approval_alone_executes_nothing() -> None:
    """Approval is permission to attempt, never an ungoverned execution path."""
    hook = InjectedApprovalHook(allow=True)
    deps = _deps(hook)

    approved = request_approval(deps, tool_name="echo", arguments={})

    assert approved is True
    # No registry, no invoke_tool, no tool body — approval on its own does nothing.
    assert deps.governed_run.state is RunState.ACTIVE
