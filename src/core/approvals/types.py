# SPDX-License-Identifier: Apache-2.0
"""Approval seam — the target for framework interrupts. Default deny.

Thin protocol only. Control Groups (ADR-0016), the portal, and any human
notification channel are out of scope; this exists so an interrupt binds to a
governed decision point rather than to adapter-local logic.

A model verdict may gate a step but never satisfies an approval a policy assigns
to a human (Principle IX) — that distinction belongs to whatever implements this
protocol for real, not to the adapter.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class ApprovalHook(Protocol):
    """Decide whether an interrupted call may proceed."""

    def request_approval(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        correlation_id: str,
    ) -> bool:
        """Return True to allow. Implementations deny on error, never allow."""
        ...


class DenyAllApprovalHook:
    """Default: nothing is approved. The safe answer when no approver exists."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    def request_approval(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        correlation_id: str,
    ) -> bool:
        self.requests.append((tool_name, correlation_id))
        return False


class InjectedApprovalHook:
    """Test double with an injectable verdict. Errors still deny."""

    def __init__(self, *, allow: bool = False, raises: bool = False) -> None:
        self._allow = allow
        self._raises = raises
        self.requests: list[tuple[str, str]] = []

    def request_approval(
        self,
        tool_name: str,
        arguments: Mapping[str, Any],
        correlation_id: str,
    ) -> bool:
        self.requests.append((tool_name, correlation_id))
        if self._raises:
            raise RuntimeError("approval backend unavailable")
        return self._allow
