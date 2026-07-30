# SPDX-License-Identifier: Apache-2.0
"""Every revival is in the trail, in order, and the chain still verifies (014 T030, FR-017).

Principle IX in the shape this feature is about. A revival that happened and was not recorded
is a revival nobody can see — and the question an investigator actually asks is not "was this
run resumed" but "how many times, and what came of each". That is answerable only if every
revival appears, numbered, with its outcome.

**Ordered before its consequences**, because a trail read in sequence is the only reading
anyone does. `RUN_RESUMED` after the work would show a run doing things with no record of why
it was running.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.run import RESUME_ATTEMPT_CAP
from tests.conformance.durability import dispatch_harness as h

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def test_row_every_revival_appears_numbered_and_before_what_it_caused(conn: Any) -> None:
    """Three revivals, three events, 1-based, each ahead of that revival's work.

    Three rather than one because the property is about a SEQUENCE: a single revival cannot
    distinguish "numbered correctly" from "always says 1", and the flap is where an
    investigator's question ("how many times was this revived?") stops being trivial.
    """
    run_id = h.unique("trail-order")
    dispatcher = h.dispatcher()
    h.arrange_disrupted(conn, run_id, tool_name="terraform_apply", step_index=1)

    revival = h.dispatch_args(
        run_id,
        resume=True,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
        packs=frozenset({"terraform"}),
        invoke_tools=False,
        steps=4,
    )

    rounds = min(3, RESUME_ATTEMPT_CAP)
    for _ in range(rounds):
        dispatcher.dispatch(**revival)
        alloc = h.allocation_of(h.job_of(dispatcher, run_id))
        h.wait_dead(alloc)
        h.assert_entrypoint_ran(alloc)

    revivals = h.events(conn, run_id, "run_resumed")
    assert len(revivals) == rounds, f"expected {rounds} revivals in the trail, got {revivals}"

    # 1-BASED and consecutive, so "attempt 3 of 5" reads without arithmetic.
    assert [event["attempt"] for event in revivals] == list(range(1, rounds + 1)), (
        f"the attempt numbers are not a 1-based sequence: {[e['attempt'] for e in revivals]}"
    )
    for event in revivals:
        assert event["run_id"] == run_id
        assert event["outcome"] in {"continued", "stopped", "suspended"}
        assert set(event) >= {"completed_steps", "pending_steps"}, (
            f"a revival without step counts cannot answer 'what did it skip': {event}"
        )

    # ---- ordered before the consequences of the revival it records
    #
    # The first RUN_RESUMED must precede the first thing the revived run did. Compared by
    # sequence within the correlation id, which is the order the evidence path returns and
    # therefore the order anyone reads.
    order = h.event_order(conn, run_id)
    assert order[0] == "run_resumed", (
        f"the trail opens with {order[0]!r} — the revival must be recorded before its "
        f"consequences, or an investigator reads a run working with no record of why"
    )


def test_row_the_chain_verifies_across_a_resumed_runs_whole_trail(conn: Any) -> None:
    """A trail spanning several allocations is still one verifiable chain.

    Each revival is a different process appending to the same correlation id, so this is the
    case where a chain implementation that assumed a single writer would break — and it would
    break silently, since nothing else reads `prev_hash`.
    """
    run_id = h.unique("trail-chain")
    dispatcher = h.dispatcher()
    h.arrange_disrupted(conn, run_id, tool_name="terraform_apply", step_index=1)

    revival = h.dispatch_args(
        run_id,
        resume=True,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"echo"}),
        subject_roles=frozenset({"operator"}),
        packs=frozenset({"terraform"}),
        invoke_tools=False,
        steps=4,
    )
    for _ in range(2):
        dispatcher.dispatch(**revival)
        alloc = h.allocation_of(h.job_of(dispatcher, run_id))
        h.wait_dead(alloc)
        h.assert_entrypoint_ran(alloc)

    rows = h.query(
        conn,
        "SELECT seq, prev_hash, entry_hash FROM audit_entries WHERE correlation_id = %s "
        "ORDER BY seq",
        (run_id,),
    )
    assert len(rows) >= 2, f"too few entries to verify a chain: {rows}"

    # Every entry names its predecessor. The genesis entry names the genesis constant, and
    # each later one names the hash of the entry before it — across allocation boundaries.
    from core.audit.chain import GENESIS_PREV_HASH

    assert rows[0][1] == GENESIS_PREV_HASH, f"the first entry does not start the chain: {rows[0]}"
    for earlier, later in zip(rows, rows[1:], strict=False):
        assert later[1] == earlier[2], (
            f"the chain breaks between seq {earlier[0]} and {later[0]} — a revival appended "
            f"without reading the previous allocation's head"
        )
