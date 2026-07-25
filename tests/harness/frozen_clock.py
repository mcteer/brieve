# SPDX-License-Identifier: Apache-2.0
"""Deterministic clock with advance() for TTL tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class FrozenClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start if start is not None else datetime(2026, 1, 1, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


def frozen_clock(start: datetime | None = None) -> FrozenClock:
    """Factory matching the documented harness name."""
    return FrozenClock(start)
