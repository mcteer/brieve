<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 024 — grounded guidance

---

## The directory name predates the split, and is not a claim

**`024-portal-answering` builds answering through the API and MCP. It touches no portal file.**

The name was chosen when the feature was one feature. Analysis pass 3 found SC-001 reading
*"through the portal"* while no task did anything of the kind, and the portal's own answering
surface became the second of two deferrals — recorded in `ROADMAP.md` beside estate-state.

Renaming a directory mid-feature would break every reference in the planning artifacts for a
cosmetic gain. Leaving it unremarked would be worse: a planning document that misdescribes what
exists has cost this repository twice in two days. So it is written down here instead.

**The boundary is asserted, not asserted-about.** `git diff main -- src/surfaces/portal/` was
empty at implementation. That check expires the moment this merges, so the durable form lives in
`tests/conformance/portal/test_containment.py`: no portal module imports `core.answering`. The
portal consumes the catalogue; it does not implement it (ADR-0034).

---

## Who runs these rows

| Group | Where | Needs |
| --- | --- | --- |
| Answering, citations, declining, never-acts | `tests/component/`, `tests/conformance/answering/` | Nothing — a fixture provider and the vendored corpus |
| The two suites scoring product output | `packs/*/evals/` via `make evals` | Nothing |
| Both surfaces answering identically | `tests/conformance/{api,mcp}` | The enclave |
| **Qualifying an `ask` cell against a real model** | `make evals-live` | A paid credential, **Dan McTeer** |

**The blocking lane must stay vendor-free.** A gate that needs a credential is a gate that stops
running, and this feature's whole subject is gates that stopped meaning anything.

| | What it is | Who | Status |
| --- | --- | --- | --- |
| Qualifying the `ask` matrix cell | `make evals-live` against a real model | **Dan McTeer** | **Owed** |
| **Principle V review** | One additive `AuditEventType` member for the ask record (T006a) | **Dan McTeer** | **Owed** — the plan originally asserted no review was needed; analysis pass 2 found the data model already required a member |

---

## What these rows assert

**An answer carries resolvable citations.** Every claim has at least one, and every citation
resolves to a section of the pinned corpus. **An unresolvable citation fails the row** — it reads
as evidence and is the worst available failure.

**Declining is preferred to answering.** A question the corpus does not support is declined, and
the decline names what was missing.

**A provider failure is not an answer.** It fails, distinguishably, and never arrives shaped like a
decline (FR-011).

**There is no path that answers without the model** (FR-011a).

**Asking reaches no effecting tool** — including when the question is phrased as an instruction.
Asserted by exercising the path, not argued from structure.

**An unqualified cell refuses before any provider call.**

**The trail records who asked and what was consulted, and never the content.**

**`citation_accuracy` and `must_decline` score what the product path produced.** This is the row
that closes the finding this feature was written around.

### Every prompt-scoring suite, and where it stands (FR-015a)

**Written out in full, because the failure being fixed is a suite nobody looked at.**

| Suite | After this feature | Why |
| --- | --- | --- |
| `citation_accuracy` | **Scores product output** | This feature's |
| `must_decline` | **Scores product output** | This feature's |
| `must_deny` | **Decided by T025a** — product output, or an entry here naming what would close it | Same shape as the two above: a prompt with an authored `recorded` response. It is about a governed run refusing rather than about answering, so it may not be reachable from this path — but *"not about answering"* is not by itself a reason to leave it, and an earlier draft used it as one. |
| `estate_state` | **Stays authored** | Belongs to the deferred estate-state feature and is that feature's obligation. Recorded so it reads as assigned rather than overlooked. |
| `report_fidelity` | Already scores compiled reports | 021's, and not prompt-scored. |

**No suite is left unaccounted for.** That is the whole point of this table: the defect this feature
exists to close was four suites nobody had asked what they scored.

---

## What these rows refuse to assert

**They do not assert the answer is good.** Whether a cited, corpus-grounded answer is *useful* is a
judgement these rows do not make. Principle VIII's gates bound quality; a green row here means the
answer was traceable, not that it was right.

**They do not assert the corpus is correct.** It is somebody else's document set, pinned. A wrong
statement in the corpus, correctly cited, passes every row here — as it should.

**They do not assert anything about estate-state answering.** That is a separate feature, and rows
here must not be read as covering it — including its `estate_state` suite, which continues to score
authored recordings until that feature closes it.

**They do not assert the model will behave this way tomorrow.** The blocking lane scores a fixture.
The live lane qualifies a cell at a point in time, which makes the guarantee **periodic** rather
than continuous — recorded here rather than papered over.

---

## The row that would have caught the original problem

**The one that drives the product path.** Today `citation_accuracy` and `must_decline` are green
because `FixtureScorer` replays an authored string and `LiveModelScorer` asks a vendor directly —
**neither has ever touched product code**. A scorer that drives the answering path fails
immediately against a platform that cannot answer, which is the correct behaviour and is why it
is the row that matters most in this feature.
