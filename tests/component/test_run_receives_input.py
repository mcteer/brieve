# SPDX-License-Identifier: Apache-2.0
"""What a run receives: the message, and prior results as the bytes they were stored as.

SC-002 says "byte-identical", and this file is where that word is operationalized. The
comparison is on the **stored serialization**, not on parsed objects — a comparison on
parsed objects passes a reserialization that reorders keys today and passes one that drops
a key tomorrow, because nothing was ever comparing what was written.

These rows exercise `resolve_run_input` directly. That is deliberate and was a planning
finding: the in-process dispatcher runs work through `start_governed_run`, which has no
input parameter and does not grow one — the allocation's entrypoint is the only production
caller, and it is proven end-to-end by the enclave row. Testing the function is testing the
thing both paths share.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob
from core.threads.context import RESULT_KEY, resolve_run_input, serialize_result
from core.threads.records import RunInput
from core.threads.store import InMemoryThreadStore


def _record_result(durability: InMemoryDurabilityProvider, run_id: str, result: object) -> None:
    durability.save(
        CheckpointBlob(
            blob_id=run_id,
            payload={RESULT_KEY: result},
            correlation_id=run_id,
            step_index=0,
            written_by="test",
        )
    )


def test_a_run_receives_its_message() -> None:
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    store.put_run_input(
        RunInput(run_id="run-1", message="plan the migration", created_at=datetime.now(UTC))
    )

    resolved = resolve_run_input(run_id="run-1", store=store, durability=durability)

    assert resolved is not None
    assert resolved.message == "plan the migration"
    assert resolved.context == ()


def test_carried_context_is_byte_identical_to_what_was_recorded() -> None:
    """The row SC-002 names. Bytes, not objects."""
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    result = {"plan": ["step one", "step two"], "risk": "low", "count": 2}
    _record_result(durability, "run-earlier", result)
    store.put_run_input(
        RunInput(
            run_id="run-later",
            message="now apply it",
            context_run_ids=("run-earlier",),
            created_at=datetime.now(UTC),
        )
    )

    resolved = resolve_run_input(run_id="run-later", store=store, durability=durability)

    assert resolved is not None
    assert resolved.context == (("run-earlier", serialize_result(result)),)


def test_a_truncated_result_is_detected() -> None:
    """The break fixture, as a row: one byte short must not compare equal."""
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    result = {"plan": "migrate the workspace"}
    _record_result(durability, "run-earlier", result)
    store.put_run_input(
        RunInput(
            run_id="run-later",
            message="continue",
            context_run_ids=("run-earlier",),
            created_at=datetime.now(UTC),
        )
    )

    resolved = resolve_run_input(run_id="run-later", store=store, durability=durability)

    assert resolved is not None
    carried = resolved.context[0][1]
    assert carried != carried[:-1]
    assert carried == serialize_result(result)


def test_serialization_is_stable_across_key_order() -> None:
    """Two equal results must produce the same bytes.

    Without this, a byte-comparison would fail on a difference that means nothing, and
    someone would 'fix' it by comparing parsed objects — losing the property entirely.
    """
    assert serialize_result({"a": 1, "b": 2}) == serialize_result({"b": 2, "a": 1})


def test_context_is_ordered_as_the_input_recorded_it() -> None:
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    for name in ("run-a", "run-b", "run-c"):
        _record_result(durability, name, {"from": name})
    store.put_run_input(
        RunInput(
            run_id="run-later",
            message="continue",
            context_run_ids=("run-c", "run-b", "run-a"),
            created_at=datetime.now(UTC),
        )
    )

    resolved = resolve_run_input(run_id="run-later", store=store, durability=durability)

    assert resolved is not None
    assert [rid for rid, _ in resolved.context] == ["run-c", "run-b", "run-a"]


def test_an_unreadable_prior_result_is_omitted_not_faked() -> None:
    """A placeholder would make a run's input claim something no record supports."""
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    _record_result(durability, "run-present", {"ok": True})
    store.put_run_input(
        RunInput(
            run_id="run-later",
            message="continue",
            context_run_ids=("run-missing", "run-present"),
            created_at=datetime.now(UTC),
        )
    )

    resolved = resolve_run_input(run_id="run-later", store=store, durability=durability)

    assert resolved is not None
    assert [rid for rid, _ in resolved.context] == ["run-present"]


def test_a_run_without_a_thread_resolves_to_nothing_without_error() -> None:
    """Runs started through `start_run` behave exactly as they did before this feature."""
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()

    assert resolve_run_input(run_id="never-a-turn", store=store, durability=durability) is None


def test_a_prior_run_with_no_result_yet_is_omitted() -> None:
    store, durability = InMemoryThreadStore(), InMemoryDurabilityProvider()
    durability.save(
        CheckpointBlob(blob_id="run-running", payload={"step": 3}, correlation_id="run-running")
    )
    store.put_run_input(
        RunInput(
            run_id="run-later",
            message="continue",
            context_run_ids=("run-running",),
            created_at=datetime.now(UTC),
        )
    )

    resolved = resolve_run_input(run_id="run-later", store=store, durability=durability)

    assert resolved is not None and resolved.context == ()


def test_the_result_key_matches_the_surface_that_writes_it() -> None:
    """Two definitions, one value — asserted so the duplication cannot drift silently.

    `core` cannot import `surfaces`, so the reserved key is declared in both places. That
    is a deliberate duplication with a guard rather than an accident: if these ever
    diverge, every run's result becomes unreadable by the thing that carries it forward,
    and nothing else would notice.
    """
    from surfaces.api.runs import RESULT_KEY as SURFACE_RESULT_KEY

    assert RESULT_KEY == SURFACE_RESULT_KEY
