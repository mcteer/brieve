<!-- SPDX-License-Identifier: Apache-2.0 -->
# Research: 021 — a report compiles from records, or it says it could not

Phase 0. Measured against the tree on 2026-08-01, not inferred.

---

## F1. The governed read already exists, transport-independent, and already audits itself

FR-007 requires compilation to go through the governed, tenant-scoped evidence read, audited.
Measured — that is `read_evidence_for` in `src/surfaces/api/evidence.py:59`, and its docstring
states the reason it is a function rather than a route body:

> "Extracted from the route so MCP reaches *this* rather than reimplementing it. ADR-0033 asks
> for the same verdict on every transport, and two implementations agreeing by inspection would
> make that a measure of how carefully they were written."

It bounds by `subject.tenant_id` (never from the request), computes the SCOPED/OUT_OF_SCOPE
disposition, blanks entries when out of scope, and calls `_record_access`, which **fails the read
if the meta-audit write fails** rather than proceeding.

**Decision**: the report compiler consumes `read_evidence_for` and never reaches
`EvidenceQuery.search` directly.

**Rationale**: every property FR-007 and FR-008 ask for is already implemented once, and a
second caller of `search` would be a second answer to "who may see this" — the shape ADR-0033's
parity row exists to catch, arriving one layer below where that row looks.

**Alternatives**: reaching `search` with a hand-built `EvidenceQueryRequest` (rejected — it
duplicates the disposition logic and silently skips the meta-audit, which is the one write
`_record_access` says must not be best-effort); a new read path for reports (rejected outright,
FR-008b).

---

## F2. `Observer` already answers "cannot determine", so FR-006a needs no new concept

The clarified read-back rule needs three outcomes, not two. Measured at
`src/core/observation/types.py:17` — `ObservationOutcome` is already three-way, and the module's
docstring argues for it in the same terms this feature needs:

> "A two-way outcome would force a guess in exactly the case where guessing is the failure."

`Observer.observe(idempotency_key) -> Observation` carries `outcome` and `detail`, and the
protocol states that an implementation which cannot reach the external system **MUST** return
`CANNOT_DETERMINE`. `registry.observers()` returns observers by tool name.

**Decision**: read-back is `registry.observers().get(tool)`, called with the step's idempotency
key. `HAPPENED` → the claim is product-confirmed; `DID_NOT_HAPPEN` → the claim is contradicted
and says so; `CANNOT_DETERMINE` → `unverified_unreachable`; **no observer at all** →
`unverified_no_observer` (FR-016a).

**Rationale**: the mapping is total, and the two `unverified` reasons are kept apart because they
send a reader to different places — one to the product, one to the tool's registration.

**What this makes cheap, and it is the point**: FR-016b forbids adding observers to satisfy the
requirement. Nothing here tempts anyone to, because the absent-observer case has a defined,
honest answer rather than being a hole someone is motivated to fill with a stub.

---

## F3. Report fidelity does not fit the existing `EvalCase`, and that is the largest finding here

FR-013 says move `report_fidelity` out of `suites.py`'s `OWED` dictionary and into the suites in
force. **That is not a one-line change**, and reading the loader is what shows it.

`EvalCase` is `(id, suite, prompt, expected, recorded)` — it scores *a model's response to a
prompt*. `parse_cases` validates `case.expected in EXPECTED_OUTCOMES[case.suite]`, where the
permitted values are verbs: `deny`, `decline`, `cited`, `match`.

Report fidelity scores something else entirely: **a compiled report against the material events
of a run**. Its input is not a prompt, its expectation is not a verb, and its measure is
precision and recall rather than a single outcome. There is no `EXPECTED_OUTCOMES` entry for it,
and `parse_cases` has a bespoke error branch that fires when a case names it — written in 013 to
make the absence loud.

**Decision**: extend the case vocabulary rather than force fidelity into the prompt/expected
shape. A fidelity case names a **recorded run** and the **material events** a faithful report
must mention; scoring is precision and recall of the report's claims against that labelled set.

**Rationale**: the four existing suites all ask "did the model say the right kind of thing". This
one asks "did the compiler mention everything that mattered, and nothing that did not". Forcing
it into `expected: str` would either reduce fidelity to a boolean — losing precision and recall,
which FR-013a requires — or smuggle a serialized structure into a string field.

**Alternatives**: a boolean `expected = "faithful"` (rejected — it is the thin corpus ADR-0018
warns about, wearing the schema's clothes); a wholly separate gate outside `suites.py` (rejected
— the constitution's row is one of five in one place, and moving it out would leave `SUITES` a
list of four forever, which is the absence this feature exists to close).

**Per-pack, following the existing loader.** `load_pack_cases(pack_dir, suite)` reads
`packs/<pack>/evals/<suite>.toml`, and a report is about a run, and a run uses a pack. Fidelity
cases live where the other four live.

