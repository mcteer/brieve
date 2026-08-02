<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 027 — how the platform holds a model credential

---

## Who runs these rows

| Group | Where | Needs |
| --- | --- | --- |
| Reader, refusal vocabulary, no-cache | `tests/component/` | Nothing |
| Three-refusal distinction, never-persisted, no-env-fallback, revocation | `tests/conformance/answering/` | Nothing — swept by the first conformance recipe line |
| Both paths, one mechanism | `tests/conformance/answering/` + a run-path row | Nothing |
| Credential path readable from the fabric | `tests/conformance/identity/` | The enclave lane |
| **A real answer through the deployed surface (SC-001)** | Served surface, real vendor | A credential in the store, **Dan McTeer** |
| **Revocation on a live enclave (SC-003)** | Served surface | **Dan McTeer** |
| **Principle V review** | `ASK_ANSWERED` gains `model_authority` | **Dan McTeer, before merge** |
| **The constitution amendment** | `.specify/memory/constitution.md` v1.4.0 + ADR-0058 | **Dan McTeer** (security-maintainer review), **merges with this feature** |

| | What it is | Who | Status |
| --- | --- | --- | --- |
| Constitution amendment | Two named exceptions; the static-key sentence rewritten | **Dan McTeer** | **Owed — a deliverable, not a follow-up** |
| Principle V review | One additive reference field on a sealed-core record | **Dan McTeer** | **Owed — gates this PR** |
| SC-001 real answer | A person gets an answer from the deployed surface | **Dan McTeer** | **Owed** |

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

**The same mechanism serves both paths (SC-002, FR-003).** The ask path and a run binding a
non-fixture model both obtain material through the one reader — asserted by both reaching
`BrokeredModelCredential`, not by two doubles that happen to agree.

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
assert only that the running system and the amended text **agree** (SC-007): a deployment holding
a workload-persisted key fails a check.

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
