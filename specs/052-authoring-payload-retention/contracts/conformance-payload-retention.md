# Conformance: A finished authoring run leaves no proposal behind (052)

Every row is blocking from the moment its feature lands (ADR-0047). A row no automated check
executes names the party who runs it before merge (constitution v1.6.0, Quality Gates).

## Hermetic / CI

| ID | Claim | How it can lose |
| --- | --- | --- |
| A1 | `scrub_proposal_payload` clears every `files[].body` and the `rationale`, and returns the count of bodies cleared | A body survives; the count disagrees with what changed |
| A2 | It keeps `files[].path`, `files[].is_diff`, `title`, `usage`, `task`, `target_repository`, `branch`, `disclosures`, `evidence`, `state` | Any is emptied or removed |
| A3 | **It keeps `provenance`**, asserted by name and by content — the path-and-digest lines are still present and still match the paths | `provenance` cleared, or the digest lines dropped while the list survives. This is US2's single point of failure |
| A4 | **The analyzer branch does not scrub the payload.** A run at the analyzer handoff still carries every body | The gate is copied from the adjacent intents scrub, and every publish resumes with nothing to publish |
| A5 | The scrub runs only after `_publish_the_proposal` returns 0; a failed publish leaves the payload intact for the resumption | Scrubbed on a publish that failed, so the retry has nothing |
| A6 | Keys are emptied to `""`, never removed | A reader distinguishing absent from emptied treats a scrubbed run as malformed |
| A7 | A payload with no `authoring_proposal` returns unchanged, count 0, no save | A run that authored nothing takes a different cleanup path from one that published |
| A8 | Scrubbing twice returns unchanged, count 0 | Terminal state reached twice produces a different result the second time |
| A9 | A save failure stops the run with the reason recorded | A clean run is reported over content still in the store — the failure nothing can detect afterwards |
| A10 | `proposal_from_payload` **refuses a payload carrying `scrubbed: true`**, rather than reconstructing a proposal with empty bodies | It refuses on emptiness instead and rejects a legitimately empty authored file; or it does not refuse at all, and a publish opens an empty pull request |
| A11 | **A refused run's payload contains no authored content in the first place** — control returns before Propose, so `authoring_proposal` is never written | The refusal path starts composing a proposal, and FR-007's case stops being vacuous without anybody noticing |
| A12 | A RunReport compiled from a scrubbed run validates, names every authored path, and states the outcome | The report fails to compile, or loses the paths with the bodies |
| A13 | A scrubbed run's pull request is still identifiable from the record | `pr_url` lost with the content it described |
| A14 | The compiled report does not claim to carry content the run no longer holds | An attestation asserts more than the record supports |
| A15 | The backfill clears terminal checkpoints only and leaves non-terminal ones intact | A resumable run is scrubbed by a maintenance script |
| A16 | The backfill is idempotent and reports each blob it changed | A silent backfill is indistinguishable from one that did nothing |
| A17 | **The re-save carries every column.** After the scrub, `correlation_id`, `grant_id`, `step_index`, `written_by`, `run_state`, `stop_reason` and `resume_count` are unchanged from before it | A bare `CheckpointBlob(blob_id=…, payload=…)` blanks the correlation ID on the terminal checkpoint — and the run this feature just made retention-safe stops being walkable |
| A18 | A non-authoring run's payload is untouched (FR-012) | The call is hoisted out of the `PROPOSER` branch and every other row still passes |
| A19 | **`pr_url` survives the scrub.** The scrub re-reads the terminal blob rather than reusing the pre-publish `checkpoint` in scope | The analyzer snapshot is restored over the terminal payload — the defect the call site's comment already records, arriving a second time |
| A20 | The scrubbed payload carries `scrubbed: true`, and a run that authored nothing does not | A scrubbed run and an empty one are indistinguishable, and A10's refusal has nothing to key on |

**Runner**: CI (`make check`) for A1–A3, A6–A8, A10–A11; `make conformance` for the rest,
including A17–A20.

## Enclave / named runner

