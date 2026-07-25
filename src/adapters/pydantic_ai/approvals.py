# SPDX-License-Identifier: Apache-2.0
"""Mapping 3 of 4: framework interrupts to the approval-hook path.

Thin binding only — no Control Groups, no portal, no notification channel. What
this establishes is that an interrupt reaches a governed decision point and that
the decision defaults to deny.

An approval is permission to *attempt* the call, never a substitute for it: an
approved interrupt still goes through ``invoke_tool`` and can still be denied by
core. Approval never becomes an ungoverned execution path.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from adapters.pydantic_ai.run_context import AdapterRunContext


def request_approval(
    deps: AdapterRunContext,
    *,
    tool_name: str,
    arguments: Mapping[str, Any],
) -> bool:
    """Ask the bound approval hook whether an interrupted call may proceed.

    Returns False on any hook error — an approver that cannot answer has not
    approved (Principle III).
    """
    try:
        return bool(
            deps.approval_hook.request_approval(
                tool_name,
                arguments,
                deps.correlation_id,
            )
        )
    except Exception:
        return False
