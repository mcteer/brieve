# Phase 0 Research: Northbound API Operations

**Feature**: `specs/011-api-operations` | **Date**: 2026-07-28

Findings from the source tree and the live enclave. The pattern 010 established holds
here: the two findings that shape this feature most are invisible from the spec's altitude,
and one of them is the same finding this repository has now made four times.

---

## Finding 1 — Runs cannot be listed because nothing durable knows who started one.

**Decision**: A **run index** is written at dispatch time — subject, tenant, definition,
correlation id, run id, created-at — as its own table beside the durability schema, queried
by the list operation and never read by resume.

**What the source says**. The durable run record is `checkpoints`:

```sql
blob_id | payload | correlation_id | grant_id | step_index | written_by | run_state | stop_reason
```

**No subject. No tenant.** A checkpoint answers "where did this run get to", which is what
resume needs and all 005 built it for. "What has this person started" is unanswerable from
durable state — the only places a subject appears are the audit trail (the forensic path
this feature exists to stop using as a product path) and `NomadDispatcher._dispatched`,
which is a per-process dict that dies with the surface.

**This is the recurring seam finding, fourth appearance.** 009 hit it when the sweeper
could not reconstruct a dispatch (`suspended_runs` gained `subject_user_id`, `tenant_id`,
`agent_definition_id`); 010 hit it twice. Each store was built for exactly one caller and
carries exactly what that caller passed. The 009 remedy is the template: an index table
owned by the new reader, written at the moment the facts exist (dispatch), with the
checkpoint remaining authoritative for run *state* — the index is a candidate list for
enumeration exactly as `suspended_runs` is a candidate list for the sweeper.

**Alternatives considered**: Deriving the list from `run_start` audit events — rejected;
the spec's own US3 argument applies (forensic path as product path), and evidence reads are
themselves audited, so listing your runs would generate an evidence-access record per page.
Widening `checkpoints` with subject/tenant — rejected; resume does not need them, and a
resume-critical table should not grow columns only a listing reads.

---

## Finding 2 — The collect operation has nothing to look up: the accessor is returned and forgotten.

**Decision**: Submission writes a **change-request record** (accessor, requester, tenant,
mapping, submitted-at) when Vault answers with a wrap accessor. Collect looks the record up
by accessor, verifies the caller is its requester in its tenant, and only then asks Vault.

**What the source says**. `VaultAuthoritySubmitter.submit` raises
`BlockedPendingApprovalError` carrying the accessor, the surface returns it to the caller,
and **nothing stores it**. The platform that reasoned about clients collecting an outcome
later kept no record that there was anything to collect.

**What the live enclave says**. The polling mechanism exists and takes exactly one
argument:

```
$ vault path-help sys/control-group/request
    accessor (string)   The accessor of the request.
    "Check the status of a control group request"
```

**Why the record is load-bearing rather than bookkeeping**: without it, anyone holding an
accessor could poll any request — the accessor becomes a capability, and spec scenario 3
("another tenant's request answers as not-exists") is unimplementable because there is no
tenant to compare against. The record is what makes collect a *tenant-scoped read* instead
of an accessor-bearer capability. FR-002's read-only property comes free: the status
endpoint cannot authorize; authorization is a different Vault call this feature never makes.

---

## Finding 3 — Stop needs no new terminal machinery; it needs a reader at the step boundary.

**Decision**: Stop writes `run_state = STOPPED`, `stop_reason = stopped_by:<subject>` to
the durable run record. The running allocation observes it **at the step boundary** — after
the in-flight step's result is bracketed, before the next intent is written — which is
exactly C3's semantics falling out of where the check sits rather than being enforced by a
timeout.

**What the source says**, and all three pieces already exist:

- `RunState.STOPPED` is terminal (`is_terminal()` true) — a stopped run is not resumable
  by construction.
- The sweeper's `_is_suspended` returns `False` for any run whose checkpoint carries a
  terminal outcome or a non-SUSPENDED state — **FR-009 (the sweeper never resumes a
  stopped run) holds with zero new code**, and the conformance row asserts it rather than
  building it.
- `RunOutcome(state, stop_reason)` is carried on the checkpoint because "a resuming process
  has only the checkpoint" — the same argument gives the stop its durable home.

