# Data Model: Customer-supplied context

Shaped by research R1–R10. Governance facts live in the trust fabric; content weight lives in
Postgres; nothing new is operated.

## EndorsedSource (US1/US3 — the governance record, trust fabric)

The fourth console record, at `harness-authority/data/endorsed-sources`.

| Field | Type | Rule |
| --- | --- | --- |
| `name` | str | the citation namespace segment (`/endorsed/<name>/…`); immutable once endorsed |
| `location` | URL | where the source lives; a location, never a credential (044 FR-018b posture) |
| `endorsed_by` / `endorsed_at` | str / timestamp | FR-002 — who trusted it, when |
| `adopted_version` | str | which synced version answers rest on; **flipping this is the adoption**, through the console's request-and-decide path |
| `adopted_by` / `adopted_at` | str / timestamp | FR-017e — an adoption is recorded like the endorsement it renews |
| `withdrawn` | bool | FR-004 — withdrawal zeroes citability at the next resolution, no restart (read per request, 044's toggle mechanism) |
| `set_by` | str | 044's provenance stamp, unchanged |

Invariants: `name` is unique and never begins with a corpus path prefix; a withdrawn source
resolves nothing regardless of `adopted_version`; the record is CAS-guarded like every console
record.

## SyncedVersion (US2/US3 — the content, Postgres)

Immutable once written. An adoption references one; it never mutates.

| Field | Type | Rule |
| --- | --- | --- |
| `source` | str | the EndorsedSource it came from |
| `version_id` | str | content digest over the manifest — the identity a run pins and a record names |
| `upstream_tip` | str | what the source said it was at sync time; what detection compares against |
| `synced_at` / `synced_by` | timestamp / str | FR-017; `synced_by` is the administrator whose act triggered it |
| `state` | enum: `candidate` \| `adopted` \| `superseded` | a review-sync lands as `candidate` (R5); adoption flips it; a later adoption supersedes, never deletes (R3 — runs may still pin it) |
| `documents` | rows | per document: path (`/endorsed/<source>/<rel>`), digest, anchors, sections |

Verification on read mirrors the pinned corpus: a document that does not match its digest
refuses (`CorpusUnavailable`'s posture — a refusal, never a fallback; FR-007).

## EndorsedCorpus (US5/US6/US7 — the reader's view)

Same contract as `Corpus`, second implementation, never a modification of the first (R1).

| Member | Rule |
| --- | --- |
| `resolves(path, anchor)` | true only for documents in the **adopted** version of a **non-withdrawn** source for **this tenant** |
| `digest` | the adopted `version_id` — what the record names (FR-017h) |
| `synced_at` | drives the age disclosure via the same `describe_ground` reasoning (FR-017b) |

**CombinedView**: resolution tries the pin, then the endorsed corpus; the `/endorsed/`
namespace makes overlap impossible. The pinned reader is not edited (US6 by construction).

## Citation provenance (US5 — clarify Q2)

Each rendered citation gains `provenance: "validated-design" | "customer-endorsed"` — **data,
not presentation** — derivable from the path and emitted explicitly because a prefix
convention in every consumer is how conventions decay. The answer's note summarises: validated
designs, your organisation's endorsed material, or both. The proposal's evidence section
carries the same (FR-016).

## DriftFlag (US3 — detection, health-checker state)

| Field | Rule |
| --- | --- |
| `source` | which endorsed source moved |
| `upstream_tip` vs `adopted_tip` | the comparison that raised it; a listing of refs, no content transfer |
| `detected_at` | when the checker noticed |

Noticing changes nothing (FR-017a). The console renders the flag; review syncs a `candidate`
version on demand and presents added/removed/altered against the adopted one (FR-017c) — so a
source that moved again is reviewed against what is *currently* upstream.

## Run pinning (US4)

| Where | What |
| --- | --- |
| ask path | version resolved once per request — free |
| dispatched run | `endorsed_version` written into the checkpoint blob's existing `payload` dict at run start; resume reads the pin and loads that version (R4) |
| run/ask record | the version joins `corpus_digest`; **exactly one value** (FR-017h) |

## Refusal vocabulary added

`source_withdrawn` (a citation into a withdrawn source does not resolve — indistinguishable
from absent to the asker, recorded distinctly), `version_mismatch` (content failed its digest —
FR-007, refuses like `CorpusUnavailable`), `sync_failed` / `source_empty` / `nothing_citable`
(FR-018's three distinct states), `unknown_record` extended by `endorsed-sources` (R7).
