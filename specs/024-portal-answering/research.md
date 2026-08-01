# Research: 024 — grounded guidance

**Phase 0.** Measured against the repository on 2026-08-01. Two findings change what this feature
is; both were invisible from the spec.

---

## F1 — Neither scorer touches a product path, which is why the suites are green

**Measured**: `src/core/evals/scoring.py`. `Scorer` is a protocol with one method,
`respond(subject, case) -> str`, and two implementations:

- `FixtureScorer` returns `case.recorded` — the authored string. It never calls anything.
- `LiveModelScorer` asks a real model **directly**.

**So both lanes bypass any answering path.** The blocking lane replays a recording; the live lane
talks to a vendor. Neither has ever exercised product code, which is exactly why
`citation_accuracy` and `must_decline` pass over a capability that does not exist.

**Decision**: add a third `Scorer` that drives the **answering path**, with a fixture provider
injected. `Scorer` is already the seam, so this is an implementation of an existing protocol
rather than a new concept.

**Rationale**: clarify chose this (Q2/C). It makes the suite score what the product produced,
deterministically, with no vendor credential — and it is the only option under which the existing
green suites start meaning something.

**Alternatives**: regenerating `recorded` from live runs (a snapshot of one model on one day,
needing a paid credential to refresh); a second row beside the authored one (leaves the suite
scoring the authored artifact — the defect, one layer along).

---

## F2 — The guidance corpus is not in this repository

**Measured**: `packs/{terraform,vault}/` contain `evals/`, `skills/`, and `pack.toml`. There is no
corpus. The `citation_accuracy` cases cite **live external URLs** —
`https://developer.hashicorp.com/terraform/language/style`,
`https://developer.hashicorp.com/vault/docs/concepts/seal` — inside authored answer strings.

**So there is nothing to resolve a citation against.** A citation today is a substring in a
recording. FR-002 requires citations resolvable to a specific section of a **pinned** corpus, and
FR-014 requires change detection by content because the corpus carries no version metadata.

**This is the largest single piece of work in the feature and the spec understated it.** The spec
says the corpus "is settled", which is true of *which* corpus — it is not in the repository.

**Decision**: obtain and pin the corpus as a vendored artifact with recorded provenance, following
the precedent already in the tree.

**Rationale**: `packs/terraform/skills/` is exactly this pattern — content from
`hashicorp/agent-skills` at a pinned commit, with a `PROVENANCE.md` and a `LICENSE` beside it, so
ADR-0004's supply chain has "a genuine subject: real provenance to check, a real upstream version
to pin". A guidance corpus is the same shape of artifact and should not invent a second mechanism
(Principle VII).

**Open for tasks**: whether the corpus lives under `packs/*/corpus/` per pack or in one shared
place. It is cited by both packs' suites, which argues for shared; pack pinning argues for
per-pack. Cheap either way and better decided against the actual documents.

---

## F3 — The fixture-provider convention already exists

**Measured**: `adapters/model_chooser.py` carries `FIXTURE_PROVIDER = "fixture"` — "the provider
segment that resolves to a recording rather than a vendor" — with `core/choice/recorded.py`
implementing it. 020 uses it so its conformance lane drives the real path without a vendor.

**Decision**: reuse it. FR-016a's injected provider is the same seam, one role along
(`ask` instead of `plan`).

**Consequence**: the answering path must take its provider as a parameter rather than constructing
one. That is the constraint clarify recorded, and it is what keeps the blocking lane honest.

---

## F4 — `ask` is a role, and nothing binds it

**Measured**: `Role = Literal["ask", "plan", "write", "judge", "summarize"]` in
`core/authority/matrix.py`. 020 authored the first matrix record, for `plan`.

**Decision**: no new role, no new matrix concept. An `ask` cell and a binding are records, not
code.

**Obligation carried from FR-009**: an unqualified cell must refuse **before** any provider call.
020 already established that refusal (`unqualified_cell`) and its conformance script warns that a
missing record makes every row refuse in a way indistinguishable from the feature working.

---

## F5 — Never-acts has to be structural, and there is a shape for it

**Measured**: the platform's existing posture is that a capability absent by construction beats one
absent by policy — 021's report compiler "holds no query and no credential", so it *cannot* widen
scope or observe.

**Decision**: the answering path holds no tool registry and no authority grant. FR-006/FR-008 are
then satisfied by what the path does not have, and granting the ability to act later requires
*adding* something visible in review.

**Rationale**: ADR-0039 decided this before the feature existed precisely because it would be
tempted. A prompt instruction is not a control; a missing dependency is.

---

## F6 — What must not change

- **The blocking lane stays vendor-free** (FR-016). `evals-live` remains outside it, for
  qualifying cells.
- **`estate_state` and `must_deny` are untouched.** The first belongs to the deferred feature; the
  second is not about answering.
- **`FixtureScorer` stays.** Other suites use it, and it raises rather than inventing silence for
  an unrecorded case — a property worth keeping.
- **The portal stays a thin client** (ADR-0034): answering is an API operation, so ADR-0033's
  parity row grows.
