# SPDX-License-Identifier: Apache-2.0
"""GATE:correlation — blank/missing correlation ID refuses run start."""

from __future__ import annotations

from typing import Any

import pytest
from tests.harness import fake_identity_fabric, frozen_clock

from core.authority.types import AuthorityScope
from core.errors import CorrelationRequiredError
from core.registry.memory import ToolRegistry
from core.run import start_governed_run


def _kwargs() -> dict[str, Any]:
    return {
        "subject_user_id": "user-1",
        "requested_scope": AuthorityScope(tool_names=frozenset({"echo"})),
        "identity_fabric": fake_identity_fabric(),
        "clock": frozen_clock(),
        "registry": ToolRegistry(),
    }


def test_missing_correlation_id_refuses_start() -> None:
    with pytest.raises(CorrelationRequiredError):
        start_governed_run(correlation_id=None, **_kwargs())


def test_blank_correlation_id_refuses_start() -> None:
    with pytest.raises(CorrelationRequiredError):
        start_governed_run(correlation_id="   ", **_kwargs())
