# Phase 0 Research: Wire resume into the dispatched path

**Feature**: `specs/014-dispatched-resume` | **Date**: 2026-07-29

Three findings and five decisions. The findings came from reading the shipped code, which is
this repository's habit and has paid every time — and the first one changes the feature's
shape.

---

## Findings

### F1 — The dispatched path has no durable grant, so resume cannot check consent

`resume_run` requires a `DelegationGrant` — it calls `grant.assert_live(clock)` before
anything else, which is US4's whole mechanism. But `issue_grant` builds the grant **in
memory**, nothing persists it anywhere, and the dispatched entrypoint never issues one at
all. ADR-0026's own words describe the intended shape — *"Durable consent. Referenced by a
checkpoint via `grant_id` only"* — and the referenced-by half was built while the durable
half was not.

Worse, the reference is wrong today: the entrypoint writes
`grant_id=getattr(run.authority, "credential_id", "")` into checkpoints — **the 15-minute
task credential's id in the column meant for durable consent**. So the checkpoint points at
something that expires in minutes and is stored nowhere.

Consequence: this feature is not only wiring. A grant store must exist before US4 is even
*evaluable* on the dispatched path, and the entrypoint's grant_id write is a latent bug that
must be fixed in the same change or the store indexes garbage.

### F2 — A fully controllable suspend/resume cycle already exists in the shipped pieces

The conformance rows need to produce suspension on demand, repeatedly, without breaking the
enclave. Stopping Vault would suspend runs — and also break the trust fabric the resume needs.

The shipped pieces compose into a clean harness instead: `TerraformApplyObserver` returns
`CANNOT_DETERMINE` by design ("terraform is fixture-backed here; nothing to observe"), so a
dispatched run holding an **open intent** for `terraform_apply` will, on resume, hit exactly
the suspension path — awaiting `terraform`. The dependency store's `record_probe` is
host-writable in the conformance lane, so "terraform recovers" is one call, and the sweeper
does the rest. Flapping is repetition. No product is harmed, the fabric stays up, and every
piece involved is production code rather than test scaffolding.

### F3 — The sweeper's staleness check already tolerates what the entrypoint writes

`_is_suspended` reads `checkpoint.outcome` (terminal wins) and falls back to
`checkpoint.run_state`. The entrypoint's mid-run checkpoints carry `outcome=None`, so a
suspended run's candidacy survives, and a terminal checkpoint correctly drops it. No change
needed — recorded so nobody "fixes" it.

---

## Decisions

### D1 — A resume is declared by the dispatcher, never inferred by the entrypoint

**Decision**: the sweeper's dispatch carries an explicit `resume = "1"` in the parameterized
job's metadata; the entrypoint takes the resume path if and only if that flag is set. Fresh
dispatches never set it.

**Rationale**: the spec's edge case — a fresh dispatch carrying a resume's identifiers must
be distinguishable — rules out inference. Inferring from `step_index > 0` misses a resume
interrupted at step zero; inferring from "a checkpoint exists for this run id" turns an id
collision into a silent resume, which is precisely the failure the jobspec's own
`meta_required` comment warns about. The dispatcher *knows* whether it is resuming — the
sweeper is the only caller that does — so the knowledge travels as data rather than being
reconstructed.

**Alternatives**: checkpoint-existence inference (rejected above); a separate parameterized
job for resumes (rejected — two jobspecs that must stay identical except one flag is drift
waiting to happen).

### D2 — Grants become a durability record, written at issuance, loaded at resume

**Decision**: a `grants` table beside the checkpoints, holding exactly `DelegationGrant`'s
fields — subject, definition, scope, issued/expires. The dispatched entrypoint **issues a
real grant** at run start, persists it, and writes its id (not the credential id) into
checkpoints. Resume loads the grant by the checkpoint's `grant_id` and hands it to the
library.

