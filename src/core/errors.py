# SPDX-License-Identifier: Apache-2.0
"""Typed domain exceptions for the governed core."""

from __future__ import annotations


class CoreError(Exception):
    """Base for core domain errors."""

    def __init__(self, message: str, *, correlation_id: str | None = None) -> None:
        super().__init__(message)
        self.correlation_id = correlation_id


class CorrelationRequiredError(CoreError):
    """Run start refused because a correlation ID was missing or blank."""


class RunNotActiveError(CoreError):
    """invoke_tool called on a run that is not active."""


class AuditChainError(CoreError):
    """Append would break the per-run hash chain."""


class RegistryError(CoreError):
    """Registry resolution failed (enforcement-path error)."""


class ToolNotRegisteredError(CoreError):
    """Named tool is not present in the registry."""
