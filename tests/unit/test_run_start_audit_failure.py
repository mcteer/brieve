# SPDX-License-Identifier: Apache-2.0
"""Run start must refuse when authority/run audit entries cannot be written."""

from __future__ import annotations

from typing import Any

import pytest
from tests.harness import DEFAULT_AGENT_DEFINITION_ID, fake_identity_fabric, frozen_clock

from core.audit.schema import AuditEntry
from core.audit.sink import InMemoryAuditSink
from core.authority.errors import AuthorityRefuseError
from core.authority.types import AuthorityScope
from core.errors import CoreError
from core.registry.memory import ToolRegistry
from core.run import start_governed_run


class FailAfterAuditSink(InMemoryAuditSink):
    def __init__(self, fail_on_append_index: int) -> None:
        super().__init__()
        self._fail_on = fail_on_append_index
        self._appends = 0

    def append_event(self, **kwargs: Any) -> AuditEntry:
        if self._appends >= self._fail_on:
            raise RuntimeError("audit append failed")
        self._appends += 1
        return super().append_event(**kwargs)


def _start(audit: InMemoryAuditSink) -> None:
    start_governed_run(
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        correlation_id="corr-start-fail",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fake_identity_fabric(),
        clock=frozen_clock(),
        registry=ToolRegistry(),
        audit_sink=audit,
    )


def test_authority_issued_audit_failure_refuses() -> None:
    audit = FailAfterAuditSink(fail_on_append_index=0)
    with pytest.raises(AuthorityRefuseError, match="could not be audited"):
        _start(audit)


def test_run_start_audit_failure_raises_core_error() -> None:
    audit = FailAfterAuditSink(fail_on_append_index=1)
    with pytest.raises(CoreError, match="could not be audited"):
        _start(audit)