**Rationale**: F1 makes this unavoidable, and ADR-0026 already describes it — the checkpoint
references durable consent by id, so the id must resolve to something durable. A grant is
consent *metadata* — subject, scope, expiry — and contains no credential material, so FR-012
and the checkpoint discipline are untouched; the no-secret conformance sweep extends to the
new table verbatim. The grant's duration comes from the definition's maximum run duration,
which `issue_grant` already enforces.

**Alternatives**: embedding the grant in the checkpoint payload (rejected — checkpoints are
overwritten per step and the grant must outlive any one of them; and ADR-0026 says
*referenced*, not carried); Vault KV (rejected — a grant is run state with run lifetime, not
operator-authored authority; the trust fabric holds what operators author).

### D3 — The resume-attempt count lives on the checkpoint row; the cap is 5

**Decision**: `resume_count` as an additive, defaulted column on the checkpoint record,
incremented by the resume path after the ownership claim succeeds. The cap is a platform
constant, **5**, set in core beside the other bounds — never from workflow code, the
definition, or dispatch metadata (FR-009c).

**Rationale**: the count must survive the disruption it is counting (FR-009a), which rules
out memory and the suspended-run index (rows are forgotten on dispatch). The checkpoint row
is the one durable record with the run's lifetime. Incrementing after the lease claim means a
superseded instance cannot burn attempts. Five is a starting point, not a finding: large
enough that a real outage's recovery (one suspend, one resume) never approaches it, small
enough that a flapping dependency stops within minutes. The spec says the number will be
tuned; what matters is that exhaustion is terminal and recorded.

**Alternatives**: a separate attempts table (rejected — a second store that can disagree with
the checkpoint, for one integer); counting dispatches in the sweeper (rejected — the sweeper's
index row is dropped on dispatch, so the count would reset exactly when it matters).

### D4 — One new audit event, `RUN_RESUMED`, carrying the decision

**Decision**: a single additive `AuditEventType.RUN_RESUMED` written by the entrypoint when
it takes the resume path, with a payload carrying the decision outcome (continued / stopped /
suspended), the reason when not continuing, the attempt number, and the counts of completed
and pending steps. Stops and suspensions reached *through* resume also keep their existing
terminal records.

**Rationale**: FR-017 wants the three outcomes distinguishable by record. One event with the
outcome in its payload keeps the trail's vocabulary small (the 013 pattern: one event, the
distinction in the payload, `MODEL_GATE` vs its `verdict`) while an investigator filtering
`RUN_RESUMED` sees every revival and what came of it. Three separate event types would make
"how many times was this run revived" a three-way union for no gain.

**Alternatives**: reusing `RUN_START` with a `resumed` flag (rejected — a resumed run that
*stops* never starts, so the event would be a lie in exactly the failure cases); three new
event types (rejected above).

### D5 — The disruption harness is the terraform fixture product, per F2

**Decision**: the dispatch-level rows produce suspension via an open `terraform_apply` intent
(observer answers `CANNOT_DETERMINE` → suspend awaiting `terraform`), recovery via
`record_probe("terraform", reachable=True)`, and flapping via repetition. Interruption
mid-step for the re-observation rows uses the scheduler's own stop on a multi-step run. The
live-product re-observation rows (FR-006a) use `vault_write`'s real observer against the real
Vault, arranging both directions by writing — or not writing — the probe path first.

**Rationale**: every piece is shipped production code; the enclave stays healthy; the cycle
is repeatable in seconds rather than minutes because nothing real has to fail. The vault half
satisfies FR-006a's "live product, both directions, shipped observer" exactly.

**Alternatives**: stopping the Vault container (rejected — takes the trust fabric down with
the product, so the resume path under test cannot run); a purpose-built flaky product
(rejected by clarify Q3 — a fixture answering a question about observation).

---

## Resolved unknowns

Clarify deferred two architecture questions to planning; both are resolved above — the
discriminator (D1) and the audit shape (D4). The technical unknowns the spec left open — where
the attempt count lives (D3), what makes consent checkable at resume (F1/D2), and how the
rows produce disruption on demand (F2/D5) — are resolved above.