**What does not exist**: nothing on the invoke path reads the durable run state. Policy is
read per step (010); run state is not. The step boundary gains that read, and the write
race in the edge case ("stop arrives as the run finishes") resolves in the store: both
writers target one row, the terminal write that lands second loses, and the record shows
one outcome.

---

## Finding 4 — A run has nowhere to put a result, because no run has ever produced one for a person.

**Decision**: The terminal checkpoint's `payload` carries the result under a reserved key.
Retrieval reads the terminal checkpoint through the run index (which supplies the tenant
check) and returns the three-way disposition FR-007 requires: `run_state` absent → not
finished; result key present → the result; terminal without it → ended without one, with
`stop_reason` as the why.

**Rationale**: `payload JSONB` exists, is written at terminal transitions already, and is
read by exactly the machinery that knows the run is over. A new column would imply results
are queryable server-side, which nothing needs; a new table would be a second place a run's
end is recorded, and two records of one ending will eventually disagree.

**Alternatives considered**: A result store of its own — rejected until something needs to
query *into* results; the entitlement to revisit is cheap. Returning the last checkpoint
payload as-is — rejected; checkpoint state is resume state, and leaking it wholesale makes
its shape a compatibility surface, which is the US3 argument again one layer down.

---

## Finding 5 — Enumeration is one missing Vault capability away, and "may start" has a precise meaning.

**Decision**: The read policy gains `list` on the registration path; enumeration lists
display names, reads each ceiling record, and computes availability as **the subject's
scope intersected with the ceiling being non-empty**. Empty intersection → present but
marked unavailable (C2). Ceiling paths, policy names, and `ceiling_policies` never appear
(FR-014) — the public view is built from the harness-authority record, not the
registration.

**What the live enclave says**:

```
path "agent-registry/registration/display-name/*" { capabilities = ["read"] }
```

Read but not `list` — 010 granted exactly what resolution needed, which is the seam
pattern in policy form. One capability, one line, and the enumeration this feature adds is
the second caller that needs more.

**Why intersection-non-empty rather than subset**: a subject whose scope covers *part* of
a ceiling can legitimately start that agent with a narrower request — 002 refuses only
requests *exceeding* scope. Requiring subset would mark startable agents unavailable,
which is the inverse of C2's disclosure decision.

---

## Finding 6 — Parity grows by snapshot, and the snapshot is the spec of record.

**Decision**: Every operation lands as: route + MCP tool + snapshot entry, in the same
change. The parity row (`operation_pairs() == snapshot`) fails on any asymmetry including
count, so a grown snapshot *is* FR-019's "asserted over the grown catalogue" — no new
mechanism, provided the snapshot grows in the same commit as the surfaces.

**One trap recorded from 009**: MCP is where a "just this one helper" is cheapest to add,
and the coverage row catches it **in either direction** — an MCP tool with no API route
fails the same as the reverse. The tasks should sequence snapshot-first per operation so
the row goes red before the surfaces exist and green when both do, which turns parity into
the development loop rather than a post-hoc check.

---

## Consolidated decisions

| # | Decision | Rationale |
| --- | --- | --- |
| D1 | Run index table, written at dispatch, owned by the list operation | Checkpoints have no subject/tenant; fourth instance of the one-caller seam; `suspended_runs` is the template |
| D2 | Change-request record written on 202; collect verifies requester+tenant before polling Vault | Without it the accessor is a cross-tenant capability and scenario 3 is unimplementable |
| D3 | Stop = terminal state written durably, observed at the step boundary | STOPPED is already terminal and already sweeper-proof; C3's semantics fall out of placement |
| D4 | Result lives in the terminal checkpoint payload under a reserved key | The one place a run's ending is already recorded; two records of one ending will disagree |
| D5 | Enumeration via `list` capability + ceiling records; available = scope ∩ ceiling ≠ ∅ | Subset would mark startable agents unavailable, inverting C2 |
| D6 | Snapshot-first sequencing per operation | Makes the parity row the loop, not the audit |

## Remaining unknowns

None blocking. One carried forward deliberately: **whether the run index should eventually
absorb `suspended_runs`** — they are both "find runs by something other than their id"
tables, and two index tables over one run population is a future coherence question.
Recorded for the plan's structure section rather than decided in research.
