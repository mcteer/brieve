<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 030 — the estate eval scores the real path

---

## Who runs these rows

| Group | Where | Needs | Status |
| --- | --- | --- | --- |
| Parse: an estate case without a role, or with an unknown one, refuses to load | `tests/component/test_estate_eval_scores_visibility.py` | Nothing | Planned |
| Visibility: an operator case expecting an authority reference refuses at scorer construction | same file | Nothing | Planned |
| Narrowing: an operator case's provider never receives a record outside operator visibility | same file (recording provider) | Nothing | Planned |
| The tagged suites still pass the blocking gate | `tests/component/test_eval_gates.py` | Nothing | Planned |
| **The live re-run of the corrected suite (US3)** | `make evals-live` | Vendor credential, ~25 min, **named runner: Dan McTeer** | **Owed** |
| **Matrix outcome recorded** — confirm / re-earn / withdraw, in the matrix variables | `infra/environments/dev/variables.tf` | The re-run's verdict | **Owed** |
| **ADR-0059** — what a cell's estate evidence asserts | `docs/adr/0059-*.md` | Review: **Dan McTeer** | Planned — merges with the feature |

No sealed core; no Principle V review (fourth feature running).

---

## What these rows assert

**A case says who could ask it, or it does not load.** The role is required, from the platform's
own vocabulary, and never defaulted — the implicit assumption this feature removes must not
reappear as a default one field over.

**A case cannot expect what its role cannot see.** The visibility check refuses at construction,
naming the case, the reference and the invisible type. This is the row that would have caught the
original defect: three vault cases expecting authority records under any operator-shaped scoring.

**The provider sees only what the role would.** Asserted at the provider's input with a recording
double, because that is where the narrowing is observable — and it is the row that fails when
somebody deletes the filter (research F4's direction 1).

**The naive mutation check is recorded as vacuous.** Re-running correctly tagged cases without
narrowing passes — each case's expected records are visible to its role, so the verdict cannot
see the filter. Written here so nobody "strengthens" the suite with a check that checks nothing.

**What the suite still does not exercise is written where the suite is read**: the governed read
and its access record, temporal windows, the per-type bound. A five-record fixture could not
exercise a bound at any scorer depth.

---

## What these rows refuse to assert

**They do not assert answer quality** — that stays the lane's precision/recall over surviving
references, unchanged.

**They do not assert the full production path.** Scope narrowing is the piece this feature's
finding is about; the rest is stated as unscored rather than silently implied as covered.

**They do not decide role visibility** (FR-011). The operator/authority-records question stays
owed exactly as 029 recorded it.

**They do not grandfather the live cells.** US3's re-run decides; until it runs, the cells stand
on their 2026-08-02 evidence *with this feature's finding attached to it in the ADR*.
