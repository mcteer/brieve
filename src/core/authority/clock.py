# SPDX-License-Identifier: Apache-2.0
"""Clock protocol for authority TTL checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return timezone-aware UTC datetime."""
        ...


class SystemClock:
    """Wall-clock UTC implementation."""

    def now(self) -> datetime:
        return datetime.now(UTC)
