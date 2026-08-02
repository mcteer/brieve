# Research: 026 — asking binds to the Qualified Model Matrix

**Phase 0.** Measured against merged `main` on 2026-08-02. One finding decides where the code may
NOT live; one dissolves the run-id collision the spec's assumptions flagged; one names the real
cost of the refuse-by-default decision, which is in the test fixtures rather than in production.

---

## F1 — Resolution lives in `core.authority`, because `core.answering` is forbidden to touch it

**Measured**: 025's never-acts rows read the answering path's **imports**:
`test_the_path_cannot_reach_a_tool_at_all` forbids any import containing `authority` in
`answer.py`, and the estate/routing rows forbid `("registry", "authority", "tools", "dispatch")`.
Those rows are the executable form of ADR-0039, and they would fail the obvious design — a
`core/answering/binding.py` that imports `core.authority.matrix`.

**Decision**: the binding record's parser and the ask-cell resolver live in
**`core/authority/ask_binding.py`**, beside `ceiling.py` and `matrix.py`, which parse the same
family of operator-authored record. The **surface** (`surfaces/api/ask.py`) calls it *before* the
answering path is entered — the same ordering 020's entrypoint uses: `resolve_bound_model`
validates, and only then does `build_chooser` construct anything.

**Rationale**: the never-acts rows stay exactly as they are, and they keep meaning what they mean.
An answering path that could read authority records would be an answering path one import away
from reading grants. The surface already sits above both packages; ordering there is enforceable
by the same provider-call-count rows the spec demands.

**Rejected**: putting resolution in `core.answering` and widening the never-acts allowlist. A row
whose forbidden-word list grows an exception the same week it would have fired is not a row.

---

## F2 — The binding record: one path, one shape, the ceiling's discipline

**Measured**: `parse_ceiling_record` and `parse_matrix_record` both refuse a missing or unsupported
`schema_version` with `ResolutionRefused(reason_code="unsupported_schema_version")`, and
`MatrixSource`'s docstring already distinguishes *unreadable* from *empty*: refused loudly when
absent, because treating an outage as an empty matrix would make every definition look unqualified
during an incident. The run role's Vault policy grants `data/model-matrix` and
`data/definition-bindings`, asserted by `test_matrix_is_readable`.

**Decision**: an **ask-binding record** at `harness-authority/data/ask-bindings`:

```json
{"schema_version": 1, "guidance_cell": "vault:anthropic/claude-opus@5:ask", "estate_cell": "..."}
```

Parsed by the ceiling's rules — versioned, refused when malformed, refused when absent, and a cell
reference that names a role other than `ask` refused at parse (`malformed_record`) rather than at
resolution, so a mis-authored binding fails when written about, not when first asked through.
Either cell may be omitted: **a source with no cell named refuses for that source alone**
(FR-005a).

**The reachability question is deployment work and is named now**: the surface that answers asks
must be able to read the two paths, which means a Terraform policy change in
`infra/environments/dev` plus a conformance row on the pattern of `test_matrix_is_readable` —
a grant present in HCL and a grant that is effective are different claims, which 010 already paid
to learn.

---

## F3 — Substitution rides the ask record, which dissolves the run-id collision

**Measured**: `MATRIX_FALLBACK`'s documented payload carries `run_id` — the schema comment says the
*caller* records it because the resolving module holds neither sink nor tenant. An ask has no run
id, so reusing the event as-is would either fabricate one or generalise a second sealed-core
member's documented payload.

**Decision**: **no new event, no reuse of the run-shaped one.** The `ask_answered` payload —
already touched by 024 (`source`) and 025 (`source` semantics) — gains three fields:

| Field | Meaning |
| --- | --- |
| `cell` | The cell that authorised the answer — the one actually used |
| `bound_cell` | The cell the binding named |
| `cell_disposition` | `pinned` \| `fallback:<reason>` \| `refused:<reason>` |

An ask consults exactly one model, so which cell authorised it — and whether it was the named one —
is an **attribute of the ask**, the same argument 024 made for `source` over a separate routing
event. FR-006's "substitution recorded naming pinned, used, and reason" is satisfied by one record
with all three, on the stream the investigator is already reading.

**This is a sealed-core touch, the third additive change to this payload in three features.**
Principle V review owed (Dan McTeer, before merge) — and the plan says so now, because 024's plan
asserted otherwise and was proven wrong, while 025's declared it up front and was not.

---

## F4 — Refusals are dispositions, and the vocabulary distinguishes the three failures

**Measured**: the ask record's `disposition` field already carries `answered` / `declined` /
`provider_unavailable` / `scope_empty` — 025 added the last without ceremony, because disposition
values are payload content, not enum members.

**Decision**: three new dispositions, each recorded via the existing `record_ask` before the
refusal is returned (SC-008 — a refused ask still shows someone asked):

- `unbound` — no binding record, or none for this source. An operator has not decided.
- `unqualified_cell` — the binding names a cell the matrix does not qualify (absent, withdrawn, or
  wrong role). An operator decided, and the decision does not hold.
- `matrix_unreadable` — the fabric could not be read. An outage, not a governance state (SC-004).

**Rationale**: FR-002's distinguishability lands in the field an investigator already filters on,
and the caller-facing refusal can carry the same word — none of the three leaks anything a caller
could not already infer from being refused.

---

## F5 — The real cost is in the fixtures, and it is paid explicitly, not defaulted away

**Measured**: `served.py` configures neither `ask_provider` nor `ask_model` — every deployed
surface already answers 503, so refuse-by-default changes nothing operationally. What it does
change: **every existing ask row that answers** (parity, routing, estate bounding — ~20 rows across
three files) currently gets an answer with no authority arranged, and under FR-004a they would all
refuse.

**Decision**: `surface_under_test` gains an `ask_authority` collaborator — shared between both
surfaces like the seven before it — and a harness helper `qualified_ask_authority(model=...)`
builds an in-memory binding + matrix pair that qualifies the given model for both sources. Rows
that answer call it **explicitly**; rows that test refusal pass nothing and get the default.

**Rejected, and this is the trap**: having the fixture auto-qualify whatever provider is injected.
That recreates *"a configured provider is a qualification"* inside the test harness — the exact
equation this feature exists to break — and every refusal row would then be testing an override
rather than the default.

---

## F6 — What must not change

- **`resolve_with_fallback` is reused untouched.** Its no-third-branch property is the guarantee;
  a second resolver would be a second place for the branch to grow back.
- **`core.answering` modules gain no imports.** The never-acts rows are the check (F1).
- **The blocking lanes stay credential- and enclave-free** (FR-009): in-memory sources in tests,
  fabric-backed ones only in assembly.
- **No new operation, no response-shape break**: a refusal is the existing refusal shape with a
  new reason; an answer's response body is unchanged (the cell lands in the trail, not the body —
  a caller needs the answer, an investigator needs the authorisation).
- **`fixture:plan` cells and the run path**: untouched. This feature adds `ask` cells to the dev
  matrix record as deployment data, qualifies nothing, and changes no run behaviour.

---

## Open for tasks, not for plan

- Whether `qualified_ask_authority` lives in `tests/harness/api_fixtures.py` or its own harness
  module. Cosmetic; decide at the first use.
- Whether the dev enclave's Terraform seeds an example ask-binding record alongside the policy
  grant, so `make dev-up` produces a bindable surface. Convenient, and honest only if the seeded
  binding names cells the matrix actually holds.
