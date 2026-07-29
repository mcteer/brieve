# SPDX-License-Identifier: Apache-2.0
"""US3 — a thread is run state, so it survives the process that made it.

ADR-0034 asserts threads are persisted like any other run state. That claim had never been
tested against a real conversation, and it is the difference between run state and a cache
with an ADR describing it as something else.

The in-memory store cannot prove persistence — it *is* the process — so what these rows
prove is the contract: a store instance constructed fresh, with no shared objects, reads
back what a previous one wrote. Against Postgres that is process death; against the
in-memory store it is at least the absence of hidden per-instance state. The real
restart is the enclave row.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.threads.records import RunInput, ThreadRecord, TurnDisposition, TurnRecord
from core.threads.store import InMemoryThreadStore, new_thread_id, new_turn_id

TENANT = "tenant-test"


def _seed(store: InMemoryThreadStore) -> ThreadRecord:
    thread_id = new_thread_id()
    thread = ThreadRecord(
        thread_id=thread_id,
        correlation_id=f"corr-{thread_id}",
        subject_user_id="alice",
        tenant_id=TENANT,
        created_at=datetime.now(UTC),
    )
    store.create_thread(thread)
    store.append_turn(
        TurnRecord(
            turn_id=new_turn_id(),
            thread_id=thread.thread_id,
            tenant_id=TENANT,
            subject_user_id="alice",
            seq=-1,
            message="plan the migration",
            disposition=TurnDisposition.DISPATCHED,
            created_at=datetime.now(UTC),
            run_id="run-1",
        )
    )
    store.put_run_input(
        RunInput(run_id="run-1", message="plan the migration", created_at=datetime.now(UTC))
    )
    return thread


def test_a_second_store_over_the_same_state_reads_the_same_thread() -> None:
    """The contract both implementations sign: nothing lives in the instance."""
    first = InMemoryThreadStore()
    thread = _seed(first)

    # Same underlying state, a different store object — the closest the in-memory
    # implementation gets to a restart.
    second = InMemoryThreadStore(
        threads=first.threads, turns=first.turns, run_inputs=first.run_inputs
    )

    reread = second.get_thread(thread_id=thread.thread_id, tenant_id=TENANT)
    assert reread == thread
    assert [t.message for t in second.turns_of(thread_id=thread.thread_id)] == [
        "plan the migration"
    ]
    assert second.get_run_input(run_id="run-1") is not None


def test_turn_order_survives() -> None:
    """`seq` is dense and stable, so a reread cannot reorder a conversation."""
    store = InMemoryThreadStore()
    thread = _seed(store)
    for i in range(3):
        store.append_turn(
            TurnRecord(
                turn_id=new_turn_id(),
                thread_id=thread.thread_id,
                tenant_id=TENANT,
                subject_user_id="alice",
                seq=-1,
                message=f"later {i}",
                disposition=TurnDisposition.DECLINED,
                created_at=datetime.now(UTC),
            )
        )

    reread = InMemoryThreadStore(
        threads=store.threads, turns=store.turns, run_inputs=store.run_inputs
    )

    assert [t.seq for t in reread.turns_of(thread_id=thread.thread_id)] == [0, 1, 2, 3]
    assert [t.message for t in reread.turns_of(thread_id=thread.thread_id)][-1] == "later 2"


def test_nothing_a_thread_holds_is_derived_at_write_time_from_a_run() -> None:
    """Run state is joined at READ time, so a restart cannot leave it stale.

    011's rule, inherited: the checkpoint is the one writer of a run's state. A turn that
    cached `state` would be a second record of it, and the two would disagree the moment
    a run progressed while the portal was down.
    """
    store = InMemoryThreadStore()
    thread = _seed(store)

    turn = store.turns_of(thread_id=thread.thread_id)[0]

    assert not hasattr(turn, "state")
    assert not hasattr(turn, "result")
