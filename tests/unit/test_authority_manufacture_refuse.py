# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — amplification refused at manufacture."""

from __future__ import annotations

import pytest
from tests.harness import DEFAULT_AGENT_DEFINITION_ID, fake_identity_fabric, frozen_clock

from core.authority.errors import AuthorityRefuseError
from core.authority.manufacture import manufacture_authority
from core.authority.types import AuthorityScope


def test_requested_exceeds_user_refuses() -> None:
    fabric = fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo", "admin"})
    with pytest.raises(AuthorityRefuseError) as exc:
        manufacture_authority(
            subject_user_id="user-1",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo", "admin"})),
            identity_fabric=fabric,
            clock=frozen_clock(),
            agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        )
    assert exc.value.reason_code == "authority_refused"


def test_requested_exceeds_ceiling_refuses() -> None:
    fabric = fake_identity_fabric(tool_names={"echo", "admin"}, ceiling_tools={"echo"})
    with pytest.raises(AuthorityRefuseError) as exc:
        manufacture_authority(
            subject_user_id="user-1",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo", "admin"})),
            identity_fabric=fabric,
            clock=frozen_clock(),
            agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        )
    assert exc.value.reason_code == "authority_refused"
