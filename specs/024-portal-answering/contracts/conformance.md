<!-- SPDX-License-Identifier: Apache-2.0 -->
# Conformance contract: 024 — grounded guidance

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

---

## What these rows refuse to assert

**They do not assert the answer is good.** Whether a cited, corpus-grounded answer is *useful* is a
judgement these rows do not make. Principle VIII's gates bound quality; a green row here means the
answer was traceable, not that it was right.

**They do not assert the corpus is correct.** It is somebody else's document set, pinned. A wrong
statement in the corpus, correctly cited, passes every row here — as it should.

**They do not assert anything about estate-state answering.** That is a separate feature, and rows
here must not be read as covering it.

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
