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
from collections.abc import Callable
from types import FrameType
from typing import Any

from core.audit.integrity import IntegrityReport, verify_stream_integrity
from core.dependencies.store import PostgresDependencyStore
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.postgres import PostgresDurabilityProvider
from core.durability.sweeper import Sweeper
from core.hooks.suspension import TRUST_FABRIC_DEPENDENCY
from core.registry.memory import ToolRegistry
from surfaces.dispatch.nomad import NomadDispatcher
from surfaces.dispatch.types import RunDispatcher
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


def build_sweeper(
    store: PostgresDependencyStore,
    dispatcher: RunDispatcher,
    load_checkpoint: Any,
) -> Sweeper:
    """The sweeper, over the store's index and the existing dispatch seam.

    Through `RunDispatcher` rather than a resume-specific path to the scheduler: a second
    way to start a run is how two lifecycles quietly diverge, and one of them would stop
    getting the attention the other receives.
    """
    return Sweeper(
        index=store,
        health=store.state_of,
        load_checkpoint=load_checkpoint,
        dispatch_resume=_resume_dispatcher(dispatcher),
    )


def _resume_dispatcher(dispatcher: RunDispatcher) -> Any:
    """Dispatch a resume as the run's own subject, in a new allocation.

    Every field comes from the index rather than from the sweeper, because the sweeper has
    no subject of its own to lend. It carries no credential either way: the allocation
    manufactures its own from its own attested identity, which is what makes
    re-authentication structural rather than a rule someone remembers.
    """

    def _dispatch(record: Any) -> None:
        dispatcher.dispatch(
            correlation_id=record.correlation_id,
            subject_user_id=record.subject_user_id,
            tenant_id=record.tenant_id,
            agent_definition_id=record.agent_definition_id,
            requested_tools=frozenset(),
            run_id=record.run_id,
            step_index=record.step_index,
        )

    return _dispatch


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


def unconfigured_probe(product: str) -> tuple[bool, str]:
    """What a product with no probe reports: unreachable.

    Deliberately not "healthy". A registered product nobody knows how to reach is exactly
    the "we do not know" case FR-006 sends to unhealthy, and defaulting the other way would
    mean the mechanism reported everything fine for precisely the products it cannot see.

    Probing a real managed product is that product's adapter's business — this platform
    fakes product APIs by constitutional decision, so there is nothing here to reach yet.
    Stated as a default rather than left as an unimplemented branch, because the difference
    between "no products registered" and "no way to check them" is the difference between
    a quiet system and a broken one.
    """
    return False, "no probe configured for this product"


def _pass(name: str, work: Callable[[], None]) -> None:
    """Run one supervisory pass, reporting rather than propagating a failure."""
    try:
        work()
    except Exception as exc:  # noqa: BLE001 — a failed pass must not end the service
        print(f"{name} pass failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)


def record_trust_fabric_health(store: PostgresDependencyStore) -> None:
    """Record that the trust fabric is reachable — by having just reached it.

    **The probe is not a separate check, and that is the whole design.** Reaching this
    store at all required a database credential, and that credential came from the trust
    fabric moments ago. So a pass that gets here has already proved the thing it is about
    to record, and one that could not would have failed before arriving — leaving the
    record untouched, which staleness turns into UNKNOWN, which refuses.

    That is what makes FR-008b's recovery ordering self-asserting rather than a sequence
    someone has to maintain:

        fabric returns → login succeeds → credentials obtained → health recorded → sweep

    Every arrow is a precondition of the next, so the order cannot be got wrong by writing
    the steps in a different sequence. It is the only order that terminates, and it is also
    the only order that runs.

    **Nothing that failed to reach the fabric can mark it healthy** (FR-008c), because
    marking it requires a credential only the fabric issues. The guarantee is structural
    rather than a rule about who may call this.
    """
    store.record_probe(
        product=TRUST_FABRIC_DEPENDENCY,
        reachable=True,
        detail="credential acquisition succeeded",
    )


def _report_health(checker: HealthChecker) -> None:
    for health in checker.sweep():
        if not health.state.permits_calls():
            print(
                f"::dependency:: {health.product} {health.state.value}: {health.detail}",
                file=sys.stderr,
                flush=True,
            )


def _report_sweep(sweeper: Sweeper, store: PostgresDependencyStore) -> None:
    """Sweep every product something is actually waiting on.

    Driven from the suspension index rather than from the registry: a run can be suspended
    on a product whose tools are no longer registered, and that run still has to come back.
    Sweeping the registry instead would strand it silently, which is the one outcome
    ADR-0049 removed a human to avoid.
    """
    outcome = sweeper.sweep(store.awaited_products())
    if outcome.resumed:
        print(f"resumed {len(outcome.resumed)} suspended run(s): {outcome.resumed}", flush=True)
    for run_id, why in outcome.failed:
        print(f"::sweep:: {run_id} could not be resumed: {why}", file=sys.stderr, flush=True)


def _report_integrity(report: IntegrityReport) -> None:
    for finding in report.findings:
        print(
            f"::integrity:: {finding.correlation_id} {finding.kind}: {finding.detail}",
            file=sys.stderr,
            flush=True,
        )


def supervisory_pass(
    *,
    checker: HealthChecker,
    sweeper: Sweeper,
    store: PostgresDependencyStore,
    credentials: VaultDatabaseCredentials,
) -> list[str]:
    """One pass of everything this service exists to do. Returns the passes it ran.

    A named function rather than the loop's body, because the loop's body is unreachable
    from a test: it blocks. This service was shipped constructing a health checker and a
    sweeper that the loop then never called, and every conformance row still passed —
    each exercises its component directly, and nothing asserted that the loop calls them.
    The hosting claim rested on the jobspec existing.

    **Health before sweep, in that order and not the reverse.** The sweeper resumes runs
    whose dependency `state_of` reports healthy, so sweeping first would decide on the
    previous pass's health — a full interval of resuming into an outage this pass already
    knows about.

    Each pass is independent and a failure in one is reported rather than propagated. A
    supervisory loop that died on a transient database error would take the health checker
    and the sweeper with it, and the platform would then trust whatever was last recorded
    until staleness caught up.
    """
    ran: list[str] = []
    # Before the product sweep, because the fabric is what the sweep's own store
    # credentials come from — see `record_trust_fabric_health`.
    _pass("trust-fabric", lambda: record_trust_fabric_health(store))
    ran.append("trust-fabric")
    _pass("health", lambda: _report_health(checker))
    ran.append("health")
    _pass("sweep", lambda: _report_sweep(sweeper, store))
    ran.append("sweep")
    _pass("integrity", lambda: _report_integrity(check_integrity(credentials)))
    ran.append("integrity")
    return ran


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
    checker = build_health_checker(registry, store, unconfigured_probe)

    checkpoints = PostgresDurabilityProvider(credentials=credentials)
    sweeper = build_sweeper(store, NomadDispatcher(), checkpoints.load)

    tenant = os.environ.get("HARNESS_DEFAULT_TENANT", "").strip()
    interval = float(os.environ.get("MCP_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS))
    print(
        f"mcp service ready — role={VAULT_ROLE} tenant={tenant or '(unset)'} "
        f"products={registry.products()} interval={interval}s",
        flush=True,
    )

    supervisor = _Supervisor(interval)
    while supervisor.running:
        supervisory_pass(checker=checker, sweeper=sweeper, store=store, credentials=credentials)
        supervisor.sleep()

    print("mcp service stopping on signal", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
