# SPDX-License-Identifier: Apache-2.0
"""Mapping 2 of 4: framework state to the durability seam.

Thin binding only. Full resume semantics are ADR-0024 depth and deferred; what
matters here is that the call path exists and targets the core protocol rather
than an adapter-local store.

Checkpoints hold state, never credentials (Principle IV). ``save_state`` strips
nothing and hides nothing — it refuses to write a payload carrying credential
material, because silently dropping a key would make the blob look complete.
"""

from __future__ import annotations

from typing import Any

from core.durability import CheckpointBlob, DurabilityProvider

# Keys that would carry authority into a checkpoint. Resume re-authenticates; it
# never replays a credential, so none of these belong in a blob.
_FORBIDDEN_KEYS = frozenset(
    {"run_salt", "credential", "credential_id", "credential_ref", "authority", "token", "secret"}
)


class CredentialInCheckpointError(Exception):
    """Raised when a checkpoint payload would carry credential material."""


def _reject_credentials(payload: dict[str, Any]) -> None:
    for key in payload:
        if key.lower() in _FORBIDDEN_KEYS:
            raise CredentialInCheckpointError(
                f"checkpoint payload may not contain {key!r}: checkpoints hold state, "
                "never credentials"
            )


def save_state(
    provider: DurabilityProvider,
    *,
    blob_id: str,
    correlation_id: str,
    state: dict[str, Any],
) -> CheckpointBlob:
    """Persist framework state through the core seam."""
    _reject_credentials(state)
    blob = CheckpointBlob(blob_id=blob_id, payload=dict(state), correlation_id=correlation_id)
    provider.save(blob)
    return blob


def load_state(provider: DurabilityProvider, blob_id: str) -> CheckpointBlob | None:
    """Read framework state back through the core seam."""
    return provider.load(blob_id)
