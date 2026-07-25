# SPDX-License-Identifier: Apache-2.0
"""Run start must refuse when the genesis audit entry cannot be written."""

from __future__ import annotations

import pytest

from core.audit.schema import AuditEntry
from core.audit.sink import InMemoryAuditSink
from core.errors import CoreError
from core.registry.memory import ToolRegistry
from core.run import start_governed_run


class FailAfterAuditSink(InMemoryAuditSink):
    def __init__(self, fail_on_append_index: int) -> None:
        super().__init__()
        self._fail_on = fail_on_append_index
        self._appends = 0

    def append(self, entry: AuditEntry) -> None:
        if self._appends >= self._fail_on:
            raise RuntimeError("audit append failed")
        self._appends += 1
        super().append(entry)


def test_run_start_audit_failure_raises_core_error() -> None:
    audit = FailAfterAuditSink(fail_on_append_index=0)
    with pytest.raises(CoreError, match="could not be audited"):
        start_governed_run(
            correlation_id="corr-start-fail",
            scope=set(),
            registry=ToolRegistry(),
            audit_sink=audit,
        )
