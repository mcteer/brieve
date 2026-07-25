# SPDX-License-Identifier: Apache-2.0
"""In-memory durability provider — the 004 default and test double."""

from __future__ import annotations

from core.durability.types import CheckpointBlob


class InMemoryDurabilityProvider:
    """Process-local checkpoint store. No persistence, no credentials."""

    def __init__(self) -> None:
        self._blobs: dict[str, CheckpointBlob] = {}

    def save(self, blob: CheckpointBlob) -> None:
        self._blobs[blob.blob_id] = blob

    def load(self, blob_id: str) -> CheckpointBlob | None:
        return self._blobs.get(blob_id)