---

## F4. Where the corpus comes from, which ADR-0018 says is the thing most likely to be skipped

The ADR names its own failure mode: building the corpus "requires labeled material events to
score against. That corpus is also the thing most likely to be skipped under schedule pressure,
which would leave the decision nominally in force and practically unenforced."

**Decision**: the corpus is **recorded runs with labelled material events**, on the `recorded`
pattern the other four suites already use — a previously-observed run is captured once, its
material events labelled by hand, and the blocking lane scores the compiler against that
deterministically.

**Rationale**: it makes the blocking lane hermetic (no enclave, no provider, no live product),
which is what keeps a gate running; and it reuses a discipline the tree already has rather than
inventing a second one.

**The risk this does not remove, stated rather than closed**: a corpus of three easy runs passes
just as green as a corpus of twenty hard ones. Labelling is human work and no mechanism forces it
to be thorough. The mitigation available is a **floor** — the existing suites already declare a
minimum case count in `pack.toml`'s `[evals.cases]` and refuse below it — and that floor should be
set from runs that actually contain the hard shapes: a denial, an unreconcilable step, a
resumption, a model that chose nothing.

---

## F5. A requestable report grows the parity row, and the snapshot is the concrete owed work

FR-015b makes this a consequence rather than a choice. Measured: the MCP surface holds an
explicit operation map at `src/surfaces/mcp/operations.py:32`, pairing each tool name with the
API method and path (`"get_run_result": ("GET", "/runs/{run_id}/result")`), and
`transport.py:99` dispatches by the same names — with `_read_evidence` importing
`read_evidence_for` from the API package, which is the established surface-to-surface pattern.

Parity is asserted against `specs/008-northbound-api/contracts/operations.snapshot.json` by
`tests/conformance/mcp/test_surface_parity.py`.

**Decision**: one operation, added to the API router, the MCP operation map, and the MCP
dispatch table, with the parity snapshot regenerated in the same change.

**Rationale**: it is three named registration points and one snapshot, all of which exist. The
work is not the plumbing; it is remembering that the snapshot is part of it — 019's contract
carried a stale table for six analysis passes, and a snapshot is the same hazard with a
test behind it.

---

## F6. Where the code goes, decided against 020's finding rather than rediscovered

020 learned this twice in one feature: a provider call belongs in `adapters/`, a framework
mapping in `adapters/pydantic_ai/`, and core never imports either. The equivalent question here
is whether the compiler is core or surface.

**Decision**:

| Lives in | What it holds |
| --- | --- |
| `src/core/reports/` | The typed `RunReport` and `Claim`, the verification vocabulary, and `compile_report(entries, observers, ...)` — pure, taking records in and returning a report. Calls `observe()`, because `Observer` and the registry are both core. |
| `src/surfaces/api/reports.py` | The governed read (`read_evidence_for`) and the route. |
| `src/surfaces/mcp/` | The operation map entry and dispatch, reaching the same function the API route does. |

**Rationale**: the compiler is domain logic over records and must be testable without a surface,
a tenant, or an HTTP request. The *read* is governed and lives where governed reads live. Core
importing `surfaces` would be the layering inversion `tests/unit/test_core_import.py` guards, one
package over from where 020 found it.

**The seam this creates, pinned now rather than at implementation time**: `compile_report` takes
already-read entries. It cannot widen scope because it never queries — it can only compile what
the governed read already returned. That is what makes FR-008b structural rather than a promise.

---

## F7. What a report must NOT carry, found by clarification rather than by design

`get_run_result` refuses `not_permitted` when the caller is not the run's subject
(`src/surfaces/api/runs.py:183`), while `EvidenceQueryRequest` has no subject field at all. Two
scopings, deliberately different: the result is a work product, the trail is a governance record.

**Decision**: the report carries no part of the run's result payload. The `RESULT_KEY` contents
of a checkpoint are out of bounds to the compiler.

**Rationale**: a report is the first artifact able to read everything, and the first therefore
able to smuggle the subject-restricted thing out under the tenant-scoped thing's rules. Recorded
here because it was found by asking who may request a report — not by designing the report — and
the next person to widen what a report includes needs to meet this sentence.

---

## Unknowns remaining after Phase 0

**One, and it is a scale question rather than a design one.** How large a run's trail can get
before compiling a report on demand becomes impractical — the durability fixtures dispatch
400-step runs, and a report recompiles from every entry on every request. No performance target
is invented here (the spec sets none). The first measurement belongs in implementation, and the
honest position until then is that `EvidenceQueryRequest.limit` defaults to 1000 and a report
over a longer run would silently compile from a truncated read, **which is a correctness problem
wearing a performance problem's clothes** and must be handled as one.
