# SPDX-License-Identifier: Apache-2.0
"""Durability seam — checkpoints hold state, never credentials (Principle IV).

Thin protocol only. Full resume semantics (kill/resume, re-observe-never-re-execute,
re-auth-never-replay, double-resume fencing) are ADR-0024 depth and are deferred; this
exists so the adapter's state mapping has a framework-agnostic target rather than a
second, adapter-local store.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class CheckpointBlob(BaseModel):
    """Opaque framework state plus join metadata. Carries no authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blob_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = ""


class DurabilityProvider(Protocol):
    """Persist and retrieve checkpoint state. Errors fail closed at the call site."""

    def save(self, blob: CheckpointBlob) -> None:
        """Persist checkpoint metadata and payload."""
        ...

    def load(self, blob_id: str) -> CheckpointBlob | None:
        """Return the blob, or None on miss."""
        ...
