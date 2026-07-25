# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — a run cannot start without an agent definition (FR-007)."""

from __future__ import annotations

from typing import Any

import pytest
from tests.harness import DEFAULT_AGENT_DEFINITION_ID, fake_identity_fabric, frozen_clock

from core.authority.errors import AuthorityRefuseError
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run


def _kwargs() -> dict[str, Any]:
    return {
        "correlation_id": "corr-def",
        "subject_user_id": "user-1",
        "requested_scope": AuthorityScope(tool_names=frozenset({"echo"})),
        "identity_fabric": fake_identity_fabric(),
        "clock": frozen_clock(),
        "registry": ToolRegistry(),
    }


@pytest.mark.parametrize("definition_id", ["", "   "])
def test_blank_agent_definition_refuses_start(definition_id: str) -> None:
    with pytest.raises(AuthorityRefuseError) as exc:
        start_governed_run(agent_definition_id=definition_id, **_kwargs())
    assert exc.value.reason_code == "identity_unavailable"


def test_missing_agent_definition_is_a_type_error() -> None:
    """The parameter is required, not defaulted — omitting it cannot silently pass."""
    with pytest.raises(TypeError):
        start_governed_run(**_kwargs())


def test_unknown_agent_definition_refuses_rather_than_opening_ceiling() -> None:
    """An id outside the ceiling map must refuse, never fall back to a default."""
    fabric = fake_identity_fabric(
        ceilings={DEFAULT_AGENT_DEFINITION_ID: AuthorityScope(tool_names=frozenset({"echo"}))}
    )
    kwargs = _kwargs()
    kwargs["identity_fabric"] = fabric
    with pytest.raises(AuthorityRefuseError) as exc:
        start_governed_run(agent_definition_id="agent-def-unknown", **kwargs)
    assert exc.value.reason_code == "identity_unavailable"
