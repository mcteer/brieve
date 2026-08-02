<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 027 — how the platform holds a model credential

---

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| Reader, refusal vocabulary, no-cache, one-read | `tests/component/test_model_credential.py` | Nothing | **In force** — 10 rows |
| Three-refusal distinction, never-persisted, no-env-fallback, revocation, in-flight | `tests/conformance/answering/test_model_credential_posture.py` | Nothing — swept by the first conformance recipe line | **In force** — 13 rows |
| Both paths, one mechanism | same file (structural, by parsing) | Nothing | **In force** |
| Constitution agreement + no vendor key in a jobspec | `tests/conformance/identity/test_posture_matches_constitution.py` | Nothing | **In force** — 4 rows |
| Credential path readable, and both roles carry the grant | `tests/conformance/identity/test_matrix_is_readable.py` | The enclave lane | **Written; runs at `make conformance`** |
| Eval-lane exemption, stated at the lane | `tests/evals_live/test_gates_live.py` | Nothing (the row does not call a vendor) | **In force** |
| **A real answer through the deployed surface (SC-001)** | Served surface, real vendor | A credential in the store, **Dan McTeer** |
| **Revocation on a live enclave (SC-003)** | Served surface | **Dan McTeer** |
| **Principle V review** | `ASK_ANSWERED` gains `model_authority` | **Dan McTeer, before merge** |
| **The constitution amendment** | `.specify/memory/constitution.md` v1.4.0 + ADR-0058 | **Dan McTeer** (security-maintainer review), **merges with this feature** |

| | What it is | Who | Status |
| --- | --- | --- | --- |
| Constitution amendment | Two named exceptions; the static-key sentence rewritten. Landed in this PR (v1.4.0, ADR-0058) | **Dan McTeer** (security-maintainer review) | **Approved 2026-08-02**, at merge |
| Principle V review | One additive reference field on a sealed-core record (`model_authority` on `ASK_ANSWERED`; `MODEL_GATE` untouched) | **Dan McTeer** | **Approved 2026-08-02**, before merge |
| SC-001 real answer + SC-003 revocation | Ask through the deployed surface, rotate, delete (quickstart §5) | **Dan McTeer** | **Owed — and blocked on out-of-scope work; see below** |
| `make conformance` on a live enclave | Includes the readability and grant rows | **Dan McTeer** | **Done 2026-08-02, exit 0** |

---

## What these rows assert

**No workload persists the credential (SC-004, SC-005).** It is fetched at task start, held in
process memory, and appears in **no** checkpoint, log, trail entry, or model context. The rows
read each of those sinks and find the reference, never the value.

**A missing or revoked credential refuses `credential_unavailable` — before any vendor contact**,
and **never falls back to the environment**. The env var is deliberately **set** in that row, so
a fallback bug would make it pass; only a true refusal does (plan, Principle III watch item).

**Three failures are distinguishable (SC-006):** `credential_unavailable` (fetch refused) ≠
`unqualified_cell` (026, cell not green) ≠ `provider_unavailable` (vendor down). Checked in the
order the design fixes: cell, then credential, then vendor.

**Revocation takes effect with no restart (SC-003).** A working path, the credential removed from
the store, the next ask refusing — same process, and the moment locatable in the trail.

**The same mechanism serves both paths (SC-002, FR-003) — asserted STRUCTURALLY, and the scope is
narrower than this contract first claimed.** `_run_task` resolves authority under an attested
workload identity, so no hermetic row can drive the run path. What the rows assert is that both
assemblies name `BrokeredModelCredential` and no rival credential source, and that both check in
the **same order** — cell, then credential, then construction. That second half matters as much as
the first: a reader shared by two call sites that check in different orders gives two different
answers to *which failure is this*.

The behavioural run-path half — a dispatched allocation reading the credential as `agent-run` — is
**owed at the deployed demonstration**, because the only place the run role exists is inside an
agent allocation. The enclave rows assert the grant is applied to both roles, which is a different
and weaker claim, and it is named as such rather than allowed to stand in.

**The eval lane keeps its env path, and says so where it lives (FR-013a).** A row in
`tests/evals_live/` asserts `client_and_model` still honours `EVAL_PROVIDER_API_KEY`, with the
comment naming the exemption — so the boundary is legible at the lane, not only in this contract.

**`model_authority` is a reference, never a value (FR-008).** The row asserts the field matches
the `vault:model-credentials/...@v<n>` shape and contains no substring of the actual key.

**The trail names who the call was for, though it was made as the platform (SC-004a).** The
asker's `subject_user_id` is on the record beside the platform-authority reference.

---

## What these rows refuse to assert

**They do not assert per-tenant billing or limits.** One vendor account, shared — recorded as a
known limitation (spec FR-005b), and a row here would assert a property the posture does not have.

**They do not assert a task in flight survives revocation.** It completes on the authority it was
issued, exactly like every other per-task grant. Revocation binds the **next** task; the row
tests that, not an impossible mid-flight interruption.

**They do not qualify any cell.** The matrix decides which model may be called (026); this feature
only supplies the means, and arranges cells in fixtures.

