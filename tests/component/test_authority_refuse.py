# SPDX-License-Identifier: Apache-2.0
"""US2 — amplification refused at start."""

from __future__ import annotations

import pytest

from core.audit.schema import AuditEventType
from core.authority.errors import AuthorityRefuseError
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from tests.harness import capture_audit, fake_identity_fabric, frozen_clock


def test_refuse_exceeds_user() -> None:
    fabric = fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo", "admin"})
    audit = capture_audit()
    with pytest.raises(AuthorityRefuseError) as exc:
        start_governed_run(
            correlation_id="corr-refuse-user",
            subject_user_id="user-1",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo", "admin"})),
            identity_fabric=fabric,
            clock=frozen_clock(),
            registry=ToolRegistry(),
            audit_sink=audit,
        )
    assert exc.value.reason_code == "authority_refused"
    types = [e.event_type for e in audit.all_entries()]
    assert AuditEventType.AUTHORITY_REFUSED in types


def test_refuse_exceeds_ceiling() -> None:
    fabric = fake_identity_fabric(tool_names={"echo", "admin"}, ceiling_tools={"echo"})
    with pytest.raises(AuthorityRefuseError):
        start_governed_run(
            correlation_id="corr-refuse-ceil",
            subject_user_id="user-1",
            requested_scope=AuthorityScope(tool_names=frozenset({"echo", "admin"})),
            identity_fabric=fabric,
            clock=frozen_clock(),
            registry=ToolRegistry(),
            audit_sink=capture_audit(),
        )
