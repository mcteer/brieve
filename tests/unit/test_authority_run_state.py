# SPDX-License-Identifier: Apache-2.0
"""FR-011 — run state exposes TaskCredentialRef fields only."""

from __future__ import annotations

from tests.harness import (
    BROKERED_GRAIN_MARKER,
    assert_no_secret_values,
    capture_audit,
    fake_identity_fabric,
    frozen_clock,
)

from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run


def test_run_state_has_no_brokered_secret() -> None:
    fabric = fake_identity_fabric(tool_names={"echo"})
    audit = capture_audit()
    run = start_governed_run(
        correlation_id="corr-state-1",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=ToolRegistry(),
        audit_sink=audit,
    )
    fabric.issue_brokered_material(run.authority.credential_id, BROKERED_GRAIN_MARKER)
    public = run.authority.public_dict()
    blob = str(public) + str(run.authority.model_dump())
    assert BROKERED_GRAIN_MARKER not in blob
    assert "run_salt" not in public
    assert_no_secret_values(audit)
