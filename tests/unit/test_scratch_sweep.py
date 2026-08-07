# SPDX-License-Identifier: Apache-2.0
"""The orphan sweep (042, T015, FR-023).

**This exists because "always destroyed" is a claim.** The impact check destroys its scratch
policies in a `finally`, which covers the ordinary path and every failing path — and cannot
cover a process that stops existing between the write and the `finally`. SC-010 says zero
scratch policies survive a killed run *once the sweep has run*, and that clause is only
honest if something does the running.
"""

from __future__ import annotations

from typing import Any

from core.audit.sink import InMemoryAuditSink
from surfaces.mcp.scratch_sweep import sweep_scratch_policies


def _sweep(
    names: list[str],
    *,
    live: set[str] | None = None,
    audit: Any = None,
    failing: set[str] | None = None,
) -> tuple[Any, list[str]]:
    deleted: list[str] = []
    blocked = failing or set()

    def _delete(path: str) -> None:
        name = path.rsplit("/", 1)[-1]
        if name in blocked:
            raise RuntimeError("vault refused the delete")
        deleted.append(name)

    outcome = sweep_scratch_policies(
        list_policies=lambda: names,
        delete_policy=_delete,
        is_live=lambda run_id: run_id in (live or set()),
        audit=audit,
        tenant_id="tenant-test",
    )
    return outcome, deleted


def test_an_orphan_from_a_dead_run_is_removed() -> None:
    """The case the sweep exists for."""
    outcome, deleted = _sweep(["scratch-agent-corr-1-current", "scratch-agent-corr-1-proposed"])

    assert sorted(deleted) == ["scratch-agent-corr-1-current", "scratch-agent-corr-1-proposed"]
    assert outcome.examined == 2


def test_a_live_runs_policies_are_left_alone() -> None:
    """The difference between a sweep and a race.

    An impact check in flight IS a scratch policy whose run is alive. Deleting it would break
    the measurement it was created for and produce a capability set that never existed —
    a sweeper corrupting the instrument it was written to tidy up after.
    """
    outcome, deleted = _sweep(
        ["scratch-agent-corr-live-proposed", "scratch-agent-corr-dead-proposed"],
        live={"corr-live"},
    )

    assert deleted == ["scratch-agent-corr-dead-proposed"]
    assert outcome.live_skipped == ("scratch-agent-corr-live-proposed",)


def test_nothing_outside_the_measurement_namespace_is_touched() -> None:
    """A sweep is a delete loop; what bounds it is the whole safety argument.

    The Vault grant refuses anything outside `scratch-agent-*` regardless, but a sweeper that
    relied on that would be one ACL edit away from deleting the estate's policies.
    """
    outcome, deleted = _sweep(["agent-ceiling", "harness-database", "scratch-agent-c1-current"])

    assert deleted == ["scratch-agent-c1-current"]
    assert outcome.examined == 1, "policies outside the namespace are not even examined"


def test_a_run_id_containing_a_hyphen_is_recovered_correctly() -> None:
    """`corr-042-ceiling` is a real correlation id in this repository.

    Splitting the stem from the LEFT would attribute the policy to run `corr`, find no such
    run, and — worse in the other direction — a live-run check keyed on the wrong id would
    skip an orphan forever or delete a live measurement.
    """
    outcome, deleted = _sweep(
        ["scratch-agent-corr-042-ceiling-proposed"], live={"corr-042-ceiling"}
    )

    assert deleted == []
    assert outcome.live_skipped == ("scratch-agent-corr-042-ceiling-proposed",)


def test_one_stuck_policy_does_not_end_the_pass() -> None:
    """An orphan left because an unrelated one was stuck is one the next pass must find again."""
    _, deleted = _sweep(
        [
            "scratch-agent-c1-current",
            "scratch-agent-c2-current",
            "scratch-agent-c3-current",
        ],
        failing={"scratch-agent-c2-current"},
    )

    assert deleted == ["scratch-agent-c1-current", "scratch-agent-c3-current"]


def test_the_removal_is_audited() -> None:
    """A policy vanishing from the trust fabric with no record is indistinguishable, later,
    from one that was never created."""
    audit = InMemoryAuditSink()

    _sweep(["scratch-agent-c1-current"], audit=audit)

    entries = [
        e for e in audit.all_entries() if e.payload.get("code") == "orphaned_scratch_policy_removed"
    ]
    assert entries, "the sweep removed a policy and said nothing"
    assert entries[0].payload["policies"] == ["scratch-agent-c1-current"]


def test_a_pass_that_removes_nothing_writes_nothing() -> None:
    """A quiet sweep is the normal case; an event per pass would bury the ones that matter."""
    audit = InMemoryAuditSink()

    _sweep(["scratch-agent-c1-current"], live={"c1"}, audit=audit)

    assert not [
        e for e in audit.all_entries() if e.payload.get("code") == "orphaned_scratch_policy_removed"
    ]
