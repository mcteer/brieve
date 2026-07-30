# SPDX-License-Identifier: Apache-2.0
"""Audit entry schema (sealed)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceDisposition(StrEnum):
    """Why an evidence read returned what it returned.

    Both values can accompany a zero-row result, which is the entire point: an
    investigator needs to distinguish "nothing happened" from "you may not see it", and
    the caller must not be able to tell the difference at all (FR-011).
    """

    #: The query ran within the caller's scope. Zero rows means zero rows.
    SCOPED = "scoped"
    #: The query reached beyond the caller's scope. Zero rows means "not for you".
    OUT_OF_SCOPE = "out_of_scope"


class AuditEventType(StrEnum):
    RUN_START = "run_start"
    PRE_DECISION = "pre_decision"
    TOOL_OUTCOME = "tool_outcome"
    POST_DECISION = "post_decision"
    ENFORCEMENT_ERROR = "enforcement_error"
    AUTHORITY_ISSUED = "authority_issued"
    AUTHORITY_REFUSED = "authority_refused"
    AUTHORITY_DENIED = "authority_denied"
    AUTHORITY_EXPIRED = "authority_expired"
    MIRRORING_DECISION = "mirroring_decision"
    EVIDENCE_READ = "evidence_read"
    EVIDENCE_READ_REFUSED = "evidence_read_refused"
    #: An authority change the harness observed the trust fabric decide (ADR-0016, 007).
    #: Added here rather than reusing AUTHORITY_ISSUED: a change that was *requested* and
    #: is awaiting quorum has not issued anything, and filing it as an issuance would make
    #: the trail claim authority was granted at the moment it was asked for.
    AUTHORITY_CHANGE_OBSERVED = "authority_change_observed"
    #: A person's message, recorded as the rationale for what it caused (ADR-0051, 012).
    #:
    #: Written for every **accepted** turn — one that dispatched, one that was declined
    #: because nothing could be dispatched, and one refused on scope — *before* the turn
    #: does anything else. A declined ask is still an ask, and after a thread is deleted
    #: this event is the only copy of it: threads are a deletable view, and this is the
    #: record. It carries the message verbatim, which is a deliberate divergence from
    #: `redact_arguments` and is argued in ADR-0051 rather than assumed here.
    TURN_RECORDED = "turn_recorded"
    #: A message the platform never accepted — rate-limited, or over its size bound.
    #:
    #: Separate from TURN_RECORDED because it carries the message's SIZE and never its
    #: content. Recording the content here would make the append-only trail growable at
    #: whatever rate a caller can be refused, so the bound protecting dispatch would leave
    #: evidence unbounded; recording nothing would make flooding invisible. The size is
    #: what lets an investigator see the shape of an abuse attempt without the trail
    #: carrying its payload.
    TURN_REFUSED = "turn_refused"
    #: A thread's view was removed. The turns it held remain in this trail.
    #:
    #: In the chain, so "the deletion itself appears in the trail" is a row rather than a
    #: claim — and so deletion is demonstrably not a masking primitive.
    THREAD_DELETED = "thread_deleted"
    #: A model verdict that gated a step (ADR-0039, 013). Payload: run_id, role, model,
    #: cell, verdict, step_index.
    #:
    #: **This ESTABLISHES a distinction rather than repairing one.** FR-015 requires the
    #: trail to distinguish a model gate from a human approval, and there is no approval
    #: member in this enum at all — `core/approvals/types.py` is a Protocol and two doubles
    #: with no event of its own (research.md F3). So the distinction could not be made by
    #: adding nuance to an existing pair, because the pair did not exist. Adding this one
    #: unilaterally means that when human approvals gain their own event, the two are
    #: already separate rather than needing to be untangled.
    #:
    #: A model verdict MAY gate a step and **never** satisfies an approval requirement that
    #: policy assigns to a human (Principle IX). That rule is enforced where approvals are
    #: resolved; this event is what makes it auditable.
    MODEL_GATE = "model_gate"
    #: The pinned matrix cell was unavailable and another QUALIFIED cell was used
    #: (ADR-0022/0039, 013). Payload: run_id, role, pinned_cell, used_cell, reason.
    #:
    #: Separate from MODEL_GATE because they answer different questions — "a model decided
    #: something" versus "the model that ran was not the model that was pinned" — and an
    #: investigator looking for the second should not have to filter the first.
    #:
    #: The recording is the load-bearing half of FR-010: falling back to an unqualified
    #: model is impossible, and falling back *silently* would leave a definition that does
    #: not describe what ran. Written by whoever holds the sink — `start_governed_run` at
    #: run start, the resume caller on resume — because the module that RESOLVES a fallback
    #: holds neither a sink nor a tenant, and `AuditEntry` requires both.
    MATRIX_FALLBACK = "matrix_fallback"
    #: The two copies of the trail were compared, and what came of it (ADR-0055, 015).
    #:
    #: Payload: `basis` (``scheduled`` | ``on_demand``), `caller`, `streams_checked`,
    #: `findings` by kind with counts, `backlog`, `coverage` (attested-since), and `posture`
    #: (``in_force`` | ``absent`` | ``unverified`` | ``non_compliant``).
    #:
    #: One type with the distinction in the payload, on the `MODEL_GATE` pattern: an
    #: investigator filtering for reconciliation wants every run, and three event types
    #: would make "how often was this checked" a union nobody remembers to write in full.
    #:
    #: **Findings carry stream and sequence, never payload content.** A record of an
    #: evidence read that quoted the evidence would be an ungoverned read path wearing an
    #: audit event's clothes — and this one is written precisely because reading evidence is
    #: audited (ADR-0035).
    AUDIT_RECONCILED = "audit_reconciled"
    #: A disrupted run was revived, and what came of the revival (ADR-0049, 014).
    #:
    #: Payload: run_id, `attempt` (1-based, so the trail reads "attempt 3 of 5" without
    #: arithmetic), `outcome` (``continued`` | ``stopped`` | ``suspended``), `reason` (the
    #: stop reason or the awaited dependency; empty when continued), and `completed_steps`
    #: / `pending_steps` as COUNTS rather than contents — enough for an investigator to see
    #: "it skipped 3 and ran 2" without the trail carrying step payloads.
    #:
    #: One event with the outcome in the payload, on the `MODEL_GATE` pattern: one type,
    #: the distinction inside. Three event types would make "how many times was this run
    #: revived" a three-way union for no gain, and every filter that wanted revivals would
    #: have to know all three names or silently miss one.
    #:
    #: **Not a flag on `RUN_START`.** A resumed run that stops — expired consent, a missing
    #: checkpoint, the attempt cap — never starts, so a `RUN_START` carrying `resumed=true`
    #: would be a record of a beginning that did not happen, in exactly the failure cases
    #: an investigator is reading the trail to understand.
    #:
    #: Written by the entrypoint, before any pending step executes, on the same reasoning
    #: as `MATRIX_FALLBACK` above: the library returns a decision, the caller that holds
    #: the sink and the tenant records it. Ordering it first is what makes the trail show
    #: the revival before its consequences (FR-017).
    RUN_RESUMED = "run_resumed"


class AuditEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    correlation_id: str
    #: The bounding dimension of every evidence read, and INSIDE the hash chain.
    #: A tenant column beside the chain would leave the field that decides who may see a
    #: record alterable without breaking it — the one place that must not be true.
    tenant_id: str
    seq: int = Field(ge=0)
    event_type: AuditEventType
    timestamp: datetime
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str
