# SPDX-License-Identifier: Apache-2.0
"""US4 — the state mapping binds to the durability seam (FR-009).

GATE:no-secret-leak. Companion to test_durability_no_credentials, which covers the
core seam; this covers the adapter mapping onto it.
"""

from __future__ import annotations

import pytest
from tests.harness import AUTHORITY_SECRET_MARKER, assert_no_secret_values

from adapters.pydantic_ai.durability import (
    CredentialInCheckpointError,
    load_state,
    save_state,
)
from core.durability import InMemoryDurabilityProvider


def test_state_roundtrips_through_the_core_seam() -> None:
    provider = InMemoryDurabilityProvider()
    blob = save_state(
        provider,
        blob_id="blob-1",
        correlation_id="corr-dur",
        state={"messages": ["hello"], "step": 2},
    )
    loaded = load_state(provider, "blob-1")
    assert loaded is not None
    assert loaded.payload == blob.payload
    assert loaded.correlation_id == "corr-dur"


def test_load_miss_returns_none() -> None:
    assert load_state(InMemoryDurabilityProvider(), "absent") is None


@pytest.mark.parametrize(
    "key", ["run_salt", "credential_id", "authority", "token", "secret", "CREDENTIAL"]
)
def test_credential_bearing_payload_is_refused(key: str) -> None:
    """Refuse loudly rather than dropping the key — a silently stripped blob looks complete."""
    provider = InMemoryDurabilityProvider()
    with pytest.raises(CredentialInCheckpointError):
        save_state(
            provider,
            blob_id="blob-bad",
            correlation_id="corr-dur",
            state={key: AUTHORITY_SECRET_MARKER},
        )
    assert load_state(provider, "blob-bad") is None


def test_saved_blob_carries_no_secret_markers() -> None:
    provider = InMemoryDurabilityProvider()
    blob = save_state(
        provider,
        blob_id="blob-2",
        correlation_id="corr-dur",
        state={"messages": ["ordinary content"]},
    )
    assert_no_secret_values(blob.model_dump())
