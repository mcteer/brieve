# SPDX-License-Identifier: Apache-2.0
"""Resolved by asking, not assuming — against live Vault, both directions (014 T020).

FR-006a and clarify Q3 ask for the strongest available form of US2: not a scripted observer
agreeing with the test that wrote it, but the **shipped** `VaultWriteObserver` reading the
**real** Vault and deciding. So each direction arranges the product's actual state first, and
the run is told nothing.

Why both directions, always together: each alone passes against a broken implementation.
"always skip" satisfies the landed case and silently drops work in the other; "always run"
satisfies the not-landed case and re-executes a non-repeatable effect. The pair is the claim.

Order-sensitive by nature, and each direction cleans up the state it arranged — the observer's
answer is a fact about Vault, so a leftover key from one direction is the other direction's
wrong answer.
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.conformance.durability import dispatch_harness as h

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: Where the disruption left the run. Steps 0 and 1 are behind the checkpoint mark; step 1
#: holds the open intent, so it is the one re-observation has to decide about.
INTERRUPTED_AT = 1
TOTAL_STEPS = 4


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


def _resume_args(run_id: str) -> dict[str, Any]:
    return h.dispatch_args(
        run_id,
        resume=True,
        agent_definition_id="vault-agent",
        requested_tools=frozenset({"vault_write"}),
        subject_roles=frozenset({"vault-operator"}),
        packs=frozenset({"vault"}),
        invoke_tools=True,
        steps=TOTAL_STEPS,
    )


def _arrange(conn: Any, run_id: str) -> str:
    h.arrange_disrupted(
        conn,
        run_id,
        tool_name="vault_write",
        step_index=INTERRUPTED_AT,
        scope_tools=("vault_write",),
        definition="vault-agent",
    )
    return h.step_key(run_id, INTERRUPTED_AT, "vault_write")


def test_row_an_interrupted_write_that_landed_is_not_re_executed(conn: Any) -> None:
    """HAPPENED, decided by Vault: the step is skipped.

    This is the case a checkpoint cannot answer. The effect landed and the bracket never
    closed, so the run's own records say only "we were about to". Re-running here would repeat
    a non-repeatable write — the exact failure the bracket exists to prevent.
    """
    run_id = h.unique("reobserve-landed")
    key = _arrange(conn, run_id)
    h.arrange_effect_landed(key)
    try:
        dispatcher = h.dispatcher()
        dispatcher.dispatch(**_resume_args(run_id))
        alloc = h.allocation_of(h.job_of(dispatcher, run_id))
        h.wait_dead(alloc)
        h.assert_entrypoint_ran(alloc)

        assert h.checkpoint(conn, run_id)["run_state"] == "completed", (
            f"the resumed run did not finish. nomad alloc logs -stderr {alloc} harness"
        )
        # Steps 2 and 3 only. Step 1's effect was observed to have landed, so it is skipped;
        # steps 0 and 1 sit behind the checkpoint mark.
        assert h.tool_invocations(conn, run_id) == TOTAL_STEPS - INTERRUPTED_AT - 1, (
            f"expected {TOTAL_STEPS - INTERRUPTED_AT - 1} invocations after the revival — the "
            f"interrupted step's effect was already in Vault and must not have been repeated"
        )
    finally:
        h.clear_effect(key)


def test_row_an_interrupted_write_that_did_not_land_proceeds(conn: Any) -> None:
    """DID_NOT_HAPPEN, decided by Vault: the step runs.

    The direction a completion-only assertion cannot see. A resume that skipped here would
    exit successfully having silently dropped the work, which reads as success everywhere
    except a count of effects — and is why the row counts effects.
    """
    run_id = h.unique("reobserve-absent")
    key = _arrange(conn, run_id)
    # Explicitly cleared rather than merely assumed absent: a leftover key from a previous run
    # of the sibling row above would make Vault answer HAPPENED, and this row would then be
    # asserting the opposite of what it says.
    h.clear_effect(key)

    dispatcher = h.dispatcher()
    dispatcher.dispatch(**_resume_args(run_id))
    alloc = h.allocation_of(h.job_of(dispatcher, run_id))
    h.wait_dead(alloc)
    h.assert_entrypoint_ran(alloc)

    assert h.checkpoint(conn, run_id)["run_state"] == "completed", (
        f"the resumed run did not finish. nomad alloc logs -stderr {alloc} harness"
    )
    # Steps 1, 2 and 3: the interrupted one proceeds because nothing in Vault says it happened.
    assert h.tool_invocations(conn, run_id) == TOTAL_STEPS - INTERRUPTED_AT, (
        f"expected {TOTAL_STEPS - INTERRUPTED_AT} invocations — the interrupted step's effect "
        f"was NOT in Vault, so it was still pending and had to run"
    )
