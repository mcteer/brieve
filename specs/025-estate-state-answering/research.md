# Research: 025 — estate-state answering

**Phase 0.** Everything below was measured against the repository on 2026-08-02. One finding
corrects an assumption the spec carried; one names a sealed-core obligation up front because the
last feature's plan asserted the absence of one and was wrong.

---

## F1 — The governed read exists, is transport-independent, and records by itself

**Measured**: `src/surfaces/api/evidence.py:59` — `read_evidence_for()` builds an
`EvidenceQueryRequest` with `tenant_id` **from the subject, never the request**, runs the search,
computes a disposition, empties the result on `OUT_OF_SCOPE`, and **writes the access record before
returning**. MCP reaches this same function (ADR-0033's discipline, already applied by 022).

**Decision**: the estate answering path consumes `read_evidence_for()` — not `EvidenceQuery`
directly, and not a new query. **One governed door.**

**Rationale**: FR-008 (an estate question's read is recorded) then comes free rather than being a
second recording site that can drift from the first. A path that reached `EvidenceQuery` directly
would be the parallel read path ADR-0035 and the spec both refuse.

**Consequence**: SC-008 also comes free — `_disposition` already collapses "not yours" into zero
rows for the caller while recording the difference in the trail. The estate path must not undo
that by phrasing its decline differently for the two cases.

---

## F2 — Roles are carried everywhere and consumed nowhere that matters here

**Measured**: `AuthenticatedSubject.roles` exists (`src/core/identity/types.py:38`), claim-mapped,
documented *"empty means refuse — never a default role"*. It is threaded through dispatch
(`subject_roles` on every dispatcher) and stamped into run metadata. **Nothing maps a role to what
evidence it may see.** The governed read bounds by tenant alone; `EvidenceQueryRequest` has no
roles field.

**Decision**: role scope is a **visibility map from role to the audit event types that role may
see**, held in core beside the answering path, and applied by **narrowing the query request before
it is made** — `event_types` is already a narrowing field on `EvidenceQueryRequest`.

**Rationale**: the spec forbids a post-filter (*"a filter applied to results after a broad read is
how scope errors become silent"*). Narrowing the request means out-of-scope rows are never read at
all — the bound is in the query, and the trail's access record shows the narrowed request rather
than a broad one. The map's domain is the closed `AuditEventType` vocabulary, so an unknown role
maps to nothing and *empty means refuse* applies unchanged.

**Corrected by analysis (I1), and the correction is a signature, not the design**:
`read_evidence_for` builds the request internally and **exposes no `event_types` parameter** —
measured at `evidence.py:60-69`, where the first draft of this finding assumed the field was
reachable because the request model carries it. The one-door design therefore needs one additive
parameter: `event_types: frozenset[AuditEventType] | None = None`, defaulting to the unnarrowed
read. Same shape as 024's ask-provider fix — a collaborator the design requires must be a
parameter, not an assumption.

**What this deliberately is not**: a change to `GET /evidence` behaviour. The route never passes
the new parameter, so 022's operator read stays tenant-bounded as shipped — asserted by a row, not
by this paragraph (tasks T009a). An operator reading the trail directly is a different act from
the platform assembling an answer on someone's behalf, and retrofitting role bounds onto 022's
surface would change merged behaviour this feature has no mandate to change.

**Alternatives considered**:

- **Bound inside `EvidenceQuery` implementations.** Puts authorization in every store
  implementation — three copies of a security decision (memory, postgres, and whatever comes
  third), which is how one of them drifts.
- **A new scope attribute on the subject.** That is ADR-0035's *team* granularity, needs identity
  work the platform lacks, and is exactly what FR-004d records as owed instead.

---

## F3 — The reference is the entry hash, because the trail already names its entries

**Measured**: every `AuditEntry` carries `entry_hash` — content-derived, unique per entry, already
the chain's own identity for it. The corpus analogue (`Corpus.resolves(path, anchor)`) shows the
shape a reference check needs: set membership against material the asker was allowed to see.

**Decision**: an **estate reference is an entry hash**, and it resolves iff that hash is in the
result set of *this asker's own scoped read*. A claim whose reference does not resolve is dropped;
an answer with nothing left declines — 024's citation discipline, verbatim.

**Rationale**: resolving against the scoped read result makes FR-005a structural. The model only
ever sees scoped records, and a reference can only point into them — so an answer cannot carry
the shape of a record outside the asker's scope, including by implication, because nothing outside
the scope ever enters the path.

---

## F4 — Routing is string-shape against a closed vocabulary, and the decision rides the existing record

**Measured**: `ask_for()` in `src/surfaces/api/ask.py` goes straight to
`answer_question(corpus=...)`. Routing slots in front of it, in core, so both surfaces inherit it
through the one implementation.

**Decision**: a deterministic router in `core.answering` classifies a question as **estate-shaped**
(temporal-window and estate-record vocabulary — *changed, last night, who, when, run, violation,
denied, refused*), **guidance-shaped** (*how does, what is, should I, recommended*), or neither.
Ties break toward **estate**, and the decline names the source consulted (FR-010c), so a misrouted
asker learns which door was tried and can rephrase.

**Why ties break toward estate**: the two misroutes are not symmetric. Estate→corpus tells someone
their own records are documentation (bad answer). Guidance→estate performs a **scoped read** that
writes an access record for a question that was never about the records (bad act). But the
tie-break must go somewhere, and estate is the direction whose failure is *visible to the asker* —
a guidance question routed to estate declines naming the evidence plane, and the asker rephrases;
the reverse misroute produces a plausible-looking wrong source. Visible failures get fixed.

**The recording**: `ASK_ANSWERED`'s payload gains a `source` field naming what was consulted.
**This is a sealed-core touch** — the audit schema documents that payload as
`{subject_user_id, corpus_digest, model, disposition}`, and investigators parse what it documents.
**Principle V review is owed, and is declared now** rather than discovered by an analysis pass,
which is precisely how 024's plan got this wrong. `corpus_digest` generalises to the identity of
what was consulted: the corpus pin for guidance, the access record's identity for estate.

**Alternative considered**: a separate routing event type. A second sealed-core member for a fact
that is an attribute of the ask, not an event of its own — an ask consults exactly one source, so
the source belongs on the ask record.

---

## F5 — `estate_state` scoring reuses the fidelity machinery, and both failure directions come free

**Measured**: `score_fidelity(report, expected)` (`src/core/evals/fidelity.py:88`) already computes
`matched / missing / invented` — recall catches omission, precision catches invention. The
`EvalCase` shape already carries `events: tuple[str, ...]` for exactly this kind of labelling.
Meanwhile `_judge_response`'s `match` case is a substring check: **it cannot fail an answer that
names something extra**, so FR-011b is unsatisfiable in the current shape — measured, not assumed.

**Decision**: reauthored `estate_state` cases carry the **expected reference set** in `events`.
The blocking lane drives the estate path with a `RecordedEstateProvider` (the recording is the
model's proposed claims), the path resolves references against a **fixture estate**, and the
surviving references are scored against `events` by the fidelity discipline — precision and
recall, not substring.

**The fixture estate lives in the pack** (`packs/<pack>/evals/estate_records.toml`): the arranged
records the cases ask about, the analogue of the vendored corpus. The live lane offers the same
records to a real model and scores the same way — same thresholds, only the provider differs,
which is the D8 seam's whole claim.

**Consequence for the old cases**: *"which secrets engines are mounted?"* cannot be answered from
records and is reauthored per FR-006a. The old cases' final act is FR-012: the old suite runs once
against the live model **with per-case output printed** (the evals-smoke discipline — one call
visible beats twenty-eight minutes blind) to name which case failed on 2026-08-01, the finding is
recorded in the conformance contract, and then the reauthoring lands.

---

## F6 — What must not change

- **`GET /evidence` behaviour** (F2). 022's surface is not this feature's to modify.
- **The never-acts property is inherited, not rebuilt.** The estate path lives in
  `core.answering`, holds a reader and a provider, and imports no registry — the existing AST
  conformance rows extend to it by listing the new module, not by new machinery.
- **`ask` stays one operation.** Parity grows by zero operations; the parity rows grow estate
  *verdicts* under the existing operation.
- **The blocking lane stays credential-free** (FR-011a). The fixture estate is data in the pack;
  no enclave, no vendor, no store.
- **The matrix stays honest.** The `ask` cell remains `fixture` until the reauthored suite passes
  live; this feature does not flip it by reauthoring away the failure — FR-012 names the old
  failure first, so the record shows *what* failed before the suite that failed is replaced.
- **No new dependency.** Routing is stdlib string work; scoring reuses `fidelity.py`.

---

## Open for tasks, not for plan

- Whether the routing vocabulary lists live beside the router as constants or in the pack. They
  start beside the router: they are platform vocabulary (the trail's own nouns), not pack content,
  and moving them later is cheap.
- Whether `estate_records.toml` wants a digest pin like the corpus manifest. Probably not — it is
  authored fixture material, not vendored third-party content — but the analogy deserves one
  paragraph in the conformance contract saying why the pin is absent.
