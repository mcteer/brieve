# SPDX-License-Identifier: Apache-2.0
"""Shared assertions for the seven durability rows.

Extracted so each row's **break fixture** can exercise the same assertion against a
deliberately weakened arrangement. A gate nobody has watched fail is a gate nobody
knows works (FR-014).
"""

from __future__ import annotations

from core.durability.types import CheckpointBlob, DurabilityProvider
from core.observation.types import ObservationOutcome
from core.run import RunState

FORBIDDEN_IN_CHECKPOINTS = ("credential", "token", "secret", "password", "run_salt")


def assert_resumes_from_checkpoint(blob: CheckpointBlob | None, *, expected_step: int) -> None:
    assert blob is not None, "no checkpoint: nothing to resume from"
    assert blob.step_index == expected_step, "resumed from the wrong point"


def assert_executed_exactly_once(counts: dict[str, int], step: str) -> None:
    """Across the whole run, not per segment — a per-segment count passes a replayer."""
    assert counts.get(step, 0) == 1, f"{step} executed {counts.get(step, 0)} times, expected 1"


def assert_no_credential_in_checkpoint(blob: CheckpointBlob) -> None:
    dumped = str(blob.model_dump()).lower()
    for token in FORBIDDEN_IN_CHECKPOINTS:
        assert token not in dumped, f"checkpoint contains {token!r}"


def assert_fresh_authority(before_id: str, after_id: str | None) -> None:
    assert after_id is not None, "resume manufactured no authority"
    assert after_id != before_id, "resume reused the pre-disruption credential"


def assert_superseded_is_rejected(provider: DurabilityProvider, run_id: str, stale: str) -> None:
    assert not provider.check_lease(run_id, stale), "a superseded holder still holds the lease"


def assert_parked(state: RunState, reason: str | None, *, expected_prefix: str) -> None:
    assert state is RunState.PARKED, f"expected PARKED, got {state}"
    assert reason is not None and reason.startswith(expected_prefix), (
        f"park reason {reason!r} does not start with {expected_prefix!r}"
    )


def assert_observation_decides(outcome: ObservationOutcome, *, repeated: bool) -> None:
    """The decision must match what was observed, in both directions."""
    if outcome is ObservationOutcome.HAPPENED:
        assert not repeated, "repeated a step observed to have already taken effect"
    elif outcome is ObservationOutcome.DID_NOT_HAPPEN:
        assert repeated, "skipped a step observed not to have taken effect"
    else:  # pragma: no cover - cannot-determine must park before reaching here
        raise AssertionError("cannot_determine must park, not resolve to a decision")


def assert_same_step_same_key(first: str, second: str) -> None:
    assert first == second, "a retry of the same step produced a different identity"


def assert_evidence_spans_disruption(blob: CheckpointBlob, correlation_id: str) -> None:
    assert blob.correlation_id == correlation_id, "the join key did not survive the boundary"
