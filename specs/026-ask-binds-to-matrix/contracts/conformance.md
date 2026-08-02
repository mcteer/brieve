<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 026 — asking binds to the Qualified Model Matrix

---

## Who runs these rows

| Group | Where | Needs |
| --- | --- | --- |
| Parsing, resolution, disposition vocabulary | `tests/component/` | Nothing |
| Provider-never-called, per-source refusal, record-on-refusal, fixture-default-refuses | `tests/conformance/answering/` | Nothing — swept by the first conformance recipe line (not the host_enclave line; the 024 inert-entry lesson) |
| Refusal parity — all three dispositions on both surfaces | `tests/conformance/mcp/test_ask_parity.py` | Nothing |
| **Binding record readable from the fabric** | `tests/conformance/identity/`, `test_matrix_is_readable` pattern | The enclave — joins `make conformance`'s existing lane, no new named runner |
| **Principle V review** | `ASK_ANSWERED` gains `cell`, `bound_cell`, `cell_disposition` | **Dan McTeer**, before merge |

| | What it is | Who | Status |
| --- | --- | --- | --- |
| Principle V review | Three additive payload fields on a sealed-core record — the third additive touch to this payload in three features | **Dan McTeer** | **Owed** |

---

## What these rows assert

**An unqualified model is unreachable, verified at the provider (SC-001).** The provider counts
its own calls, and with no qualified cell the count is zero — on both surfaces, for both sources.
A response-level check would pass a refusal that had already called the model; only the provider's
own count shows "unreachable, not merely unused."

**A withdrawn cell refuses like an absent one (SC-002), and a `plan` cell authorises nothing here
(SC-003).** Inherited from `resolve_with_fallback` and asserted anyway — inherited properties
that nobody asserts are the ones that quietly stop being inherited.

**A binding for one source does not license the other (SC-003a).** Guidance bound and estate
unbound answers guidance questions while refusing estate ones, in the same session.

**No deployment value supplies a binding (SC-003b, FR-004a).** A surface with a provider injected
and no authority refuses `unbound`. **The fixture's default is that refusal** — a row asserts
`surface_under_test` with a provider and no explicit authority refuses, because a harness that
auto-qualified injected providers would rebuild the exact equation this feature breaks.

**The three refusals are distinguishable (SC-004, FR-002)** — `unbound` / `unqualified_cell` /
`matrix_unreadable` — in the trail, via the disposition the investigator already filters on. An
outage is not a governance state.

**Every answer's record names its authorising cell (SC-005)**, and a substitution names the bound
cell, the used cell, and the reason on the same record (SC-006). Fallback reaches only another
qualified `ask` cell — the no-third-branch property, exercised for asks.

**A refused ask still records that someone asked (SC-008).** 022's rule, applied to three new
refusal shapes.

**Both surfaces refuse identically (SC-007)** — same disposition, same reason text, for all three
refusals.

**Deleting the binding check fails a named row (SC-009).** The provider-never-called row is that
row: remove the resolution step and it counts a call.

**The binding record is readable where the surface runs.** A grant present in HCL and a grant
that is effective are different claims — 010's lesson, re-applied to the two paths this feature
reads.

---

## What these rows refuse to assert

**They do not assert any cell is green.** Qualification is evaluation's to earn and the matrix's
to record; these rows arrange cells in fixtures and assert the *refusal machinery*, not the
qualification.

**They do not assert the dev matrix contains `ask` cells.** Seeding one is deployment data; the
platform's behaviour when none exists — refuse — is exactly what SC-001 asserts.

**They do not assert 024's SC-006 retroactively held.** It did not. FR-012 replaces the contract's
flat assertion with a pointer to the rows here; the history of the gap stays in this spec and in
026's traceability, not papered over.

**They do not assert the core answer functions are unreachable without a cell.** The binding
governs the **surfaces** — the only places a real provider exists — and the eval lanes drive
`answer_question` / `answer_estate_question` directly with recorded providers, by design: core is
handed its provider the same way it is handed its records, and the never-acts rows are what keep
that hand-off from widening. The provider-never-called row asserts the surfaces; it does not
claim core is unreachable, and reading it that way would be wrong (analysis C2).

**They do not assert the substitution path against a live vendor.** `available` is arranged in
fixtures; the live lane's cost buys qualification evidence, not fallback choreography.

---

## The row that would have caught the original problem

**Provider-never-called, counted at the provider.** 024 wrote *"an unqualified cell refuses before
any provider call"* into its contract with no row behind it, and two features shipped answering
paths that never consulted the matrix. A row that counts calls at the provider fails the moment
the resolution step is absent — which is a check on the claim, not on the prose around it.

## FR-012 — the 024 contract correction

On completion, `specs/024-portal-answering/contracts/conformance.md`'s line *"An unqualified cell
refuses before any provider call"* gains the row reference and a dated note that the assertion was
unbacked between 024's merge and 026's — recorded plainly, because the defect class this lineage
keeps closing is precisely a claim nobody re-measured.


---

## Status on completion (2026-08-02)

| Row group | Result |
| --- | --- |
| Parsing, resolution, disposition vocabulary (`tests/component/test_ask_binding.py`) | ✅ 17 rows |
| Provider-never-called, fixture-default, withdrawn, wrong-role, unreadable≠unbound, per-source, answered-records-cell, precedence, substitution ×5 | ✅ 13 rows |
| Refusal parity — all three dispositions, both surfaces | ✅ 3 rows |
| `make check` | ✅ 963 |
| Hermetic conformance | ✅ 226 (was 215) |

**Two spec names became existing platform names**, and the reason is anti-fragmentation rather
than convenience:

- `matrix_unreadable` as a *reason code* is **`fabric_unreachable`**, which already means "the
  trust fabric did not answer". A second code for one concept would split every investigator's
  filter. It remains `matrix_unreadable` as the ask record's **disposition**, which is the
  ask-facing vocabulary.
- Only **`unbound_ask_source`** was genuinely new in `RESOLUTION_REASONS`, registered with the
  distinction that earns it: `no_binding_for_role` is a fact about a *definition*, and an ask has
  none.

**SC-002's property is stronger than the spec wrote it.** `resolve_with_fallback` collapses
absent, withdrawn and wrong-role alike to `no_qualified_fallback` once candidates are exhausted —
so the three are indistinguishable *at the seam*, not merely mapped to one disposition afterwards.
