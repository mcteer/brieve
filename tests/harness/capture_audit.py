# SPDX-License-Identifier: Apache-2.0
"""Factory for the in-memory audit sink used in tests."""

from __future__ import annotations

from core.audit.sink import InMemoryAuditSink


def capture_audit() -> InMemoryAuditSink:
    """Return a fresh in-memory audit sink with chain verification access."""
    return InMemoryAuditSink()
