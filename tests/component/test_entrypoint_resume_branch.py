# SPDX-License-Identifier: Apache-2.0
"""The entrypoint's resume branch (014 T015) — the integration this feature exists for.

`resume_run` shipped in 005 with five conformance properties asserted against it and **no
caller in `src/`**. The properties were true of the function and said nothing about the
platform, because nothing dispatched ever reached it. These rows assert the caller.

Hermetic, against in-memory providers, and that is a deliberate boundary rather than the
whole story: what a hermetic row can prove is that the branch honours each decision and
skips what it should. What it cannot prove is that any of it survives a real disruption —
that claim needs a scheduler killing a real allocation, and it lives in
`tests/conformance/durability/test_dispatched_resume.py`. Both, because either alone is the
shape this feature repairs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from core.audit.schema import AuditEventType
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob, IntentRecord, ResultRecord, RunOutcome
from core.registry.memory import ToolRegistry
from core.run import RESUME_ATTEMPT_CAP, RunState
from core.threads.context import RESULT_KEY
from surfaces.dispatch.entrypoint import resume_dispatched_run
from tests.component.conftest import CountingHandler
from tests.harness import capture_audit, durability_grant, fake_identity_fabric, frozen_clock


def _prepared(
    *,
    steps: int = 3,
    reached: int = 0,
    grant_duration: timedelta = timedelta(hours=1),
    resume_count: int = 0,
    save_grant: bool = True,
    open_intent_at: int | None = None,
    tool_name: str = "echo",
) -> dict[str, Any]:
    """A disrupted run, mid-flight, exactly as an allocation would have left it."""
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={tool_name}, duration=grant_duration)
    if save_grant:
        provider.save_grant(grant)

    handler = CountingHandler()
    registry = ToolRegistry()
    registry.register(tool_name, handler)

    # Steps 0..reached-1 completed their brackets before the disruption.
    for step in range(reached):
        key = f"run-1:step-{step}"
        provider.record_intent(
            IntentRecord(
                run_id="run-1",
                idempotency_key=key,
                step_index=step,
                tool_name=tool_name,
                recorded_at=datetime.now(UTC),
            )
        )
        provider.record_result(
            ResultRecord(
                run_id="run-1",
                idempotency_key=key,
                step_index=step,
                recorded_at=datetime.now(UTC),
            )
        )

    if open_intent_at is not None:
        # An intent with no result: the interrupted case, and the only thing re-observation
        # has to resolve.
        provider.record_intent(
            IntentRecord(
                run_id="run-1",
                idempotency_key=f"run-1:step-{open_intent_at}",
                step_index=open_intent_at,
                tool_name=tool_name,
                recorded_at=datetime.now(UTC),
            )
        )

    provider.save(
        CheckpointBlob(
            blob_id="run-1",
            payload={"step": max(reached - 1, 0)},
            correlation_id="corr-1",
            grant_id=grant.grant_id,
            step_index=max(reached - 1, 0),
            written_by="alloc-1",
            resume_count=resume_count,
        )
    )

    audit = capture_audit()
    return {
        "durability": provider,
        "audit_sink": audit,
        "registry": registry,
        "identity_fabric": fake_identity_fabric(
            subject_user_id=grant.subject_user_id,
            tool_names={tool_name},
            ceiling_tools={tool_name},
        ),
        "clock": clock,
        "correlation_id": "corr-1",
        "blob_id": "run-1",
        "tenant_id": "tenant-1",
        "holder_identity": "alloc-2",
        "observers": {},
        "depends_on": {},
        "total_steps": steps,
        "tools": [tool_name],
        "invoke_tools": False,
        "_handler": handler,
        "_grant": grant,
        "_audit": audit,
    }


def _call(prepared: dict[str, Any], **overrides: Any) -> int:
    kwargs = {k: v for k, v in prepared.items() if not k.startswith("_")}
    kwargs.update(overrides)
    return resume_dispatched_run(**kwargs)


def _events(audit: Any) -> list[tuple[str, dict[str, Any]]]:
    return [(str(e.event_type), dict(e.payload)) for e in audit.all_entries()]


def _result(provider: Any) -> dict[str, Any]:
    stored = provider.load("run-1")
    assert stored is not None
    return dict(stored.payload.get(RESULT_KEY) or {})


def test_a_resumed_run_does_not_re_execute_completed_steps() -> None:
    """The headline of SC-001, from the caller's side.

    Steps 0 and 1 closed their brackets before the disruption; the checkpoint records step 1.
    The revived run must run 2 only. A resume that re-ran 0 and 1 would be the exactly-once
    violation this whole feature is here to make demonstrable.
    """
    prepared = _prepared(steps=3, reached=2)

    assert _call(prepared) == 0

    stored = prepared["durability"].load("run-1")
    assert stored is not None
    assert stored.outcome is not None
    assert stored.outcome.state == RunState.COMPLETED.value
    assert _result(prepared["durability"])["steps"] == [2], "only the pending step ran"


def test_a_step_whose_result_landed_but_whose_checkpoint_did_not_is_not_re_run() -> None:
    """The window between `record_result` and the checkpoint save — an exactly-once violation.

    **Caught by the dispatched exactly-once row in CI, non-deterministically**, because it
    needs the kill to land inside that window. This reproduces it on purpose, so the property
    stops depending on timing: a run reaching step 2, whose bracket for step 2 CLOSED, and
    whose checkpoint still says step 1.

    That step is invisible to the two inputs the resume decision used to have. Its bracket is
    closed, so re-observation never sees it — `completed_steps` and `pending_steps` are drawn
    from OPEN intents. And the checkpoint names step 1, so `step < resume_from` is false at
    exactly index 2. The resumed run therefore re-executed an effect that had already
    happened, and it looked identical to a first run.

    The closed bracket is the stronger record: written by the step at the moment it finished,
    where the checkpoint is written afterwards and can be lost.
    """
    # reached=3 closes brackets for steps 0, 1, AND 2 ...
    prepared = _prepared(steps=4, reached=3)
    provider = prepared["durability"]
    stored = provider.load("run-1")
    assert stored is not None
    # ... while the checkpoint lags at step 1, exactly as a kill in the window would leave it.
    provider.save(stored.model_copy(update={"step_index": 1, "payload": {"step": 1}}))

    assert _call(prepared) == 0

    assert _result(provider)["steps"] == [3], (
        "step 2's result was already recorded, so re-running it repeats an effect that "
        "already happened — the exactly-once violation this row exists to pin down"
    )


def test_a_resume_with_no_checkpoint_stops_and_never_starts_fresh() -> None:
    """A missing checkpoint means we cannot know what already happened.

    Guessing is the failure re-observation exists to prevent, so this refuses. The dangerous
    reading — "no checkpoint, so start over" — would silently re-execute every effect the run
    had already produced, which is indistinguishable from a successful resume in every record
    except the ones counting effects.
    """
    prepared = _prepared(steps=3, reached=0)
    prepared["durability"] = InMemoryDurabilityProvider()

    assert _call(prepared) == 1

    events = _events(prepared["_audit"])
    assert events[0][0] == AuditEventType.RUN_RESUMED
    assert events[0][1]["outcome"] == "stopped"
    assert events[0][1]["reason"] == "checkpoint_missing"


def test_a_missing_grant_refuses_rather_than_assuming_consent() -> None:
    """FR-013: a missing grant is not "no consent required".

    Before 014 this was not merely unhandled but *unreachable* — nothing persisted a grant,
    so every dispatched resume would have arrived here. The row exists so the fail-closed
    direction is asserted rather than inherited from a bug being fixed.
    """
    prepared = _prepared(steps=3, reached=1, save_grant=False)

    assert _call(prepared) == 1

    kinds = [kind for kind, _ in _events(prepared["_audit"])]
    payloads = [p for _, p in _events(prepared["_audit"])]
    assert AuditEventType.RUN_RESUMED in kinds
    assert payloads[0]["reason"] == "grant_missing"
    # Nothing ran. A refusal that executed a step first would be a refusal in name only.
    assert prepared["_handler"].call_count == 0


def test_lapsed_consent_stops_the_run_before_any_step() -> None:
    """US4 through the caller: the bound is honoured, recorded, and terminal.

    Exit zero, deliberately: a bound is an ending, not a crash. An allocation that failed
    here would make every expired grant look like an outage to whoever reads allocation
    states.
    """
    prepared = _prepared(steps=3, reached=1, grant_duration=timedelta(seconds=1))
    prepared["clock"].advance(timedelta(minutes=5))

    assert _call(prepared) == 0

    stored = prepared["durability"].load("run-1")
    assert stored is not None
    assert stored.outcome is not None
    assert stored.outcome.state == RunState.STOPPED.value
    assert stored.outcome.stop_reason == "grant_expired"
    assert prepared["_handler"].call_count == 0

    payload = _events(prepared["_audit"])[0][1]
    assert payload["outcome"] == "stopped"
    assert payload["reason"] == "grant_expired"


def test_an_exhausted_revival_budget_stops_terminally() -> None:
    """The cap, reached through the entrypoint rather than the library.

    Terminal and recorded, and the run does no work: a revival past the bound must not be a
    revival that happens to also stop afterwards.
    """
    prepared = _prepared(steps=3, reached=1, resume_count=RESUME_ATTEMPT_CAP)

    assert _call(prepared) == 0

    stored = prepared["durability"].load("run-1")
    assert stored is not None
    assert stored.outcome is not None
    assert stored.outcome.stop_reason == "resume_attempts_exhausted"
    assert prepared["_handler"].call_count == 0


def test_the_revival_is_recorded_before_its_consequences() -> None:
    """FR-017's ordering, which is what makes the trail readable.

    `RUN_RESUMED` first, then everything the revival caused. An investigator reading in order
    otherwise sees a run doing work with no record of why it was running at all.
    """
    prepared = _prepared(steps=2, reached=1)

    assert _call(prepared) == 0

    kinds = [kind for kind, _ in _events(prepared["_audit"])]
    assert kinds[0] == AuditEventType.RUN_RESUMED
    # And the revival's own record precedes the authority issued to carry it out.
    assert AuditEventType.AUTHORITY_ISSUED in kinds
    assert kinds.index(AuditEventType.RUN_RESUMED) < kinds.index(AuditEventType.AUTHORITY_ISSUED)


def test_the_attempt_number_is_one_based_and_counts_this_revival() -> None:
    """ "attempt 3 of 5" without arithmetic — the reason the payload carries a number."""
    prepared = _prepared(steps=2, reached=1, resume_count=2)

    assert _call(prepared) == 0

    assert _events(prepared["_audit"])[0][1]["attempt"] == 3


def test_the_resumed_run_threads_the_count_into_every_checkpoint_it_writes() -> None:
    """The H1 wipe, from the caller's side.

    `save()` overwrites the whole row, so a per-step blob built without the count would reset
    the bound to zero on the first step after a revival — making the cap clear itself whenever
    any work happens. The stores also refuse to lower a count, so this is the second of two
    defences; asserted here because a caller that relies on the store's floor is a caller
    whose own arithmetic is wrong.
    """
    prepared = _prepared(steps=3, reached=1, resume_count=2)

    assert _call(prepared) == 0

    stored = prepared["durability"].load("run-1")
    assert stored is not None
    assert stored.resume_count == 3


def test_a_suspended_resume_files_an_index_row_and_exits_zero() -> None:
    """A suspension is a wait, not a failure.

    The index row is what the sweeper finds; without it the run sits suspended forever, which
    is the hang ADR-0049 removed a human to avoid — reached by the mechanism meant to prevent
    it. Exit zero because a failed allocation presents the wait as a crash.
    """
    from tests.harness import ScriptedObserver

    prepared = _prepared(steps=3, reached=1, open_intent_at=1, tool_name="terraform_apply")
    prepared["observers"] = {"terraform_apply": ScriptedObserver()}
    prepared["depends_on"] = {"terraform_apply": "terraform"}

    filed: list[dict[str, Any]] = []
    assert _call(prepared, record_suspension=lambda **kw: filed.append(kw)) == 0

    assert len(filed) == 1, "a suspension nobody indexed is a run the sweeper never finds"
    assert filed[0]["awaiting"] == "terraform", "the PRODUCT, never the tool name"
    assert filed[0]["run_id"] == "run-1"

    payload = _events(prepared["_audit"])[0][1]
    assert payload["outcome"] == "suspended"
    assert payload["reason"] == "terraform"

    # Not terminal: the run must still be resumable when the dependency recovers.
    stored = prepared["durability"].load("run-1")
    assert stored is not None
    assert stored.outcome is None


def test_re_observation_skips_a_step_whose_effect_already_landed() -> None:
    """The open intent resolved as HAPPENED is skipped, not re-run (US2).

    This is the case a checkpoint cannot answer: the work landed and the bracket never closed,
    so only the product knows. Believing the checkpoint here would re-execute a
    non-repeatable effect.
    """
    from core.observation.types import ObservationOutcome
    from tests.harness import ScriptedObserver

    prepared = _prepared(steps=3, reached=1, open_intent_at=1)
    prepared["observers"] = {"echo": ScriptedObserver(default=ObservationOutcome.HAPPENED)}

    assert _call(prepared) == 0

    stored = prepared["durability"].load("run-1")
    assert stored is not None
    assert _result(prepared["durability"])["steps"] == [2], "step 1 landed; only 2 pending"


def test_re_observation_runs_a_step_whose_effect_did_not_land() -> None:
    """The other direction, and the one a completion-only assertion cannot tell apart.

    DID_NOT_HAPPEN means the step is genuinely pending, so it must run. A resume that skipped
    it would exit zero having silently dropped work — which reads as success everywhere
    except a count of effects.
    """
    from core.observation.types import ObservationOutcome
    from tests.harness import ScriptedObserver

    prepared = _prepared(steps=3, reached=1, open_intent_at=1)
    prepared["observers"] = {"echo": ScriptedObserver(default=ObservationOutcome.DID_NOT_HAPPEN)}

    assert _call(prepared) == 0

    stored = prepared["durability"].load("run-1")
    assert stored is not None
    assert _result(prepared["durability"])["steps"] == [1, 2]


def test_a_terminal_run_is_not_re_entered() -> None:
    """The edge case: a dispatch flagged as a resume whose run already finished.

    The library decides this from the terminal checkpoint; the row asserts the entrypoint
    honours it rather than starting the work again.
    """
    prepared = _prepared(steps=3, reached=3)
    provider = prepared["durability"]
    stored = provider.load("run-1")
    assert stored is not None
    provider.save(
        stored.model_copy(
            update={"outcome": RunOutcome(state=RunState.COMPLETED.value, stop_reason=None)}
        )
    )

    assert _call(prepared) == 0
    assert prepared["_handler"].call_count == 0
