# SPDX-License-Identifier: Apache-2.0
"""The persistent MCP service.

Three things live here because each needs something that outlives a run, and everything
else in this platform is deliberately ephemeral:

- the **MCP transport** itself, the second of ADR-0033's four;
- the **dependency health checker**, which must answer on demand rather than at the next
  tick — a run about to call a product asks now;
- the **resume sweeper** and **continuous evidence verification**, which need to notice
  things happening while nobody is watching.

**The registry of record.** This service's :class:`~core.registry.memory.ToolRegistry` is
the estate's, and that is a decision with tenure rather than an implementation detail.
`ToolRegistry` is per-process and in-memory — 002 built it for one caller in one process —
so before this there was no instance a persistent service could read, and the health
checker's subject set had no source at all.

The ADR-0008 line, stated where it will be read: this is the platform's **own** tool
registry gaining a persistent home, not a registry *product*. It registers nothing on
anyone else's behalf, serves no other system, and ships no API for third parties. If it
ever grows one, that is the violation — not this.

**No product credential.** The service starts runs and reads health; it does not act on
the products agents operate, so there is nothing for it to hold. That is the whole
mitigation for a persistent component holding a persistent identity, and it is worth
checking against rather than assuming: if this module ever needs a product credential, the
asymmetry that justifies its existence has broken.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from types import FrameType
from typing import Any

from core.audit.integrity import IntegrityReport, verify_stream_integrity
from core.dependencies.store import PostgresDependencyStore
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.registry.memory import ToolRegistry
from surfaces.mcp.health import HealthChecker, Probe

#: The Vault JWT auth role this service assumes. Selected by the job id in its workload
#: identity's claims — asking for the wrong one fails as "could not obtain a database
#: credential ... HTTPError", which names the credential path rather than the mismatch.
VAULT_ROLE = "mcp"

#: Seconds between supervisory passes.
#:
#: Short enough that a recovered dependency resumes runs promptly, long enough that
#: checking is not itself load on a product that is already struggling. A numeric default
#: rather than a computed one, because the right value is deployment-shaped and pretending
#: otherwise would be false precision.
DEFAULT_INTERVAL_SECONDS = 30.0

#: This module is a supervisory loop, and blocking is its job.
#:
#: Declared explicitly because `tests/unit/test_surface_never_pauses.py` forbids blocking
#: primitives across the surfaces package — correctly, since in a request path any sleep
#: is a held request. A service loop is the one shape where that approximation is wrong,
#: and saying so on the record is better than the check quietly growing an exception.
#:
#: What the rule actually forbids still holds here absolutely: **nothing in this loop waits
#: on a human.** It waits on its own interval, and every pass ends whether or not anything
#: was found.
__service_loop__ = True


def build_credentials() -> VaultDatabaseCredentials:
    """This allocation's own identity. No token reaches this process any other way."""
    return VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role=VAULT_ROLE)


def run_connection_factory(credentials: VaultDatabaseCredentials) -> Any:
    """A factory for connections under the **run** role.

    `verify_stream_integrity` needs one, and the evidence role cannot supply it:
    `audit_stream_heads` deliberately carries no grant for the read path, because a reader
    able to see the heads could learn what it would need to forge.
    """
    import pg8000.dbapi

    def _open() -> Any:
        cred = credentials.fetch()
        return pg8000.dbapi.connect(
            host="127.0.0.1",
            port=5432,
            database="brieve",
            user=cred.username,
            password=cred.password,
        )

    return _open


def check_integrity(credentials: VaultDatabaseCredentials) -> IntegrityReport:
    """Verify evidence-stream integrity while the system is running.

    008 shipped this checker and called it from `make enclave-verify`, which covers
    bring-up and not the running estate — a tamper-detection mechanism that only runs when
    an operator restarts something detects tampering on a schedule the tamperer chooses.
    """
    return verify_stream_integrity(run_connection_factory(credentials))


def build_health_checker(
    registry: ToolRegistry,
    store: PostgresDependencyStore,
    probe: Probe,
) -> HealthChecker:
    return HealthChecker(registry=registry, store=store, probe=probe)


class _Supervisor:
    """Runs the periodic passes and stops cleanly on a signal.

    A service whose task exits is not a service: Nomad restarts it, the restart budget
    drains, and the job is eventually marked failed — while `enclave-verify` still reports
    it *registered*, because registration and liveness are different facts. So this
    blocks, and it stops on SIGTERM rather than being killed, which is what lets a drain
    or an identity re-issue land cleanly.
    """

    def __init__(self, interval: float) -> None:
        self.interval = interval
        self.running = True
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, _signum: int, _frame: FrameType | None) -> None:
        self.running = False

    def sleep(self) -> None:
        """Wait, in slices, so a signal is noticed promptly rather than at the next pass."""
        remaining = self.interval
        while self.running and remaining > 0:
            step = min(1.0, remaining)
            time.sleep(step)
            remaining -= step


def main() -> int:
    """Start the service.

    What this feature owed here is the persistent home, the attested identity that reaches
    the stores, and a supervisory loop that keeps running. The transport's operations and
    the sweeper's resume path are the tasks that follow, and each hangs off this loop.
    """
    try:
        credentials = build_credentials()
    except Exception as exc:  # noqa: BLE001 — an unattested service must not start
        print(f"no attested identity available: {exc}", file=sys.stderr)
        return 2

    store = PostgresDependencyStore(credentials=credentials)
    store.migrate()

    registry = ToolRegistry()
    tenant = os.environ.get("HARNESS_DEFAULT_TENANT", "").strip()
    interval = float(os.environ.get("MCP_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    print(
        f"mcp service ready — role={VAULT_ROLE} tenant={tenant or '(unset)'} "
        f"products={registry.products()} interval={interval}s",
        flush=True,
    )

    supervisor = _Supervisor(interval)
    while supervisor.running:
        # Each pass is independent and failures are reported rather than fatal. A
        # supervisory loop that died on a transient database error would take the health
        # checker and the sweeper with it — and the platform would then trust whatever was
        # last recorded until staleness caught up.
        try:
            report = check_integrity(credentials)
            if not report.ok:
                for finding in report.findings:
                    print(
                        f"::integrity:: {finding.correlation_id} {finding.kind}: {finding.detail}",
                        file=sys.stderr,
                        flush=True,
                    )
        except Exception as exc:  # noqa: BLE001 — a failed pass must not end the service
            print(
                f"integrity pass failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
                flush=True,
            )

        supervisor.sleep()

    print("mcp service stopping on signal", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
