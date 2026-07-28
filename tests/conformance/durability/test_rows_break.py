# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — each durability row fails when its guarantee is weakened (FR-014).

**These tests pass on a clean tree.** Each constructs the weakened arrangement and
asserts the row's shared assertion *raises*. A gate nobody has watched fail is a gate
nobody knows works, and prose claiming "this would fail if..." is not evidence.

Following 004's pattern: self-verifying rather than a red test left in the suite.
"""

from __future__ import annotations

import pytest

from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob
from core.observation.types import ObservationOutcome
from core.run import RunState
from tests.conformance.durability import rows


def test_kill_resume_row_fails_without_a_checkpoint() -> None:
    with pytest.raises(AssertionError, match="nothing to resume"):
        rows.assert_resumes_from_checkpoint(None, expected_step=2)


def test_kill_resume_row_fails_when_resuming_from_the_wrong_point() -> None:
    blob = CheckpointBlob(blob_id="b", step_index=0)
    with pytest.raises(AssertionError, match="wrong point"):
        rows.assert_resumes_from_checkpoint(blob, expected_step=2)


def test_exactly_once_row_fails_when_a_step_is_replayed() -> None:
    """The weakening this catches: resume re-running work it already did."""
    with pytest.raises(AssertionError, match="executed 2 times"):
        rows.assert_executed_exactly_once({"provision": 2}, "provision")


def test_no_credential_row_fails_when_a_checkpoint_carries_one() -> None:
    leaky = CheckpointBlob(blob_id="b", payload={"authority_token": "anything"})
    with pytest.raises(AssertionError, match="token"):
        rows.assert_no_credential_in_checkpoint(leaky)


def test_reauthenticate_row_fails_when_the_credential_is_reused() -> None:
    with pytest.raises(AssertionError, match="reused the pre-disruption credential"):
        rows.assert_fresh_authority("cred-1", "cred-1")


def test_reauthenticate_row_fails_when_no_authority_is_manufactured() -> None:
    with pytest.raises(AssertionError, match="manufactured no authority"):
        rows.assert_fresh_authority("cred-1", None)


def test_fencing_row_fails_when_a_superseded_holder_still_holds() -> None:
    provider = InMemoryDurabilityProvider()
    provider.acquire_lease("run-1", "alloc-old")  # never superseded — the weakening
    with pytest.raises(AssertionError, match="still holds the lease"):
        rows.assert_superseded_is_rejected(provider, "run-1", "alloc-old")


def test_parking_row_fails_when_an_expired_grant_resumes() -> None:
    with pytest.raises(AssertionError, match="expected STOPPED"):
        rows.assert_stopped(RunState.ACTIVE, None, expected_prefix="grant_expired")


def test_parking_row_fails_on_the_wrong_reason() -> None:
    """Parking for the wrong reason is not the guarantee — the cause must be right."""
    with pytest.raises(AssertionError, match="does not start with"):
        rows.assert_stopped(RunState.STOPPED, "checkpoint_missing", expected_prefix="grant_expired")


def test_reobservation_row_fails_when_an_observed_effect_is_repeated() -> None:
    with pytest.raises(AssertionError, match="repeated a step observed"):
        rows.assert_observation_decides(ObservationOutcome.HAPPENED, repeated=True)


def test_reobservation_row_fails_when_an_absent_effect_is_skipped() -> None:
    """The other direction: silently incomplete runs are the quieter, worse failure."""
    with pytest.raises(AssertionError, match="skipped a step observed"):
        rows.assert_observation_decides(ObservationOutcome.DID_NOT_HAPPEN, repeated=False)


def test_reobservation_row_refuses_to_decide_on_cannot_determine() -> None:
    with pytest.raises(AssertionError, match="must park"):
        rows.assert_observation_decides(ObservationOutcome.CANNOT_DETERMINE, repeated=False)


def test_duplicate_rejection_row_fails_when_a_retry_gets_a_new_identity() -> None:
    with pytest.raises(AssertionError, match="different identity"):
        rows.assert_same_step_same_key("run:1:provision", "run:2:provision")


def test_drain_row_fails_when_evidence_does_not_span_the_boundary() -> None:
    orphaned = CheckpointBlob(blob_id="b", correlation_id="a-different-run")
    with pytest.raises(AssertionError, match="join key did not survive"):
        rows.assert_evidence_spans_disruption(orphaned, "corr-conformance")
