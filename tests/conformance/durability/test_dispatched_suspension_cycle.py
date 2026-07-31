# SPDX-License-Identifier: Apache-2.0
"""Suspension names what recovers it, and the sweeper acts on it (014 T023, SC-005/006).

**The 009 sweeper's first end-to-end demonstration.** 009 built the sweeper, the dependency
health store, and the suspended-run index; nothing ever filed a row in that index, so the
sweeper swept an empty candidate list and every property downstream of it was structurally
unreachable while looking wired. `record_suspension` had zero callers in `src/` and in
`tests/` until this feature.

The harness is D5's: an open `terraform_apply` intent resumes to `CANNOT_DETERMINE`, because
`TerraformApplyObserver` answers that by design — "terraform is fixture-backed here; nothing
to observe". No product is harmed and the trust fabric stays up, which is why D5 rejected
stopping the Vault container: that would take down the fabric the resume itself needs.

Note what the run does NOT need: `terraform_apply` in its ceiling. It never invokes the tool
— the row arranges the open intent — so only the PACK has to load, for its observer and its
product mapping.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from tests.conformance.durability import dispatch_harness as h

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def test_row_a_resumed_run_suspends_naming_the_product_and_is_indexed(conn: Any) -> None:
    """SC-005 and the write half of SC-006.

    Three things have to be true together, and each was independently broken before 014: the
    suspension names the **product** rather than the tool; the index row is **written**; and the
    allocation exits **zero**, because a suspension is a wait and a failed allocation presents
    it as a crash.
    """
    run_id = h.unique("suspend-cycle")
    dispatcher = h.dispatcher()
    h.arrange_disrupted(conn, run_id, tool_name="terraform_apply", step_index=1)

    # Down first, for the same reason the revival row below does it: this row asserts the
    # index row EXISTS, and the sweeper's job is to consume it. If the other row in this
    # file ran first under a random seed, it left terraform marked reachable, and the
    # sweeper could revive this run between the suspension and the read below — emptying
    # the index and failing a row about whether the index was ever written.
    #
    # An order-dependent row is a flake that will only ever fail in the lane, where the
    # seed is not the one anybody debugged with.
    h.mark_reachable("terraform", reachable=False)

    dispatcher.dispatch(
        **h.dispatch_args(
            run_id,
            resume=True,
            agent_definition_id="planner-agent",
            requested_tools=frozenset({"echo"}),
            subject_roles=frozenset({"operator"}),
            packs=frozenset({"terraform"}),
            invoke_tools=False,
            steps=4,
        )
    )
    alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(alloc)
    h.assert_entrypoint_ran(alloc)

    assert h.exit_code(alloc) == 0, (
        f"a suspended run failed its allocation (exit {h.exit_code(alloc)}) — a wait presented "
        f"as a crash leaves nothing for the sweeper to find. "
        f"nomad alloc logs -stderr {alloc} harness"
    )

    resumed = h.events(conn, run_id, "run_resumed")
    assert resumed, f"the revival was not recorded. nomad alloc logs -stderr {alloc} harness"
    assert resumed[-1]["outcome"] == "suspended"
    assert resumed[-1]["reason"] == "terraform", (
        f"the trail named {resumed[-1]['reason']!r} — a suspension must name the PRODUCT the "
        f"health checker watches, never the tool nobody watches (FR-008)"
    )

    indexed = h.suspended_rows(conn, run_id)
    assert len(indexed) == 1, (
        "the suspension was not indexed, so the sweeper will never find this run — it would "
        "wait forever, which is the hang ADR-0049 removed a human to avoid"
    )
    assert indexed[0]["awaiting"] == "terraform"
    # What the run needs to be ITSELF again, not a fresh run under its identity (T010a).
    assert indexed[0]["subject_roles"], "no roles indexed: the revival would refuse on scope"
    assert indexed[0]["packs"], "no packs indexed: the revival's observers would be missing"
    assert indexed[0]["steps"], "no steps indexed: the revival would complete trivially"

    # NOT terminal — the run must stay resumable for the recovery that has not happened yet.
    assert h.checkpoint(conn, run_id)["run_state"] is None


def test_row_the_sweeper_revives_a_suspended_run_when_its_product_recovers(conn: Any) -> None:
    """SC-006, the read half: recovery revives the run with no human action.

    The whole of ADR-0049's claim that consent to start a run is consent to finish it. Nobody
    presses anything: the health record changes, the sweeper's next pass notices, and the run
    is re-dispatched as itself.

    Slow by construction — the service sweeps on its own interval, and waiting for a real pass
    is the point rather than an inconvenience.
    """
    run_id = h.unique("sweep-revival")
    dispatcher = h.dispatcher()
    h.arrange_disrupted(conn, run_id, tool_name="terraform_apply", step_index=1)

    # Down first, so the sweeper cannot act on the row before the row exists.
    h.mark_reachable("terraform", reachable=False)

    dispatcher.dispatch(
        **h.dispatch_args(
            run_id,
            resume=True,
            agent_definition_id="planner-agent",
            requested_tools=frozenset({"echo"}),
            subject_roles=frozenset({"operator"}),
            packs=frozenset({"terraform"}),
            invoke_tools=False,
            steps=4,
        )
    )
    first = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(first)
    h.assert_entrypoint_ran(first)
    assert h.suspended_rows(conn, run_id), "nothing to sweep; the suspension was not indexed"

    # ---- the recovery. Nobody presses anything; a health record changes.
    #
    # Re-probed on a cadence rather than once, because health is deliberately PERISHABLE:
    # `state_of` folds staleness in, and a record older than `DEFAULT_STALE_AFTER` reads as
    # UNKNOWN, which is treated as unhealthy. That is 009 working — a product nobody has
    # checked recently is not a product known to be up.
    #
    # In production the health checker keeps the record fresh on its own interval. Here it
    # cannot: the mcp service's checker derives its products from its REGISTRY, and the
    # service loads no packs, so it has never heard of terraform. This loop stands in for the
    # probe that would exist if it had, and standing in for it is honest — what the row is
    # testing is the sweeper's response to a healthy product, not who wrote the record.
    h.mark_reachable("terraform", reachable=True)

    deadline = time.time() + 300
    while time.time() < deadline:
        if not h.suspended_rows(conn, run_id):
            break
        h.mark_reachable("terraform", reachable=True)
        time.sleep(5)
    else:
        pytest.fail(
            f"the sweeper did not act on {run_id} within 240s of terraform recovering. The "
            f"index row is still there. Check the mcp service: nomad alloc logs "
            f"$(nomad job status mcp | awk '/^[0-9a-f]{{8}} /{{print $1; exit}}')"
        )

    # The row is forgotten only after a SUCCESSFUL dispatch — `Sweeper._resume_one` forgets
    # last, precisely so a failed dispatch does not lose the run — so its absence is already
    # evidence that something was dispatched. But absence alone cannot tell a dispatch from
    # the other reason a row is dropped: a candidate whose checkpoint has moved on is
    # forgotten as stale. The trail is what separates them.
    #
    # Polled rather than read once. The revived allocation has to be placed and has to build
    # its environment before it records anything, and the index row disappears at dispatch —
    # so reading immediately asserts against a run that has not started.
    deadline = time.time() + 420
    revivals: list[dict[str, Any]] = []
    while time.time() < deadline:
        revivals = h.events(conn, run_id, "run_resumed")
        if len(revivals) >= 2:
            break
        time.sleep(5)

    assert len(revivals) >= 2, (
        f"the index row was dropped but no second revival reached the trail within 420s, so "
        f"the run was forgotten as stale rather than resumed. Got {revivals}"
    )
    assert revivals[1]["attempt"] == 2, (
        f"the swept revival is attempt 2 of this run, got {revivals[1]}. The count must survive "
        f"the dispatch that forgets the index row — which is why it lives on the checkpoint"
    )
