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

    #: A step a resumed allocation did NOT execute, and why (ROADMAP gap 0c).
    #:
    #: **The counterpart to `TOOL_OUTCOME`, and together they must account for every step.**
    #: A step records its result and then audits its outcome; a kill between the two leaves
    #: an effect that happened, is durably recorded, and has no entry in the trail — and the
    #: resume correctly does not repeat it, so the entry was never going to appear later
    #: either. The trail was short by one and nothing said why.
    #:
    #: So the skip records itself. An investigator reconciling a resumed run finds, for every
    #: step, either an outcome (this allocation ran it) or one of these (a previous allocation
    #: ran it and this one observed that rather than repeating it). "Re-observe, never
    #: re-execute" stops being an inference from counts and becomes a statement in the record.
    STEP_REOBSERVED = "step_reobserved"

    #: How a step's tool was decided, and by whom (020, ADR-0022/0039). Payload: run_id,
    #: step_index, attempt, model, named, outcome.
    #:
    #: **A SEALED-CORE ADDITION** (Principle V). The audit schema is named sealed core
    #: explicitly, so this member required the approved spec and the security-maintainer
    #: review that principle demands. Research F1 established the change is purely additive
    #: to an unversioned enum that no test asserts the membership of — which made it small,
    #: not exempt.
    #:
    #: **Why a new type rather than a field on the tool bracket.** A refused choice never
    #: opens a bracket. The single most important record this feature produces — a model
    #: reached past its ceiling — would have had nowhere to live, so the trail would have
    #: shown only the choices that succeeded and described the wrong run.
    #:
    #: **Why not `PRE_DECISION`.** That records what a *hook* decided about a tool
    #: (`hook_name`, `capability_kind`, `outcome`, `reason_code`). This records who *named*
    #: the tool and why it was on the table. Folding the second into the first would leave a
    #: reader unable to tell a chosen tool from a scheduled one, which is the whole of what
    #: SC-002 must be able to prove.
    #:
    #: One type with the distinction in `outcome`, on the `MODEL_GATE` / `RUN_RESUMED`
    #: pattern. The vocabulary is closed and lives in `core.choice.ChoiceOutcome`:
    #:
    #: * ``chosen`` — named, permitted, executed.
    #: * ``refused`` — named, refused by the existing enforcement. Every attempt gets one,
    #:   not only the last before success (FR-004c).
    #: * ``malformed`` — the model emitted something that is not a tool name at all.
    #:   Distinct from ``refused`` because the two mean different things to a reader: one
    #:   model misunderstood the task, the other understood it and reached past its ceiling.
    #: * ``empty`` — the model named nothing. Terminal; the run does not default to a tool.
    #: * ``exhausted`` — the re-choice bound ran out. Terminal, and recorded rather than
    #:   inferred from a run of ``refused`` entries that simply stops.
    #: * ``not_consulted`` — this step asked no model, because the run invokes no tools
    #:   (FR-002a/FR-002b). Written so the carve-out is legible rather than showing as an
    #:   absence, which is how `STEP_REOBSERVED` came to exist one feature earlier.
    #: * ``provider_unavailable`` — the provider could not be reached, or answered unusably.
    #:   Terminal, with no fallback to any non-model selection (FR-007). Separate from
    #:   ``empty`` because a model declining to act and a vendor failing to answer are
    #:   different events with different fixes, and the trail must not report an outage as an
    #:   agent decision. Carries an extra ``reason`` key naming which failure it was.
    #:
    #: **The model's reasoning is never carried.** It is not a governance fact, and it would
    #: bring whatever the model read out of a tool result into an append-only trail. The
    #: no-secret-leak posture applies to what is recorded about a choice exactly as it
    #: applies to a tool result.
    TOOL_CHOSEN = "tool_chosen"

    #: What a run learned by asking a product whether its effect actually landed (021,
    #: ADR-0018). Payload: run_id, step_index, tool, idempotency_key, outcome, detail.
    #:
    #: **A SEALED-CORE ADDITION** (Principle V), and the second in two features. Purely
    #: additive to an unversioned enum, which is what makes it small — and "additive" is the
    #: word that precedes most sealed-core regressions, so it carried the approved spec and
    #: the security-maintainer review that principle demands rather than being waved through.
    #:
    #: **Why this exists at all.** What a run records about a tool is that it was *allowed*.
    #: That is not the claim *it happened*. ADR-0018 requires a read-back before asserting
    #: something completed, and nothing in the trail could support that assertion — so a
    #: report compiled from records alone would have had to either guess or stay silent, and
    #: "applied successfully to three workspaces" when a fourth silently failed is the exact
    #: failure the ADR opens with.
    #:
    #: **Why the RUN writes it, and not the report.** This is the whole of 021's Constitution
    #: Check, which failed on Principle IV before this shape was chosen. `Observer.observe`
    #: takes no credential and reads under *ambient* identity — inside an allocation that is
    #: the run's own attested identity, bounded by its ceiling. At report time there is no
    #: allocation, so a read-back performed for a reader would run under the API surface's
    #: identity and hand them an observation they may hold no authority to make. An agent
    #: never exceeds its human; a report must not exceed its reader.
    #:
    #: So the allocation observes before it reaches a terminal state, records the answer
    #: here, and the report compiles it like any other record. The compiler holds no
    #: credential and calls no observer — a property to check first on any later change.
    #:
    #: ``outcome`` is `core.observation.ObservationOutcome`, unchanged and already three-way:
    #: ``happened`` / ``did_not_happen`` / ``cannot_determine``. That third value is why this
    #: works — an unreachable product is not evidence of success, and not of failure either,
    #: and a two-way outcome would force a guess in exactly the case where guessing is the
    #: failure.
    #:
    #: **Recording an observation never changes the run's outcome.** A run that did its work
    #: and then found an effect missing completed and produced a finding; letting the
    #: observation retroactively fail the run would give a reporting mechanism power over
    #: what it reports.
    EFFECT_OBSERVED = "effect_observed"

    #: Someone was shown a record about a run or a thread (022). Payload: subject_user_id,
    #: operation, target_correlation_id, target_id, disposition, result_count.
    #:
    #: **A SEALED-CORE ADDITION** (Principle V), and the third feature running to make one. The
    #: additive-only argument is the same one 020 and 021 made, and it is checked rather than
    #: repeated: `test_widening_the_event_vocabulary_moves_no_existing_hash` pins one entry's
    #: digest as a literal, because the hash covers an entry's *own* ``event_type`` value and
    #: not the set of possible values.
    #:
    #: **Why this is not `EVIDENCE_READ`.** That member means someone read the *audit plane*.
    #: Reusing it would hand an operator asking who read the trail a list of run listings, and
    #: would silently change what entries already written appear to mean — which is not an
    #: additive change however it is spelled.
    #:
    #: **Why it exists.** ADR-0035 made reading the evidence itself evidence, and stopped at
    #: the audit plane. Nine of seventeen operations returned records about runs and threads
    #: and wrote nothing, while both surfaces told every client that every operation was
    #: recorded. The sharpest case: 021 kept the run's result out of `RunReport` so a
    #: tenant-scoped report could not route around `get_run_result`'s subject-only
    #: restriction — and `get_run_result` itself recorded nothing about who read it. The
    #: artifact that could not leak the result was audited; the one that served it was not.
    #:
    #: **Never the content read** — the payload carries the shape of the access and the
    #: identifiers, never rows. A record that quoted what it described would copy the thing it
    #: points at into an append-only trail, and would inherit neither the trail's
    #: no-egress-by-default posture nor `get_run_result`'s subject restriction.
    #:
    #: **Written to `record-access:{tenant}`, never to the chain being read.** Appending to a
    #: run's own chain would mean reading a run alters it — and 021's `RunReport` compiles
    #: from that chain, so a report of a run would carry claims about who read the run,
    #: including reads of the report, growing every time anyone looked. The evidence path
    #: already refused this shape for its own reason; here it is load-bearing twice.
    RECORD_READ = "record_read"

    #: A read of a run or thread record that was refused (022). Same payload, with
    #: ``disposition`` carrying the reason code.
    #:
    #: **A separate member rather than a flag**, mirroring `EVIDENCE_READ_REFUSED`. A boundary
    #: a caller can probe without trace is the thing this prevents, and the trail keeps the
    #: distinction the caller cannot see: ``no_such_record`` and ``outside_tenant`` are one
    #: answer to the caller and two different events here — a run of the second is someone
    #: probing, and collapsing them would show a user who mistypes a lot.
    RECORD_READ_REFUSED = "record_read_refused"

    #: A thread was created (022). Payload: subject_user_id, thread_id.
    #:
    #: **The missing counterpart to `THREAD_DELETED`**, which has existed since 012. The trail
    #: could show a thread ended and everything said in it, and could not show it began — a
    #: lifecycle recorded only at its end is a narrative with no first page. Written to the
    #: thread's own stream, where its counterpart is written; this is an act on the thread
    #: rather than a read of it.
    THREAD_CREATED = "thread_created"

    #: A person withdrew consent and ended a run (022). Payload: subject_user_id, run_id,
    #: stop_reason.
    #:
    #: **Found by analysis, after this feature's own spec asserted it already existed.** The
    #: spec said `stop_run` was covered alongside `start_run` and called the pair *measured*;
    #: only `start_run` had been. `stop_run_for` wrote a `CheckpointBlob` carrying
    #: ``written_by="stop:{user}"`` and returned — no audit entry at all, no ``STOP`` member in
    #: this enum. The only attribution lived in a durability field: not hash-chained, and not
    #: reachable through the governed evidence path.
    #:
    #: **The only write among 022's seven covered operations, and the most consequential.** The
    #: other six are reads, where the gap is no trace of who looked. This one is a run being
    #: terminated by a named person — the operation whose own implementation says *"only the
    #: person who gave consent may withdraw it"* — leaving nothing a reviewer could find.
    #:
    #: On the run's own stream, for the same reason `THREAD_DELETED` is on the thread's.
    RUN_STOPPED = "run_stopped"

    #: Someone asked a question and was answered or declined (024, ADR-0039). Payload:
    #: subject_user_id, corpus_digest, model, disposition, source.
    #:
    #: **`source` is 025's additive field** and names which material answered: ``guidance`` (the
    #: pinned corpus), ``estate`` (the tenant's own records, through the governed read), or
    #: ``neither`` (the question fit no source and was declined). Asking happens in one place and
    #: the platform routes, so *which door was opened* is a fact about the ask that an
    #: investigator cannot otherwise recover — two asks with identical dispositions may have
    #: consulted entirely different material.
    #:
    #: **`corpus_digest` generalises to "identity of what was consulted"** rather than gaining a
    #: sibling field. For a guidance ask it remains the corpus pin. For an estate ask it carries
    #: the **evidence-access stream's** correlation id (``evidence-access:{tenant}``), so the walk
    #: from *someone asked* to *here is what was read* is one hop to that stream — the stream, not
    #: a single record, because 022 made the id stable per tenant on purpose so access records
    #: chain to each other rather than each being a chain of one. Within the stream the read is
    #: locatable by subject and time.
    #:
    #: **The narrowed request is what the access record carries**, and it is how an investigator
    #: distinguishes "your scope contained nothing" from "records existed outside your scope" —
    #: `EvidenceDisposition` does not distinguish those (it separates only the cross-tenant case),
    #: and the caller is deliberately told the same thing either way.
    #:
    #: **A SEALED-CORE ADDITION** (Principle V), the fourth feature running to make one, and the
    #: one whose review this feature's plan originally asserted was not needed. The plan hedged —
    #: *"if an audit event type turns out to be needed, that changes this verdict"* — and the
    #: condition had already fired when the data model was written. A conditional verdict reads as
    #: a pass; that is why nobody noticed until an analysis pass compared the two.
    #:
    #: **Why no existing member fits.** `MODEL_GATE` is the closest and carries ``run_id``,
    #: ``role``, ``cell``, ``verdict`` and ``step_index`` — a model verdict gating a **step in a
    #: run**. An ask has neither a run nor a step. `RECORD_READ` means a run or thread record was
    #: shown to someone; an ask consults a corpus, not the platform's own records.
    #:
    #: **Written to ``ask:{tenant_id}``**, stable per tenant. An ask touches neither a run nor a
    #: thread, so neither of 022's placements applies — reads go to ``record-access:{tenant}`` and
    #: acts go to the object's own stream. Stable rather than per-ask for the reason
    #: `EVIDENCE_STREAM_PREFIX` already records: a fresh correlation id each time makes every
    #: record a chain of one, linked to nothing and removable without trace.
    #:
    #: **Never the question and never the answer.** Recording either would copy corpus text into
    #: an append-only trail that does not egress by default, and 022 established that a record of
    #: an access carries its shape and never its content. What is recorded is who asked, which
    #: corpus pin was consulted, which model the binding named, and whether they were answered or
    #: declined.
    #:
    #: **A model verdict, never an approval.** ADR-0039 and Principle IX: a model may inform; it
    #: never satisfies an approval requirement policy assigns to a person. `MODEL_GATE` already
    #: establishes that distinction for runs, and this keeps it for asks rather than blurring it.
    ASK_ANSWERED = "ask_answered"


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
