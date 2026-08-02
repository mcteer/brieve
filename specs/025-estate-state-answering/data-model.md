# Data model: 025 — estate-state answering

**Phase 1.** Nothing here is persisted. Like 024's `Answer` and 021's `RunReport`, everything an
estate question produces has no identity between requests — the records it cites are the durable
thing, and they already exist.

---

## Route

The router's verdict on one question. Three values, closed:

| Value | Meaning | What happens |
| --- | --- | --- |
| `guidance` | The question is about how things work | 024's corpus path, unchanged |
| `estate` | The question is about what the records show | The estate path below |
| `neither` | The question fits no source | Decline, naming both sources tried — never a coin flip |

- **Deterministic** (FR-010a): same question, same route, every time. No model, no randomness, no
  state. Ties between the two vocabularies break toward `estate` (plan, Complexity Tracking).
- **Recorded** (FR-010b): the route rides the `ASK_ANSWERED` record's new `source` field.

## Scope

What this asker may see. Computed, never stored, never accepted from the request.

| Field | Source | Rule |
| --- | --- | --- |
| `tenant_id` | `AuthenticatedSubject.tenant_id` | The outer bound — enforced by the governed read as today |
| `visible_event_types` | `AuthenticatedSubject.roles` through the role visibility map | Union across the subject's roles; **empty union refuses** (FR-004c) |

- The map's domain is the closed `AuditEventType` vocabulary. An unknown role contributes nothing;
  a subject whose roles all contribute nothing is refused before any read happens.
- Scope narrows the `EvidenceQueryRequest.event_types` field **before the query runs** — never a
  filter over results (research F2). The access record therefore shows the narrowed request.

## Estate reference

The pointer from a claim to the record behind it — 024's citation, for the trail.

| Field | Meaning |
| --- | --- |
| `entry_hash` | The referenced entry's own content hash — the chain's existing identity for it |

- **Resolves** iff the hash is present in *this asker's scoped read result* (research F3). Not
  "exists in the trail" — exists in **what this subject was allowed to read for this question**.
  That single rule is what makes FR-005a structural rather than reviewed-for.
- An unresolvable reference drops its claim, silently to the model and visibly in `dropped`.

## Estate answer

| Field | Rule |
| --- | --- |
| `disposition` | `answered` or `declined` — never `failed`; a store failure **raises**, distinguishably (FR-003) |
| `source` | Always `estate` — carried so the decline can name it (FR-010c) |
| `claims` | Each: statement + one or more references, every one resolved |
| `declined_reason` | Names the source: *"the records you may see do not show this"* — never the corpus's decline text |
| `dropped` | Statements whose references did not resolve — surfaced for scoring, never silently gone |

**Never present, by construction rather than review**: verdicts (FR-005 — no claim that anything
is compliant/passing/healthy/safe), counts or totals over records outside scope (FR-005a — nothing
outside scope enters the path), record payload content beyond what the claim states (the reference
points; the reader follows it through the governed read like anyone else).

**The caller-indistinguishability rule (SC-008)**: "no records in scope" and "records exist but
are not yours" produce the **same** declined answer. The difference lives where 022 put it — in
the access record's disposition, readable by an investigator.

## EstateProvider (seam)

Same shape as 024's `AnswerProvider`, different material:

- **Input**: the question, and the scoped records (the read result — all the model ever sees).
- **Output**: candidate claims, each with entry-hash references.
- `RecordedEstateProvider` replays a case's recording as the model's output — the blocking lane.
- The live provider offers the fixture records to a real model — the paid lane. Same path either
  way; only the provider differs.

## The `ASK_ANSWERED` record — sealed core, one additive field

| Field | Guidance ask | Estate ask |
| --- | --- | --- |
| `subject_user_id` | unchanged | unchanged |
| `corpus_digest` | the corpus pin | the identity of what was consulted — see note |
| `model` | unchanged | unchanged |
| `disposition` | unchanged | unchanged |
| `source` **(new)** | `guidance` | `estate` (or `neither`, on an unroutable decline) |

**Note on `corpus_digest` for estate asks**: the field generalises to "identity of what was
consulted" rather than gaining a sibling — for an estate ask it carries the correlation id of the
evidence-access record the read wrote, so the ask record points at the access record and the walk
from "someone asked" to "here is exactly what was read" is one hop. **Principle V review covers
both the new field and this generalisation** (Dan McTeer, before merge).

## Eval case shape — `estate_state`, reauthored

| Field | Rule |
| --- | --- |
| `prompt` | A question the **records** can answer — no product-configuration questions (FR-006a) |
| `recorded` | The model's proposed claims, as the blocking lane's substrate |
| `events` | **The expected reference set** — which fixture records a faithful answer cites |
| `expected` | Dropped for this suite; fidelity scoring replaces the verb |

Scored by the fidelity discipline over surviving references: `missing` (recall — an omitted
violation) and `invented` (precision — a workspace the estate does not contain) both fail
(FR-011b). `packs/<pack>/evals/estate_records.toml` holds the arranged estate; no digest pin,
because it is authored fixture material, not vendored third-party content — the contract records
this distinction so the corpus analogy is not over-applied.

## State transitions

There are none. A question is asked, routed, answered or declined, and recorded — nothing persists
except the records that already existed and the two audit entries (access, ask) the existing
mechanisms write.
