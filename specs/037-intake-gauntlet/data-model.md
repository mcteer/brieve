# Data Model: The intake gauntlet

**Feature**: 037 | **Date**: 2026-08-05

No new store. Proposals are files and a pull request; everything the platform decides lands
in the existing hash-chained audit trail and is read through the governed read path.

## Audit events (additive to `AuditEventType`, sealed core, Principle V review)

### `ANALYSIS_VERDICT = "analysis_verdict"`

What the analyzer concluded about a candidate. **May block; never approves** (ADR-0043,
Principle IX) — the payload carries no field that could be read as an approval, which is the
distinction made structural rather than promised.

| Field | Type | Notes |
| --- | --- | --- |
| `skill_name` | str | which adopted skill |
| `candidate_digest` | str | identifies the *bytes*, so a verdict can never drift onto a different candidate |
| `verdict` | str | `clean` / `flagged` / `inconclusive` — three-valued, because an analysis that could not complete is not a clean one (FR-024) |
| `findings` | list[str] | finding codes, never quoted candidate prose — the trail must not become a copy of hostile content |
| `analyzer_cell` | str | which qualified matrix cell produced it, so a later re-qualification can identify what it invalidates |

### `DETONATION_COMPARED = "detonation_compared"`

How the candidate behaved against the corpus relative to the pinned version.

| Field | Type | Notes |
| --- | --- | --- |
| `skill_name`, `candidate_digest`, `baseline_digest` | str | both sides named by content |
| `tasks_run` | int | a comparison over zero tasks is not a comparison (FR-014) |
| `new_attempts` | list[str] | tool names the candidate reached for and the baseline did not |
| `new_denials` | list[str] | what the governance floor caught that it did not catch before |
| `written_by` | str | the **observer's** identity — never the specimen's (FR-013) |

### `CANARY_CONTACT = "canary_contact"`

Planted material appearing anywhere it should not. Its own member rather than a finding on
the comparison: a canary is a fact about containment, not about behaviour, and burying it in
a diff would make the loudest possible signal the quietest field in a payload.

| Field | Type | Notes |
| --- | --- | --- |
| `canary_id` | str | which canary — never its value |
| `observed_in` | str | where it surfaced (span, tool argument, artifact) |
| `candidate_digest` | str | the candidate under detonation |

### `INTAKE_BYPASSED = "intake_bypassed"`

The manual path was taken (FR-025a). **The record that keeps a permitted bypass from becoming
an invisible one.**

| Field | Type | Notes |
| --- | --- | --- |
| `skill_name`, `to_version` | str | what was adopted |
| `subject_user_id` | str | who took it — a bypass with no name is an unattributable act |
| `reason` | str | why the pipeline was unavailable, stated by the person |

## Records outside the trail

### Pin
Where an adopted skill came from and exactly which version: `repository` and `commit`, read
from a pack's `[upstream]` table. **An absent table means authored, not broken** (R2) — the
loader already refuses an `adopted` pack without one, so intake never has to guess.

### Candidate
A proposed version, identified by **content digest** rather than by version string.
Everything downstream keys off the digest so evidence cannot drift onto different bytes
(FR-005) — the failure where upstream moves twice and the reviewer accepts a package
describing a candidate that is no longer the one in the proposal.

### Delta
The exact difference between pinned and candidate. The analysis subject, which is why cost
tracks upstream motion rather than upstream size.

### Evidence package
What the reviewer is handed, and the feature's actual product: the delta, provenance for both
versions, the verdict and its findings, the detonation comparison, canary status, and — per
FR-027 — **an explicit statement of what none of it establishes**. A package that reads
"clean" without saying what clean does not cover is the reassurance failure this feature is
most able to cause.

### Intake seed case
A human-labelled hostile candidate with a known-correct verdict: the attack class it
represents, the content, and what the analyzer must say about it. Checked into
`evals/intake-seed/`, reviewed like code, authority terminating in a person's judgement
(ADR-0052's mechanism, R8).

### Golden task
A fixed task the corpus runs both skill versions against, so their behaviour is comparable.
Fixed is the point: a corpus that changed between the two runs would produce a diff that
described the corpus rather than the candidate.

## Relationships

```text
Pin ──moved?──> Candidate (by digest)
                   │
                   ├─ Delta ──> ANALYSIS_VERDICT {verdict, findings}
                   │              │
                   │              ├─ flagged ──────────────> reviewer (stages stop)
                   │              └─ clean ──> Detonation
                   │                             ├─ DETONATION_COMPARED {written_by: observer}
                   │                             └─ CANARY_CONTACT*
                   │
                   └─ Evidence package ──> human acceptance ──> promote_skill ──> warn ──> enforce
                                                     ▲
                                    nothing above this line promotes (FR-021)

INTAKE_BYPASSED ─────────────────────────────────> promote_skill   (pipeline unavailable)
```

One correlation ID joins a candidate's stages. The property in one sentence: **every arrow
into `promote_skill` passes through a human, and the trail can tell which arrow it was.**