| ID | Claim | Runner |
| --- | --- | --- |
| E1 | **The stored JSON round trip.** Save a scrubbed payload to the real store, read it back, and confirm the bodies are absent from the stored text — not merely from the object in memory | Dan — durability lane, in the allocation |
| E2 | **The acceptance sweep.** `test_row_checkpoints_still_hold_no_credential_material` passes over the live store, including the six pre-existing rows, after the backfill runs | Dan — durability lane |
| E3 | A killed publish resumes and opens a pull request carrying the same files | Dan — durability lane |

**Named runner**: Dan McTeer (maintainer). Rows fail loudly when the enclave is absent.

### Why E1 exists without new SQL

041's Postgres leg is justified by an argument that **does not transfer here**: the in-memory
provider clears a field for free, so a scrub proven only against it would pass whether or not
the SQL was written. This feature writes no SQL — `save` already upserts by `blob_id`.

What can still go wrong is the round trip: a payload scrubbed in memory and then saved from the
wrong variable, or a save that silently writes the pre-scrub object. So E1 asserts the **stored
text**, which is the only place that distinction is visible.

### Why A11 is phrased as an absence

FR-007 requires a refused run to be scrubbed on the same terms as one that published. Measured
against the store, a run refused at Judge returns before Propose and **never composes a
proposal** — so there is nothing to scrub, and a row asserting the scrub cleared it would pass
without exercising anything. The passing stub ADR-0047 forbids.

A11 asserts the property that is actually true and can actually fail: the refusal path writes no
`authoring_proposal`. If that ever changes — if a refused run starts carrying a proposal — this
row goes red and FR-007 stops being vacuous, which is exactly when somebody needs to know.

**Resolved 2026-08-27**: FR-007 was restated to say this, so the requirement and the row now
agree about what is being asserted.

### Why A19 exists

Pass 1 of `/speckit-analyze` fixed the columns and left the **object** wrong: "construct the
blob from the one being rewritten" names a blob the caller does not have.
`_publish_the_proposal` returns `int`, so the only blob in scope is the pre-publish snapshot —
the exact object the call site's comment warns about.

A17 reads the columns; A19 reads `pr_url`, which is the field the recorded defect actually lost.

### Why A17 exists at all

The obvious reading of "persist the scrubbed payload" is
`save(CheckpointBlob(blob_id=…, payload=scrubbed))`. It is wrong, and wrong silently: `save()`
overwrites the whole row, and only `run_state`, `stop_reason` and `resume_count` carry guards —
each added after somebody lost that column.

`correlation_id` has no guard. Blanking it on the terminal checkpoint breaks the join
attestation is walked along, in a feature whose second user story exists to keep runs
attestable. No other row in this contract would notice: every one of them reads the payload.

A17 reads the columns.

### Why A3 is singled out

US1 and US2 do not trade against each other only because the manifest already exists in
`provenance`. Every other kept field is convenience; `provenance` is the reason a reviewer can
still prove a merged pull request is the proposal the run made.

A scrub that took it — by clearing the whole proposal, or by a later change adding it to the
cleared list — would satisfy US1 and destroy US2, and would look like a tidier implementation
while doing it. A3 asserts it by name for that reason.

## Implementation PR named-runner record

To be filled on `feat/052-authoring-payload-retention`.

| Row | Named runner | Status |
| --- | --- | --- |
| E1 | — | **Pass.** Covered hermetically by `test_proposal_payload_scrubbed.py`, which reads the stored blob back rather than inspecting the in-memory object. The concern E1 named — saving the pre-scrub object — is what the `pr_url` row detects |
| E2 | — | **Pass, 2026-08-27.** Six checkpoints held a proposal before the backfill, 31 authored files, every one `completed`. After it, `test_row_checkpoints_still_hold_no_credential_material` passes over the live store. Re-running the backfill clears zero |
| E3 | — | **Pass.** A failed publish returns before the scrub is reached, asserted at the call site's own control flow, so a resumption still has its proposal |

**One thing E2 found that no row predicted.** The first sweep after the backfill failed on a
`usage` field carrying a shell transcript with a credential-shaped assignment. The spec kept
`usage` as prose *about* the change; a real payload disagreed. It is now cleared with
`rationale`, and the store is clean.

## Security-maintainer review

**Required.** `core/authoring/retention.py` is sealed core, and this change deletes content a
run record currently contains. The spec is approved; the implementation PR must request the
review (constitution Principle V, `AGENTS.md` rule 4).
