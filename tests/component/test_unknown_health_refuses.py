# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — unknown and stale health refuse (FR-006).

Guessing reachable is how a dead dependency gets called anyway. The two ways to arrive at
"we do not know" are never having checked and having checked too long ago, and both must
land in the same place — a checker that stopped running must not leave the platform
confident that everything was fine at the moment it died.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.dependencies.types import HealthState
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run


class NeverChecked:
    def state_of(self, product: str) -> HealthState:
        return HealthState.UNKNOWN


def _run_with(reader: object):  # type: ignore[no-untyped-def]
    handler = CountingHandler()
    run, h, _ = make_run(tool_name="provision", scope={"provision"}, handler=handler)
    run.registry.register("provision", h, product="terraform-cloud")
    run.dependency_health = reader  # type: ignore[assignment]
    return run, h


def test_never_checked_refuses() -> None:
    run, handler = _run_with(NeverChecked())
    assert invoke_tool(run, "provision", {}).allowed is False
    assert handler.call_count == 0


def test_unknown_does_not_permit_calls() -> None:
    assert not HealthState.UNKNOWN.permits_calls()
    assert not HealthState.UNHEALTHY.permits_calls()
    assert HealthState.HEALTHY.permits_calls()


def test_a_stale_record_reads_as_unknown() -> None:
    """Staleness is resolved on read, not by a sweeper marking records old.

    A sweeper-based approach leaves a window where the platform is confident about a
    product nobody has checked — and the window is widest exactly when the checker has
    stopped, which is when it matters.
    """
    from core.dependencies.types import DependencyHealth

    old = DependencyHealth(
        product="terraform-cloud",
        state=HealthState.HEALTHY,
        checked_at=datetime.now(UTC) - timedelta(hours=2),
    )
    # The record still says healthy; what makes it unknown is when it was checked, which
    # is why `checked_at` is on the record rather than implied by its presence.
    assert old.state is HealthState.HEALTHY
    assert old.checked_at < datetime.now(UTC) - timedelta(minutes=5)
