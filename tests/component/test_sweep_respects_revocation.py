# SPDX-License-Identifier: Apache-2.0
"""A revoked grant cannot be resumed, and the sweeper has no path that could override it.

Revocation is unilateral and immediate (Principle IV). The sweeper never carries a run's
authority — it dispatches, and the resumed allocation manufactures fresh authority — so
revocation is enforced where it always was rather than needing a second check here.

That is the substance: the sweeper is not *trusted* to respect revocation, it is
structurally unable to bypass it.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from core.authority.errors import AuthorityRefuseError
from core.authority.grant import GrantExpiredError, issue_grant
from core.authority.manufacture import manufacture_authority
from core.authority.types import AuthorityScope
from tests.harness import DEFAULT_AGENT_DEFINITION_ID, fake_identity_fabric, frozen_clock


def test_a_resumed_run_manufactures_fresh_authority_and_can_be_refused() -> None:
    clock = frozen_clock()
    grant = issue_grant(
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        clock=clock,
        duration=timedelta(minutes=5),
    )
    clock.advance(timedelta(minutes=6))

    with pytest.raises((GrantExpiredError, AuthorityRefuseError)):
        manufacture_authority(
            subject_user_id="user-1",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
            identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
            clock=clock,
            agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
            grant=grant,
        )


def test_the_sweeper_carries_no_credential_to_forward() -> None:
    """Structural, not procedural.

    A sweeper holding a run's credential would only respect revocation if it remembered
    to check. It holds none — the record it acts on carries identity and place, and
    nothing that authorizes anything.
    """
    from core.durability.sweeper import SuspendedRunRecord

    fields = set(SuspendedRunRecord.__dataclass_fields__)
    for credential_shaped in ("token", "credential", "authority", "grant", "secret"):
        assert credential_shaped not in fields, (
            f"{credential_shaped!r} on a suspension record would let a resume replay it"
        )
