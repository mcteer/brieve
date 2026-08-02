# Research: 029 — estate answering at real volume

**Phase 0.** Everything below is measured — against merged `main`, the deployed enclave
(2026-08-02, tenant `tenant-local`, 236,581 readable entries), or by running the code in question.
The spec carries the three findings; this carries the mechanics that decide the design.

---

## F1 — Why the router misses: its estate vocabulary is the trail's *verbs*, not its *nouns*

**Measured**: `ESTATE_TERMS` in `routing.py` holds 22 terms — `run/runs`, `denied`, `failed`,
`changed`, `happened`, `refused`, `stopped`, `resumed`, `audit`, `trail`, `evidence`, `record/s`,
`workspace/s`, `violate/-s/-tion/-tions`, `granted`, `estate`. Every measured miss is a question
about a **thing** the trail records that the list does not name: *tools* (`TOOL_CHOSEN`,
`TOOL_OUTCOME` exist), *agents* (every run has a definition), *secrets* (the platform's own
pack reads them, `EFFECT_OBSERVED` records it), *active/used* (state words with no home).

**Decision**: grow `ESTATE_TERMS` with the trail's nouns — `tool/tools`, `agent/agents`,
`secret/secrets`, `used`, `active`, `did` is **not** added (too common). The mechanism —
deterministic term overlap, ties to estate — is untouched; only the vocabulary grows, drawn from
`AuditEventType`'s own members as the module docstring already prescribes.

**The eager-routing risk is real and has a specific shape**: *"How do I read a secret?"* carries
`secret`, and ties break toward estate by design — so it would route estate and decline, where
today it answers from the corpus. The guard is a **guidance regression set** in the routing rows:
questions that must keep routing to guidance, run alongside SC-007's estate set. If a term cannot
survive both sets, the term is wrong, not the tie-break.

## F2 — Why the read starves: one bound, one competition, and `visible` passed whole

**Measured**: `estate_answer_for` in `ask.py` computes `visible = visible_event_types(roles)` (12
types for `operator`) and passes the whole set as `event_types`; the read applies `LIMIT 1000`
across all of them. Live composition for *"What ran today?"*: `effect_observed` 383,
`pre_decision` 302, … `run_start` 60. The question's types got 6% of the window.

**Decision — two pieces, split across layers on purpose**:

- **`core/answering/focus.py`**: `focus_types(question) -> frozenset[AuditEventType] | None`.
  Deterministic term→types mapping (runs → `RUN_START/RUN_STOPPED/RUN_RESUMED`; tools →
  `TOOL_CHOSEN/TOOL_OUTCOME`; denied/refused → the authority members; secrets →
  `EFFECT_OBSERVED`; …). `None` means "no focus recognised" and the read proceeds as today.
  The ask path passes `focus ∩ visible` when the intersection is non-empty — **intersection, so
  focus can only narrow** (FR-005), and an empty intersection falls back to `visible` rather than
  refusing, because "your role cannot see the thing you asked about" must not masquerade as a
  scope refusal while FR-009 holds that question open.
- **`EvidenceQueryRequest.limit_per_type: int | None = None`**: when set, the read returns the
  newest N **of each requested type** rather than N overall. Postgres:
  `ROW_NUMBER() OVER (PARTITION BY event_type ORDER BY timestamp DESC, …)` — one query, not one
  per type. In-memory: a per-type bucket fill over the same sort. `None` preserves today's
  behaviour exactly, which is what keeps every existing caller and row untouched.

**Why the split**: the query layer stays ignorant of questions (it gains a *bound*), and the
answering layer stays ignorant of SQL (it names *types*). A `focus` parameter on the query would
put question semantics in `core/audit`, which is the fragmentation seam.

## F3 — The ordering fix is done, verified, and waiting

**State**: `fix/evidence-read-returns-the-newest-window` (commit `21e71a3`, unpushed) carries the
newest-window fix for both implementations, seven rows verified to fail against the old behaviour,
and the corrected causal story in comments. Cherry-picked as the implementation branch's first
commit. Its `test_the_newest_window_is_taken_after_scope_narrowing_not_before` row is the seed the
per-type rows extend.

## F4 — FR-006 lands on the answer, and that is what keeps sealed core closed

**Measured**: `answer_estate_question` returns a verdict object the surfaces shape into the
response; `ASK_ANSWERED`'s payload is sealed core with five features of additive history and a
review discipline attached.

**Decision**: the read returns, alongside entries, **what was matched vs returned per type**
(a `SearchResult` carrying `entries` plus `window: dict[type, (returned, matched)]`, or an
equivalent second channel — exact shape is tasks-level). The estate answer carries a
`window_note` the surfaces render: *"Based on the 200 most recent run records of 1,847 today."*
**The `ASK_ANSWERED` record does not change** — the trail already carries the narrowed request in
the access record (ADR-0035), which serves the investigator; the answer serves the asker. Result:
no Principle V review, third feature running.

The matched-count is one `COUNT(*) OVER (PARTITION BY event_type)` in the same query — measured
as available in the window-function form F2 already requires; no second round-trip.

## F5 — Where the rows live, and the honest limit of the differential

**Measured**: the in-memory implementation is exercised hermetically everywhere;
`PostgresEvidenceQuery` behaviour rows run only in the enclave lane (`tests/conformance/api`,
enclave-marked). The window fix's rows cover the in-memory twin hermetically and the SQL by
inspection.

**Decision** (FR-008): property rows written once and parametrized over implementations — the
in-memory one in `make check`, the Postgres one in the enclave lane against seeded thousands.
Plus a hermetic SQL-shape row (the query must carry `PARTITION BY` exactly when `limit_per_type`
is set). **What is not claimed**: a fully hermetic behavioural differential — that would need a
fake Postgres, a new dependency asserting fidelity to a database it is not. The contract states
this split; pretending otherwise is how finding three survived.

## F6 — Volume fixtures are cheap enough to run in the blocking lane

**Measured**: the InMemory sink appends ~10k entries in well under a second; the window rows
already build hundreds. SC-002's hermetic form uses thousands of entries with the live tenant's
measured skew (383:60 against the question's types), which is the composition that actually
starved the read.

## F7 — What is recorded for decision, not built

- **`operator` visibility of authority records** (FR-009): the fourth finding stands as designed
  until decided otherwise.
- **The eval-suite/role mismatch**: 025's `estate_state` suite scores *"Which runs were denied?"*
  citing an `authority_denied` record — a question no `operator` can ask in production. Decision
  owed: re-aim the suite at an operator-visible question, or score it explicitly as
  `compliance-analyst`. **Not resolved here**; a qualified cell measuring something unreachable is
  a Principle VIII question, and this feature does not touch the matrix.

## Open for tasks, not for plan

- The exact term→types table (guarded by SC-007 + the guidance regression set either way).
- The `SearchResult` shape vs a parallel counts channel.
- Whether the portal's window note names types or stays aggregate — a rendering call, judged by
  the a11y and component rows.
