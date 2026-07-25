# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — blank/missing correlation ID refuses run start."""

from __future__ import annotations

import pytest

from core.errors import CorrelationRequiredError
from core.registry.memory import ToolRegistry
from core.run import start_governed_run


def test_missing_correlation_id_refuses_start() -> None:
    with pytest.raises(CorrelationRequiredError):
        start_governed_run(
            correlation_id=None,
            scope=set(),
            registry=ToolRegistry(),
        )


def test_blank_correlation_id_refuses_start() -> None:
    with pytest.raises(CorrelationRequiredError):
        start_governed_run(
            correlation_id="   ",
            scope=set(),
            registry=ToolRegistry(),
        )
