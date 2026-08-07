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

from core.authority.grant import DelegationGrant


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
    #: How many times this run has been revived (014, D3). Additive and defaulted, so
    #: every existing construction site is unchanged.
    #:
    #: **The default is the trap.** `save()` overwrites the whole row, so a per-step blob
    #: constructed without this field resets the stored count to zero — which would make
    #: the attempt cap a bound that clears itself whenever any work happens, and a
    #: flapping run immortal. A resumed run's caller must thread the decision's count
    #: into every checkpoint it writes; the entrypoint does, and a component row asserts
    #: it from the store side.
    resume_count: int = 0


class IntentRecord(BaseModel):
    """Written *before* a non-repeatable effect, so an interruption is resolvable.

    Since 040 it says *"we were about to run X **with these**"*: a pending step re-invokes on
    revival, and once the arguments come from a model rather than from a platform constant,
    repeating the same act requires having kept them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    step_index: int
    tool_name: str
    idempotency_key: str
    #: What the model asked this tool to do (040). **NULL is not empty**: ``None`` means
    #: recorded before this field existed, and such an intent revives with the pre-040
    #: platform constant its first attempt actually ran with, while ``{}`` means a post-040
    #: act that genuinely asked for nothing. Additive and defaulted on ``resume_count``'s
    #: precedent, so every existing construction site is unchanged — and, exactly as there,
    #: the default is the trap: a site that *does* know its arguments and lets this default
    #: writes a post-040 record on the pre-040 side of that line.
    #:
    #: **Kept until something removes it**; the platform expires nothing. Removing it from a
    #: CLOSED bracket is safe — resume reads arguments only for pending steps — and removing
    #: it from an OPEN one would make that revival re-invoke with nothing.
    arguments: dict[str, Any] | None = None
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

    def closed_intents(self, run_id: str) -> list[IntentRecord]:
        """Intents that DO have results — steps whose effect is recorded as complete.

        The counterpart to :meth:`open_intents`, and the one 005 did not need until a
        resumed run had to decide what to skip.

        **A closed bracket is the authoritative record that a step took effect**, and it is
        stronger evidence than the checkpoint's step index: the result is written by the
        step itself, at the moment it finished, while the checkpoint is written afterwards
        and can be lost to a disruption landing in between. A resume that consults only the
        checkpoint therefore re-runs a step whose effect already happened — an exactly-once
        violation for any non-repeatable tool, and invisible, because the re-run looks
        exactly like the first run.
        """
        ...

    def save_grant(self, grant: DelegationGrant) -> None:
        """Persist the subject's consent, once, at issuance.

        The durable half of ADR-0026, added in 014 because it was never built: a
        checkpoint has referenced consent by ``grant_id`` since 005, and until now the id
        resolved to nothing. Resume's first act is ``grant.assert_live(clock)``, so
        without this method consent expiry was unevaluable on the dispatched path.

        Written once and never updated — a grant's terms do not change, and a new consent
        is a new grant. Implementations therefore need no update path, and the absence of
        one is deliberate rather than pending.

        Holds consent metadata and **no credential material**: ``DelegationGrant`` has no
        field for any, and the store must not add one (FR-012).
        """
        ...

    def load_grant(self, grant_id: str) -> DelegationGrant | None:
        """Return the grant, or None when there is none.

        ``None`` rather than an exception, mirroring :meth:`load`'s absence semantics, so
        **the caller decides what absence means**. That matters here more than it does for
        checkpoints: a missing grant is not "no consent required", and the only code
        positioned to know that is the caller that was about to act under it. A provider
        raising would make the refusal the store's decision; a provider returning an empty
        grant would manufacture consent nobody gave.
        """
        ...
