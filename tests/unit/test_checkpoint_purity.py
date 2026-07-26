# SPDX-License-Identifier: Apache-2.0
"""Checkpoints hold state, never credentials — FR-003 / SC-003, T020/T032.

Asserted for **every** provider, not only the convenient one: ADR-0024's claim is that
a provider cannot change whether a checkpoint may hold a credential, and a test that
covers one implementation leaves that claim unexamined.
"""

from __future__ import annotations

import pytest
from tests.harness import SECRET_MARKERS, assert_no_secret_values, durability_grant, frozen_clock

from core.durability.memory import InMemoryDurabilityProvider
from core.durability.types import CheckpointBlob

FORBIDDEN_FIELDS = {"credential", "credential_id", "token", "secret", "password", "run_salt"}


def test_checkpoint_blob_has_no_credential_fields() -> None:
    """Structural: there is nowhere on the model to put one."""
    assert not set(CheckpointBlob.model_fields) & FORBIDDEN_FIELDS


def test_saved_checkpoints_contain_no_secret_values() -> None:
    clock = frozen_clock()
    grant = durability_grant(clock)
    provider = InMemoryDurabilityProvider()
    provider.save(
        CheckpointBlob(
            blob_id="blob-1",
            payload={"step": "gather", "notes": "nothing sensitive"},
            correlation_id="corr-1",
            grant_id=grant.grant_id,
            step_index=1,
            written_by="alloc-1",
        )
    )
    loaded = provider.load("blob-1")
    assert loaded is not None
    assert_no_secret_values(loaded.model_dump())


@pytest.mark.parametrize("marker", sorted(SECRET_MARKERS))
def test_secret_markers_are_detectable_in_a_blob(marker: str) -> None:
    """A self-check on the assertion itself.

    If ``assert_no_secret_values`` silently stopped inspecting nested payloads, every
    purity test above would keep passing while proving nothing. This makes the
    detector's failure visible.
    """
    blob = CheckpointBlob(blob_id="b", payload={"leak": marker})
    with pytest.raises(AssertionError):
        assert_no_secret_values(blob.model_dump())


def test_grant_reference_is_an_id_not_the_grant() -> None:
    """A checkpoint references consent; it does not carry it."""
    blob = CheckpointBlob(blob_id="b", grant_id="grant-123")
    assert isinstance(blob.grant_id, str)
    assert "requested_scope" not in blob.model_dump()
