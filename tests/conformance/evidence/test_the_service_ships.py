# SPDX-License-Identifier: Apache-2.0
"""The row whose absence let a broken feature pass every other row (015).

Every other row in this directory calls `ship_pass` itself. All of them passed while the
running mcp service had **never shipped a single entry** — its credential loader read
`VAULT_TOKEN` from the environment, which a host process running a row always has and an
allocation never does. The service reported ABSENT on every pass, correctly and uselessly,
and no row was watching the one actor that matters in production.

So this row ships nothing. It writes to the first copy and waits for the **service** to
notice. What it asserts is not that the mechanism works — eleven other rows do that — but
that the mechanism is *reached* by the process that runs it in the enclave, under that
process's own attested identity.

That distinction has now cost this repository four times: `resume_run` with no production
caller (014), a sweeper that had never dispatched since 009, an observer the protocol could
not call, and this. The shape is always the same — a capability that is correct, tested,
and wired to nothing.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

import pytest

from core.audit.destination_postgres import PostgresAuditDestination
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.schema import AuditEventType

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: The service sweeps every 30s. Three intervals plus slack: enough that a pass is certain,
#: short enough that a hung service fails the row rather than the run.
SHIP_BUDGET_SECONDS = 150


class _StaticCredentials:
    def __init__(self, credential: Any) -> None:
        self._credential = credential

    def fetch(self) -> Any:
        return self._credential


def test_row_the_running_service_ships_under_its_own_identity(
    egress_configured: dict[str, Any],
) -> None:
    from tests.harness.operator_credentials import OperatorCredentials

    credentials: Any = _StaticCredentials(OperatorCredentials().fetch())
    sink = PostgresAuditSink(credentials=credentials)
    destination = PostgresAuditDestination.from_credential(egress_configured)

    correlation_id = f"service-ships-{uuid.uuid4().hex[:12]}"
    for i in range(4):
        sink.append_event(
            correlation_id=correlation_id,
            tenant_id="tenant-local",
            event_type=AuditEventType.RUN_START,
            payload={"i": i},
        )

    # Nothing below ships. The only actor that can move these entries is the mcp service's
    # supervisory loop, holding the workload identity the policy grants read on the
    # credential path — which is precisely the link that was missing.
    deadline = time.monotonic() + SHIP_BUDGET_SECONDS
    shipped: list[Any] = []
    while time.monotonic() < deadline:
        shipped = destination.read_entries(correlation_id)
        if len(shipped) == 4:
            break
        time.sleep(5)

    assert len(shipped) == 4, (
        f"the running service shipped {len(shipped)} of 4 entries within "
        f"{SHIP_BUDGET_SECONDS}s. The mechanism may be perfect and unreached: check that the "
        f"mcp allocation can read the shipping credential under its OWN identity "
        f"(`vault read auth/nomad/role/mcp` must list the egress policy), and that the "
        f"allocation was replaced since the policy was applied — a running token does not "
        f"gain policies granted after it was minted."
    )
    assert [e.seq for e in shipped] == [0, 1, 2, 3]

    observations = destination.read_head_observations(correlation_id)
    assert observations, (
        "entries arrived without the head observation that makes truncation detectable — "
        "the service is shipping half of what the design requires"
    )
