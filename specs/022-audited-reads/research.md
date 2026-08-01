# Research: 022 — the trail records who looked

**Phase 0.** Everything below was measured against the repository and, where noted, the running
service — not inferred from the spec.

---

## F1 — The meta-audit pattern already exists, and it is the template

**Decision**: Adopt the shape `surfaces/api/evidence.py` already uses for recording evidence
access, rather than inventing a second way to record a read.

**Measured**: `_record_access` writes to a per-tenant stream named by `evidence_stream_for()`,
carries the *shape* of the query and never the rows, and raises when the write fails. All three
properties are what 022 needs, already argued and already shipped.

**Rationale**: Principle VII. A second mechanism for the same act would mean two answers to "how
is a read recorded", and the existing one has the better documentation.

---

## F2 — The reader stream is stable per tenant, and the reason is already written down

**Decision**: `RECORD_ACCESS_STREAM_PREFIX = "record-access"`, one stream per tenant, stable
across reads. Never a fresh correlation id per read.

**Measured**, quoting the existing constant's own note:

> *"Stable, not per-read: a fresh correlation ID each time would make every record a chain of one
> — linked to nothing and removable without trace, which defeats the reason a record of who read
> what exists at all."*

**Rationale**: That argument transfers without modification. A per-read stream is not a chain.

---

## F3 — A separate stream from `evidence-access`, not the same one

**Decision**: A second stream, `record-access:{tenant_id}`, distinct from
`evidence-access:{tenant_id}`.

**Alternatives considered**:

- **Reuse `evidence-access`.** Genuinely attractive: one chain per tenant, and one query answers
  "who looked at anything". **Rejected on volume profile.** Evidence reads are deliberate acts by
  someone conducting a review; `list_runs` is what a connected editor calls while idling. Merging
  them buries the high-signal events under routine listing noise, in the one stream an auditor
  goes to first. The trail is never sampled (Principle IX), so this cannot be corrected later by
  filtering at write time.
- **One stream, discriminated by event type.** Same burial problem, plus it makes every existing
  `evidence_read` query ambiguous about which plane it covers.

**Consequence to state plainly**: an auditor asking "who looked at anything in this tenant" now
queries two streams. That is the cost of keeping the evidence plane's records legible, and it is
worth naming in the ADR-0035 amendment rather than discovering.

---

## F4 — Three new `AuditEventType` members, not a reused one

**Decision**: Add `RECORD_READ`, `RECORD_READ_REFUSED`, and `THREAD_CREATED`.

**Alternatives considered**:

- **Reuse `EVIDENCE_READ` / `EVIDENCE_READ_REFUSED`.** **Rejected.** Those members mean *someone
  read the audit plane*. An operator asking who read the trail would get run listings back, and
  any gate row over evidence reads would silently start counting something else. Overloading a
  member is not additive — it changes what already-written entries appear to mean.
- **One member with a `kind` field.** Rejected on precedent: the existing pair is two members, and
  the refusal-vs-permitted split is exactly the distinction FR-007 needs to be queryable rather
  than filterable.

**`THREAD_CREATED` is not a read** and does not belong in the reader stream. **Measured**:
`THREAD_DELETED` writes to `record.correlation_id` — the thread's own stream. `THREAD_CREATED`
goes to the same place, which is what makes the pair symmetric and closes FR-002a's
deleted-but-never-created hole.

---

## F5 — Sealed core: the additive-member argument holds for a third time

**Decision**: Add the members to `core/audit/schema.py` and extend the pinned-digest row.

**Measured**: `tests/unit/test_audit_chain.py::test_widening_the_event_vocabulary_moves_no_existing_hash`
pins one entry's digest as a literal and asserts each feature's new members are genuinely present.
020 established it; 021 reused it. The hash covers an entry's *own* `event_type` value, not the
set of possible values, so an additive member moves nothing.

**Obligation**: the row's assertion list grows by the three new members, and the pinned literal
must remain byte-identical. If it moves, the encoding moved and every prior entry is at risk —
which is the whole reason the literal is not recomputed.

---

