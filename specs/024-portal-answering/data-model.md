# Data Model: 024 — grounded guidance

**Phase 1.** Four entities. Nothing is persisted; an answer has no lifecycle.

---

## 1. Corpus pin

**What it represents**: the exact guidance content an answer was produced from.

| Field | Note |
| --- | --- |
| `content_digest` | **The identity.** The corpus carries **no version metadata anywhere**, so a version field would name nothing. Change is detected by content or not at all (FR-014). |
| `document_count` | What was pinned, so a truncated vendoring is visible rather than silent. |
| `provenance` | Where it came from and when, recorded beside the content — the shape `packs/*/skills/PROVENANCE.md` already uses. |

### Validation rules

- **Vendored, not fetched at answer time.** An answer that depends on a third party being reachable
  is not answering from a pin, and "pinned" would be untrue.
- **A digest change is a corpus change**, and citations must reflect it (SC-009).

---

## 2. Citation

**What it represents**: a pointer from a claim to the passage supporting it.

| Field | Note |
| --- | --- |
| `document` | Which corpus document. |
| `anchor` | The section. The corpus has **stable per-section anchors**, which is what makes a citation more precise than a document reference. |
| `quote` | Optional, and never a substitute for the anchor. |

### Validation rules

- **A citation MUST resolve** against the pinned corpus. **An unresolvable citation is worse than
  no citation**, because it reads as evidence — this is the single most important rule here.
- **Citations are produced against the pin the answer used**, not against whatever is current.
- **No citation is invented from the model's memory.** If it does not resolve, the claim carrying
  it does not ship.

---

## 3. Answer

**What it represents**: what the platform returned to a question.

| Field | Note |
| --- | --- |
| `disposition` | `answered` or `declined`. **Not `failed`** — a provider failure is not an answer and does not arrive in this shape at all (FR-011). |
| `claims` | Each with its citations. A claim with none does not ship. |
| `declined_reason` | Present when declining, naming what the corpus does not support. |
| `corpus_digest` | Which pin this was produced from. |

### Validation rules

- **Never persisted.** Like `RunReport`, it has no identity between requests; a stored answer is a
  second copy of the corpus that can drift from it.
- **Declining is a first-class outcome**, not an error. Two dispositions, and the reader can tell
  which they have.
- **No effecting capability is reachable from producing one** (FR-006).

---

## 4. Ask record

**What it represents**: that someone asked, and what was consulted.

**Where it lands**: `ask:{tenant_id}` — one stream per tenant, **stable across asks**.

An `AuditEntry` requires a `correlation_id` **and** a `tenant_id`, and an ask has neither a run nor
a thread — so neither of 022's answers applies. Reads go to `record-access:{tenant}`; acts go to
the object's own stream; an ask is neither, and an earlier draft of this section named no stream at
all, which made FR-012 unimplementable.

**Stable per tenant, not per ask**, for the reason `evidence-access` already records: *"a fresh
correlation ID each time would make every record a chain of one — linked to nothing and removable
without trace."* Both tenant and subject come from the authenticated caller, exactly as
`record_access` takes them (`subject.tenant_id`); there is no tenant parameter to widen.

| Field | Note |
| --- | --- |
| `subject_user_id` | Who asked. |
| `corpus_digest` | What was consulted. |
| `model` | Which model the binding named. |
| `disposition` | Answered or declined. |

### Validation rules

- **Never the question, never the answer.** FR-012 — recording the content would copy corpus
  material into an append-only trail, and 022 established that a read record carries the shape of
  an access and never its content.
- **A model verdict is distinguishable from a human approval** (FR-010). A model may inform; it
  never satisfies an approval policy assigns to a person.

---

## State transitions

None. A question produces one answer or one decline, and neither is updated afterwards.

**One ordering constraint**: the matrix cell is checked **before** any provider call (FR-009). An
unqualified binding that reached a vendor first would have spent the call it was refused for.
