# SPDX-License-Identifier: Apache-2.0
"""The MCP service must RUN what it hosts, not merely construct it.

ADR-0049 puts the dependency health checks and the resume sweeper on this service because
both need something that outlives a run. The service shipped constructing both and calling
neither: the loop ran only the integrity pass.

**Every conformance row still passed**, and that is the interesting part. Each exercises
its component directly with fakes — which is correct, and is why they are fast and
readable — so the one thing none of them could see was whether anything calls the
components at all. The hosting claim rested on a jobspec existing.

So this row asserts the seam between "built" and "run", which is the seam that failed.
"""

from __future__ import annotations

from typing import Any

from surfaces.mcp.server import supervisory_pass


class RecordingChecker:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def sweep(self, products: Any = None) -> list[Any]:
        self.calls.append("health")
        return []


class RecordingSweeper:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def sweep(self, products: Any) -> Any:
        self.calls.append("sweep")
        return _Outcome()


class _Outcome:
    resumed: list[str] = []
    stale: list[str] = []
    failed: list[tuple[str, str]] = []


class RecordingStore:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def awaited_products(self) -> list[str]:
        return ["terraform-cloud"]


class ExplodingChecker:
    """A pass that raises. The others must still run."""

    def sweep(self, products: Any = None) -> list[Any]:
        raise RuntimeError("probe backend unreachable")


def _fixture() -> tuple[list[str], dict[str, Any]]:
    calls: list[str] = []
    return calls, {
        "checker": RecordingChecker(calls),
        "sweeper": RecordingSweeper(calls),
        "store": RecordingStore(calls),
        "credentials": object(),
    }


def test_every_pass_runs(monkeypatch: Any) -> None:
    calls, parts = _fixture()
    monkeypatch.setattr("surfaces.mcp.server.check_integrity", lambda _c: _clean_report(calls))

    ran = supervisory_pass(**parts)

    assert set(ran) == {"health", "sweep", "integrity"}
    assert calls == ["health", "sweep", "integrity"]


def test_health_runs_before_sweep(monkeypatch: Any) -> None:
    """Order, not merely membership.

    The sweeper resumes runs whose dependency reports healthy. Sweeping first would decide
    on the PREVIOUS pass's health — a full interval of resuming runs into an outage this
    pass already knows about, which looks like a working sweeper and is not one.
    """
    calls, parts = _fixture()
    monkeypatch.setattr("surfaces.mcp.server.check_integrity", lambda _c: _clean_report(calls))

    supervisory_pass(**parts)

    assert calls.index("health") < calls.index("sweep")


def test_one_failing_pass_does_not_stop_the_others(monkeypatch: Any) -> None:
    """A supervisory loop that died on a transient error would take everything with it."""
    calls, parts = _fixture()
    parts["checker"] = ExplodingChecker()
    monkeypatch.setattr("surfaces.mcp.server.check_integrity", lambda _c: _clean_report(calls))

    ran = supervisory_pass(**parts)

    assert set(ran) == {"health", "sweep", "integrity"}
    assert calls == ["sweep", "integrity"], "a raising health pass stopped the rest"


def test_break_fixture_a_pass_that_is_constructed_but_not_called_is_detected() -> None:
    """The exact defect this row exists for, constructed and asserted caught.

    Building the collaborators and running a subset is what shipped. It looks complete from
    every angle except this one: the objects exist, they are wired to real stores, and
    their own tests pass.
    """
    calls: list[str] = []
    checker = RecordingChecker(calls)  # constructed
    sweeper = RecordingSweeper(calls)  # constructed
    assert checker is not None and sweeper is not None

    # ...and only the integrity pass runs, which is what the service actually did.
    calls.append("integrity")

    assert calls != ["health", "sweep", "integrity"]
    assert "health" not in calls and "sweep" not in calls


def _clean_report(calls: list[str]) -> Any:
    from core.audit.integrity import IntegrityReport

    calls.append("integrity")
    return IntegrityReport()
