<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 025 — estate-state answering

---

## Who runs these rows

| Group | Where | Needs |
| --- | --- | --- |
| Routing (both directions), scope narrowing, estate path, scorer | `tests/component/` | Nothing |
| Never-acts over the estate path, differential entitlement, caller-indistinguishability | `tests/conformance/answering/` | Nothing — swept by the first conformance recipe line; **deliberately not on the host_enclave line**, whose markers would deselect these rows (the inert-entry lesson, learned in 024) |
| Estate verdicts on both surfaces | `tests/conformance/mcp/test_ask_parity.py` | Nothing |
| Reauthored `estate_state` via the product path | `make evals` | Nothing |
| **FR-012 — name the 2026-08-01 failure** | Old suite, live model, per-case output | A paid credential, **Dan McTeer** |
| **Live qualification of the reauthored suite** | `make evals-live` | A paid credential, **Dan McTeer** |
| **Principle V review** | `ASK_ANSWERED` gains `source`; `corpus_digest` generalised for estate asks | **Dan McTeer**, before merge |

**Ordering that matters**: FR-012 runs **before** the reauthoring lands. The old failure is named
while the failing suite still exists to name it; a reauthoring that landed first would replace the
evidence of what failed with a suite that never contained it.

| | What it is | Who | Status |
| --- | --- | --- | --- |
| Principle V review | One additive payload field on a sealed-core record, plus the documented generalisation of `corpus_digest` | **Dan McTeer** | **Owed** |
| FR-012 — the named failure | Old `estate_state`, vault pack, live model, per-case output printed; finding recorded here | **Dan McTeer** | **Owed** |
| Live qualification | `make evals-live` over the reauthored suites | **Dan McTeer** | **Owed** — the `ask` matrix cell stays `fixture` until this passes |

---

## What these rows assert

**Two subjects, one question, answers that differ exactly by entitlement (SC-001).** Verified by
comparison of the two answers, not by inspection of either.

**Every reference resolves into the asker's own scoped read (SC-002).** Not "exists in the trail" —
allowed-to-this-asker. An unresolvable reference drops its claim; a claimless answer declines.

**No verdicts (SC-003).** The rows check for the vocabulary of adjudication — compliant, passing,
healthy, safe — in answers that cite violations, because that is where the temptation lives.

**Asking reaches no effecting tool (SC-004)** — the existing never-acts rows extend over the
estate path and the router, including instruction-shaped estate questions (*"fix the workspaces
that violate this control"*), asserted by exercising the path and by reading its imports.

**Routing is right in both directions (SC-009).** An estate-shaped question never consults the
corpus. A guidance-shaped question never consults the evidence plane — checked by the **absence of
an evidence-access record**, because that misroute reads someone's records for a question that was
never about them. The second check is the sharper one and is why "some routing test exists" would
not satisfy this row.

**A decline names its source (SC-010).** Nobody who asked about their estate is told the
documentation does not cover it.

**Empty roles refuse (SC-011).** Before any read happens — the refusal writes no access record,
because no access was attempted.

**The caller cannot tell "no records" from "not yours"; the investigator can (SC-008).** Asserted
on both halves: response equality for the caller, disposition difference in the trail.

**A store failure is not a decline (FR-003).** Same raise-don't-shape discipline as 024's
provider failures, same reason: the two send a reader to different people.

**`estate_state` scores product output, in both failure directions (SC-005, FR-011b).** A
deliberately invented reference fails precision; a deliberately omitted one fails recall. Both
break-fixtures are in the component rows, because a scorer that catches only one direction passes
a platform that under-reports.

---

## What these rows refuse to assert

**They do not assert the answer is complete.** The read is bounded by the existing `limit`; the
rows assert what is answered is grounded and scoped, not that every relevant record was consulted.

**They do not assert role assignments are right.** Scope faithfully reflects the subject's roles;
whether a person *should* hold a role is the IdP's and the claim mappings' business, already
governed elsewhere.

**They do not assert the fixture estate resembles anyone's production estate.** It is arranged
material for deterministic scoring — which is also why `estate_records.toml` carries **no digest
pin**: the corpus pin detects third-party drift, and fixture material has no third party to drift
from. Recorded here so the corpus analogy is not over-applied.

**They do not assert ADR-0035's team granularity.** Roles are the bound (spec FR-004b); the team
example needs a subject attribute the platform lacks and is **owed** (FR-004d), not approximated.

**They do not assert the live model behaves tomorrow.** Same periodic-guarantee caveat every live
row carries.

---

## The row that would have caught the original problem

The 2026-08-01 live run failed `estate_state`/vault and the case ids were lost to a truncated
capture — so the platform knew *that* it failed and not *what* failed, which is exactly the state
R4 exists to forbid. FR-012 makes the identification a requirement, this contract records its
outcome, and the reauthored suite's live run then starts from a named baseline rather than from
"the old one failed somehow".

### FR-012 finding

*To be recorded by the run — case id(s), cause, and outcome either way.*
