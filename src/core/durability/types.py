# SPDX-License-Identifier: Apache-2.0
"""Durability seam — checkpoints hold state, never credentials (Principle IV).

The guarantees live **above** this interface (FR-012). A provider chooses how bytes are
stored; it cannot choose whether resume re-authenticates, whether a checkpoint may hold
a credential, or whether a superseded writer is rejected. That is the whole claim of
ADR-0024, and it is only true because the seam is drawn here rather than lower.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


class RunOutcome(BaseModel):
    """Terminal state as recorded on a checkpoint.

    Carried on the blob rather than held in memory because a resuming process has
    *only* the checkpoint. Without it there is no way to tell a run that finished from
    one interrupted mid-step, and "do not re-enter a terminal run" becomes
    unenforceable rather than merely untested.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: str
    stop_reason: str | None = None


class CheckpointBlob(BaseModel):
    """Opaque framework state plus resume metadata. Carries no authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    blob_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = ""
    grant_id: str = ""
    step_index: int = 0
    written_by: str = ""
    outcome: RunOutcome | None = None


class IntentRecord(BaseModel):
    """Written *before* a non-repeatable effect, so an interruption is resolvable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    step_index: int
    tool_name: str
    idempotency_key: str
    recorded_at: datetime


class ResultRecord(BaseModel):
    """Written *after* the effect. An intent without one is the interrupted case."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    step_index: int
    idempotency_key: str
    recorded_at: datetime


class DurabilityProvider(Protocol):
    """Persist and retrieve run state. Errors fail closed at the call site.

    Breaking change vs 004, which was ``save``/``load`` only: that protocol cannot
    express a lease or a bracket, so it cannot support resume. Pre-1.0, one in-repo
    implementation, no external consumers — declared, not assumed.
    """

    def save(self, blob: CheckpointBlob) -> None:
        """Persist a checkpoint. Failure MUST propagate — a step must not proceed as
        though it had been recorded."""
        ...

    def load(self, blob_id: str) -> CheckpointBlob | None:
        """Return the blob, or None on miss. Never return partial state as valid."""
        ...

    def acquire_lease(self, run_id: str, holder_identity: str) -> None:
        """Claim the run, superseding any prior holder atomically."""
        ...

    def check_lease(self, run_id: str, holder_identity: str) -> bool:
        """False for a superseded holder. A comparison, never advisory."""
        ...

    def record_intent(self, record: IntentRecord) -> None:
        """Persist the opening half of a bracket."""
        ...

    def record_result(self, record: ResultRecord) -> None:
        """Persist the closing half."""
        ...

    def open_intents(self, run_id: str) -> list[IntentRecord]:
        """Intents with no result — exactly what resume must resolve by observation."""
        ...