## F6 — Both transports already share the implementations, so parity is structural

**Decision**: Record inside the shared functions, not in either transport.

**Measured**: `surfaces/mcp/transport.py::_list_runs` imports and calls
`surfaces/api/runs.py::list_runs_for`. The same holds for `create_thread_for`,
`thread_detail_for`, `list_threads_for`. Both surfaces reach one implementation.

**Rationale**: FR-008 asks for identical behavior on both surfaces. Recording in the shared
function makes that structural — there is no second place for it to differ. Two matching
implementations would make parity a measure of how carefully they were written, which is what the
evidence path's own docstring already says a conformance row cannot check.

---

## F7 — The fail-closed raise must be a core error, and the existing one is not

**Decision**: The six new call sites raise a core error that both transports map to the same
verdict. **Do not copy the existing raise.**

**Measured, and this is a live defect in shipped code**: `_record_access` raises
`fastapi.HTTPException(503)` from a transport-independent function, and
`surfaces/mcp/transport.py::_read_evidence` does **not** catch it. On the API surface an
unrecordable evidence read answers 503 with a stated reason; on the MCP surface the same failure
escapes as an uncaught exception. The failure path has no parity, in the one operation whose
docstring argues most carefully for parity.

**Scope call, stated rather than absorbed**: this is pre-existing and is *not* one of 022's six
covered operations. But 022 introduces the identical fail-closed pattern to six more call sites,
so getting it right here means introducing a core error type — and once that exists, converting
the evidence path is a small consistency change in the same file family. **Recommendation**:
include it, flagged as an adjacent fix rather than folded silently into the feature. If it is cut,
022 must still not copy the HTTPException shape into six new places.

---

## F8 — The disposition belongs on the operation, as a field with no default

**Decision**: Add a required `audit_disposition` field to `McpOperation`.

**Measured**: `McpOperation` is a frozen dataclass with five fields, all required.
`tests/component/test_operations_audited.py::test_the_operation_list_here_matches_what_shipped`
guards a hand-kept list and has already caught one miss (012's five thread operations).

**Rationale**: FR-009 asks that an operation cannot ship without a disposition. A hand-kept list
requires someone to notice; a required constructor field makes omission a construction error. The
existing guard is good and stays — it covers a different question — but it is not what FR-009
needs, and the file's name suggesting otherwise is precisely how this gap survived to seventeen
operations.

---

## F9 — The governance claim must be derived, not asserted

**Decision**: Generate the coverage sentence in the MCP surface's instructions from the operation
catalogue's dispositions.

**Measured**: the claim is currently a hand-written string literal in
`surfaces/mcp/served.py:331` — *"Every operation executes as the calling user and is recorded in a
tamper-evident trail."* Nothing connects it to behavior.

**Rationale**: FR-011 requires a check that fails when the description overclaims. A check
comparing the sentence to a second hand-written copy of itself would have passed every day this
gap existed — that is the failure mode, not a hypothetical. Deriving the sentence from the
dispositions means the claim cannot overclaim without the catalogue lying first, and the catalogue
is checked against measured behavior by FR-002.

**Alternative considered**: keep the sentence hand-written and add a test asserting it matches the
dispositions. Rejected — it is one more thing to keep in sync, and the sync is the thing that
failed.

---

## F10 — What must not change

**Measured constraints carried into design:**

- `get_run_result`'s subject-only restriction is untouched (FR-015). 021's `RunReport` omission
  depends on it.
- `list_agent_definitions` and `get_agent_definition` gain nothing, and SC-011 pins that so a
  later widening is a decision rather than a drift.
- `start_run` / `stop_run` are already covered by `authority_issued` / `run_start`. Adding records
  there would double-count the same act.
- No read record carries content (FR-006). The existing `query_shape` payload is the model: shape,
  counts, and identifiers — never rows.

---

## Open for tasks, not for plan

- Whether `RECORD_READ` payloads carry a `result_count`. The evidence path does, and it is useful
  for spotting a caller enumerating a tenant. Cheap; decided at implementation.
- Whether the adjacent F7 fix lands in this feature. Recommended, flagged.
