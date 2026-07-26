# SPDX-License-Identifier: Apache-2.0
"""Grant issue and expiry — FR-001/FR-002, T008."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from tests.harness import DEFAULT_AGENT_DEFINITION_ID, fake_identity_fabric, frozen_clock
from tests.harness.frozen_clock import FrozenClock

from core.authority.errors import AuthorityRefuseError
from core.authority.grant import DelegationGrant, GrantExpiredError, issue_grant
from core.authority.manufacture import manufacture_authority
from core.authority.types import AuthorityScope

SCOPE = AuthorityScope(tool_names=frozenset({"read_tool"}))


def _grant(clock: FrozenClock, **kw: Any) -> DelegationGrant:
    return issue_grant(
        subject_user_id=kw.pop("subject_user_id", "user-1"),
        agent_definition_id=kw.pop("agent_definition_id", DEFAULT_AGENT_DEFINITION_ID),
        requested_scope=SCOPE,
        clock=clock,
        duration=kw.pop("duration", timedelta(hours=1)),
        **kw,
    )


def test_blank_subject_refuses_issue() -> None:
    with pytest.raises(AuthorityRefuseError):
        _grant(frozen_clock(), subject_user_id="   ")


def test_blank_definition_refuses_issue() -> None:
    with pytest.raises(AuthorityRefuseError):
        _grant(frozen_clock(), agent_definition_id="")


def test_duration_beyond_definition_maximum_refuses_issue() -> None:
    """A grant outliving its definition's ceiling would let a run hold authority the
    definition never permitted."""
    with pytest.raises(AuthorityRefuseError):
        _grant(frozen_clock(), duration=timedelta(hours=2), max_run_duration=timedelta(hours=1))


def test_grant_holds_no_credential_material() -> None:
    """Structural, not conventional: there is nowhere to put one."""
    grant = _grant(frozen_clock())
    fields = set(type(grant).model_fields)
    assert not fields & {"credential", "token", "secret", "password", "run_salt"}


def test_expired_grant_refuses_manufacture() -> None:
    clock = frozen_clock()
    grant = _grant(clock, duration=timedelta(minutes=30))
    clock.advance(timedelta(minutes=31))

    with pytest.raises(GrantExpiredError) as excinfo:
        manufacture_authority(
            subject_user_id="user-1",
            requested_scope=SCOPE,
            identity_fabric=fake_identity_fabric(tool_names={"read_tool"}),
            clock=clock,
            agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
            grant=grant,
        )
    assert excinfo.value.reason_code == "grant_expired"


def test_live_grant_permits_manufacture() -> None:
    clock = frozen_clock()
    grant = _grant(clock)
    result = manufacture_authority(
        subject_user_id="user-1",
        requested_scope=SCOPE,
        identity_fabric=fake_identity_fabric(tool_names={"read_tool"}),
        clock=clock,
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        grant=grant,
    )
    assert "read_tool" in result.credential.effective.tool_names


def test_grant_is_not_renewable_from_inside_a_run() -> None:
    """Only a human extends consent (ADR-0016). No API here may do it."""
    grant = _grant(frozen_clock())
    assert not [name for name in dir(grant) if "renew" in name.lower() or "extend" in name.lower()]
    assert type(grant).model_config["frozen"] is True
