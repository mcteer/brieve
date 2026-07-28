# SPDX-License-Identifier: Apache-2.0
"""FR-008b — the trust fabric is a dependency of the mechanism that monitors dependencies.

Nothing else in this platform has this property. 009's health checker and sweeper reach
their store with credentials the trust fabric issues, so while the fabric is down they are
degraded too — and the component that would notice its recovery depends on the thing
recovering.

It terminates, in exactly one order::

    fabric returns → login succeeds → credentials obtained → health recorded → sweep

**These rows assert the order rather than the outcome**, because the outcome looks the same
whether the order was designed or lucky. What makes it safe is that each arrow is a
precondition of the next: a pass that records health has necessarily already obtained a
credential, so the sequence cannot be got wrong by writing the steps differently. The rows
below exist to catch someone making it *possible* to get wrong — by caching a credential
past the fabric's availability, say, or by recording health from something that did not
reach it.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.hooks.suspension import TRUST_FABRIC_DEPENDENCY
from surfaces.mcp.server import record_trust_fabric_health, supervisory_pass


class RecordingStore:
    """A store that can only be reached when the fabric is up, like the real one."""

    def __init__(self, *, fabric_up: bool) -> None:
        self.fabric_up = fabric_up
        self.events: list[str] = []
        self.probes: list[tuple[str, bool]] = []

    def _require_credential(self) -> None:
        if not self.fabric_up:
            # What actually happens: the store's credential comes from the fabric, so with
            # the fabric down there is no way to reach the store at all.
            raise RuntimeError("no database credential: trust fabric unreachable")

    def record_probe(self, *, product: str, reachable: bool, detail: str = "") -> Any:
        self._require_credential()
        self.events.append(f"record:{product}")
        self.probes.append((product, reachable))
        return None

    def awaited_products(self) -> list[str]:
        self._require_credential()
        self.events.append("sweep-query")
        return []


def test_health_is_recorded_before_the_sweep_reads_it() -> None:
    """Order, not membership. The sweeper acts on what the health pass just wrote.

    Reversed, the sweep would decide on the previous pass's health — a full interval of
    resuming runs into an outage this pass already knows about.
    """
    store = RecordingStore(fabric_up=True)

    record_trust_fabric_health(store)  # type: ignore[arg-type]
    store.awaited_products()

    assert store.events == [f"record:{TRUST_FABRIC_DEPENDENCY}", "sweep-query"]


def test_nothing_that_failed_to_reach_the_fabric_can_record_it_healthy() -> None:
    """FR-008c, and it is structural rather than a rule about who may call what.

    Marking the fabric healthy requires writing to a store whose credential only the fabric
    issues. A monitor that could not reach it cannot write anything — so the record stays
    untouched, staleness turns that into UNKNOWN, and unknown already refuses.
    """
    store = RecordingStore(fabric_up=False)

    with pytest.raises(RuntimeError):
        record_trust_fabric_health(store)  # type: ignore[arg-type]

    assert store.probes == [], "the fabric was marked healthy by something that never reached it"


def test_recovery_terminates_once_the_fabric_returns() -> None:
    """The whole circularity, run forwards.

    Down: nothing can be recorded, nothing resumes. Up: the credential is obtainable, so
    the record happens, so the sweep sees it. No step needs the previous one to have been
    *scheduled* correctly — it needs it to have *succeeded*, which is stronger.
    """
    store = RecordingStore(fabric_up=False)
    with pytest.raises(RuntimeError):
        record_trust_fabric_health(store)  # type: ignore[arg-type]
    assert store.events == []

    store.fabric_up = True
    record_trust_fabric_health(store)  # type: ignore[arg-type]
    store.awaited_products()

    assert store.events == [f"record:{TRUST_FABRIC_DEPENDENCY}", "sweep-query"]


def test_the_supervisory_pass_records_the_fabric_first() -> None:
    """The loop runs it, and runs it before the passes that depend on it."""

    class Checker:
        def sweep(self, products: Any = None) -> list[Any]:
            return []

    class Sweeper:
        def sweep(self, products: Any) -> Any:
            class _Outcome:
                resumed: list[str] = []
                stale: list[str] = []
                failed: list[tuple[str, str]] = []

            return _Outcome()

    store = RecordingStore(fabric_up=True)
    ran = supervisory_pass(
        checker=Checker(),  # type: ignore[arg-type]
        sweeper=Sweeper(),  # type: ignore[arg-type]
        store=store,  # type: ignore[arg-type]
        credentials=object(),  # type: ignore[arg-type]
    )

    assert ran.index("trust-fabric") < ran.index("sweep")
    assert (TRUST_FABRIC_DEPENDENCY, True) in store.probes
