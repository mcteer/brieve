# SPDX-License-Identifier: Apache-2.0
"""Flapping must not produce a resume storm (FR-006, D9).

Recovery is hysteretic and failure is not, and the asymmetry is the whole point. Marking
unhealthy fast costs a suspension the sweeper resolves. Marking healthy fast resumes every
waiting run into a product that fails again — and each cycle spends real budget against
each run's maximum duration, so a flapping dependency would exhaust runs rather than
delaying them.
"""

from __future__ import annotations

from core.dependencies.store import DEFAULT_RECOVERY_THRESHOLD
from core.dependencies.types import HealthState


class Hysteresis:
    """The transition rule, exercised without a database.

    Mirrors `PostgresDependencyStore.record_probe` — the store has its own enclave rows;
    this is about the rule those rows would be checking.
    """

    def __init__(self, threshold: int = DEFAULT_RECOVERY_THRESHOLD) -> None:
        self.threshold = threshold
        self.successes = 0
        self.state = HealthState.UNKNOWN

    def probe(self, reachable: bool) -> HealthState:
        if not reachable:
            self.successes = 0
            self.state = HealthState.UNHEALTHY
        else:
            self.successes += 1
            self.state = (
                HealthState.HEALTHY if self.successes >= self.threshold else HealthState.UNHEALTHY
            )
        return self.state


def test_one_failure_is_enough_to_stop_calling_a_product() -> None:
    h = Hysteresis()
    for _ in range(DEFAULT_RECOVERY_THRESHOLD):
        h.probe(True)
    assert h.state is HealthState.HEALTHY

    assert h.probe(False) is HealthState.UNHEALTHY


def test_recovery_requires_consecutive_successes() -> None:
    h = Hysteresis()
    for i in range(DEFAULT_RECOVERY_THRESHOLD - 1):
        assert h.probe(True) is HealthState.UNHEALTHY, f"healthy after only {i + 1} successes"
    assert h.probe(True) is HealthState.HEALTHY


def test_flapping_never_reaches_healthy() -> None:
    """The failure this exists to prevent: alternate up/down never resumes anything.

    Without hysteresis, every other probe would mark the product healthy and the sweeper
    would resume every waiting run into the next failure.
    """
    h = Hysteresis()
    for _ in range(20):
        h.probe(True)
        h.probe(False)
    assert h.state is HealthState.UNHEALTHY


def test_a_single_success_after_failure_does_not_restore() -> None:
    h = Hysteresis()
    h.probe(False)
    assert h.probe(True) is HealthState.UNHEALTHY, (
        "one success after a failure restored the product, which is the resume storm"
    )