**They do not assert the constitution's *content* is correct** — that a second exception is the
right call is the human amendment's judgement, reviewed by the security maintainer. The rows
assert only that the running system and the amended text **agree** (SC-007).

**And SC-007's agreement check covers the CONFIG half, not the runtime half.** This is a
correction to what this contract originally implied. Three claims live in the amended sentences:
the text names two exceptions (checkable), no jobspec hands a workload a vendor key (checkable in
HCL), and no workload persists a fetched key (**not** visible to a config grep). The third is
asserted where it is observable — at the trail, the response body and the checkpoint, in the
answering conformance file — and the identity row says so in its own docstring. A row that quietly
covered two thirds of a requirement would be worse than two rows that each state their scope,
because the gap would be invisible from the green.

---

## The row that would have caught the original silence

**No-env-fallback with the env var set.** Three features left `EVAL_PROVIDER_API_KEY` as the only
way anything called a model, and the easiest "make the surface answer" fix is to let the
production path read it too. That would work, ship, and quietly make the eval lane's dev secret
the production credential. The row sets the var and asserts the fetch still refuses — so the
convenient wrong fix fails a gate instead of reaching production.

## Constitution agreement (SC-007)

A check compares the running deployment's posture against the amended text: a jobspec passing a
vendor key as a workload env var, or a workload persisting a fetched key, fails. The amendment and
the check land together, because a constitution that describes what the platform *should* do while
the platform does otherwise is the exact defect US3 names.

---

## What the implementation changed about this contract

Recorded rather than silently corrected, because a contract that only ever describes what happened
is not one that can be wrong.

**The reader has one method, not two.** The plan specified `fetch()` and `credential_reference()`.
Separate calls are separate reads, and a rotation landing between them would have the trail record
a generation the call did not use — on a record whose entire value is *which generation authorised
this*. `obtain()` returns both from one read, and a row asserts they move together.

**Three pre-existing gates fired, and all three were amended in the open rather than worked
around.** `test_no_static_credentials.py` gained exactly one named module exemption, pinned by
count, with a separate no-exemption row over `src/surfaces/` so widening it fails twice.
`test_core_is_product_blind.py` gained an allowlist entry: the reference prefix `vault:` names
where the authority came from, which is the reference's whole content.
`test_provider_key_is_dev_lane_only.py` matched the variable name in a docstring **explaining that
the production path must never read it** — the fifth check in this repository to match prose
instead of code, and the point at which the stripper was shared rather than the sentence rewritten.

The rejected alternative in the first case is worth keeping: renaming the KV field so the matcher
would not see it. That would have left the gate green while the credential existed, and a gate
that passes by vocabulary is worse than no gate.

**Two latent defects were found and fixed while wiring.** `LiveEstateProvider` with no id mapping
offered every record as `id: ?` and resolved every citation to `unresolvable:?`, so the first
deployed estate answer would have dropped every claim and read as *the records do not support an
answer*. And the conformance-lane marker check matched `mark.enclave` inside a docstring, which
would have reported a row that does not exist while a real orphaned row elsewhere stayed findable
only by luck.

## The two reviews, and that they gated

Both were approved by Dan McTeer on 2026-08-02, **before the merge rather than after it**. That
ordering is the discipline the just-closed Principle V review established, and this is the first
feature to hold to it: 024, 025 and 026 each merged with a review recorded as owed, and when it
was finally performed it rejected `corpus_digest`'s generalisation — a defect that had been in
merged code for three features because nobody had looked.

The scope reviewed: one additive field on `ASK_ANSWERED`, carrying a reference and never a value,
with `MODEL_GATE` deliberately untouched; and two sentences of Principle IV, moved together.

## SC-001 is not reachable inside this feature's stated scope

Stated plainly rather than left to be discovered at the demonstration.

The deployed answer needs three things. Two are delivered and verified against the live enclave:
`ASK_MODEL` reaches both surfaces, and the credential mount, policy, record and per-role grants are
applied and readable. The third is **a Qualified Model Matrix cell for a real model in the `ask`
role**, and the enclave holds only `fixture:` cells.

**That cell cannot be written by hand.** Principle VIII permits model use only through eval-gated
promotion; authoring a cell directly would fabricate a qualification, which is precisely what the
matrix exists to prevent — and 026 exists because a governed answering path was shipped without
one. Earning it requires a clean `make evals-live` run, which this feature's spec lists under
*Deferred and NOT in scope*: "promoting the `ask` cell to `live` (which needs a clean full-lane
run and is unrelated to posture)".

**The tension was in the spec from the start.** SC-001 promises an outcome that depends on work the
Assumptions section defers. Implementation did not create it and cannot dissolve it: the two
remaining actions — qualifying the cell, and writing a real vendor credential into the enclave —
are the maintainer's, and neither belongs to a posture feature.

What the posture itself proves without them: the credential is brokered per task, refuses
distinguishably, never leaks, never falls back to the environment, revokes without a restart, and
is reached by one reader from both paths. All of that is asserted by rows in the blocking lanes,
and the enclave lane confirms the deployment matches.
