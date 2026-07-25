# SPDX-License-Identifier: Apache-2.0
"""Correlation ID validation — refuse blank/missing IDs (fail closed)."""

from __future__ import annotations

from core.errors import CorrelationRequiredError


def validate_correlation_id(value: str | None) -> str:
    """Return a non-empty correlation ID or raise CorrelationRequiredError."""
    if value is None:
        raise CorrelationRequiredError("correlation ID is required")
    stripped = value.strip()
    if not stripped:
        raise CorrelationRequiredError("correlation ID must be non-empty")
    return stripped
