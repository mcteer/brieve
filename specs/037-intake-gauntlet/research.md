# Research: The intake gauntlet

**Feature**: 037 | **Date**: 2026-08-05

Measured against merged main, with the probe named so each finding can be re-checked when
something moves. The three findings that changed the plan are R2, R5 and R7.

## R1 — The gate this feature feeds, and why its order is not ours to rearrange

**Decision**: 037 produces evidence *for* `promote_skill` and changes nothing about it.

**Measured** (`src/core/evals/promotion.py`): the order is provenance → digest → lens →
suites, and the docstring gives the reason — *"running an injection lens over content whose
origin has not been established scans an arbitrary blob and reports it clean, which is worse
than not scanning."* The gauntlet's stages sit *before* this, producing the `suites_passed`
evidence and the reviewer's package; the refusal reason codes (`promotion_incomplete`,
`digest_mismatch`, `injection_suspected`) are unchanged.

**Rationale**: an automated pipeline that also redefined the gate it feeds would make two
changes at once and leave nobody able to say which one caused a later surprise.

## R2 — The pin exists on exactly one skill, and that shapes the poller

**Decision**: the poller reads `[upstream]` from pack manifests and treats an absent table
as "authored, not adopted" — never as an error.

**Measured**: `packs/terraform/pack.toml` carries `[upstream] repository = "https://github.com/hashicorp/agent-skills"`,
`commit = "8c6573abbd21e8094fab8f538eb5f97db63133fd"`. `packs/vault/pack.toml` carries **no**
`[upstream]` table, and its comment says why in the loader's own words: *"No `[upstream]`
table, and that is what `authored` means. The loader refuses an `adopted` pack without one,
because a supply chain with no pinned commit has nothing to check."*

**Consequence for the plan**: the gauntlet has **one real subject today**. The pipeline must
be correct for one adopted skill and must not assume a population — a poller that only works
when several pins exist would be untested at the size it actually runs at. It also means the
detonation corpus has one genuine skill to build golden tasks against.

## R3 — The poller shape already exists and its hardest problem is already solved

**Decision**: model the poller on `infra/bin/corpus_sync.py` and the `corpus-refresh`
workflow, including its accepted limitation.

**Measured**: `corpus_sync.py` fetches with `urllib`, digests content, writes a manifest with
`synced_at`, and its CI half opens a proposal PR. The workflow records the operational
finding this feature inherits: *"No PAT, and the consequence is accepted rather than worked
around. A PR opened with the default token triggers no workflows (a recursion guard). The
usual fix is a personal access token"* — and a PAT is the standing credential Principle IV
refuses, so the proposal explains its own missing checks instead.

**Rationale**: the same trade lands here unchanged. An intake proposal PR will not
self-trigger CI, and the honest response is the one 033 already took — say so in the
proposal rather than acquire a credential to hide it.

## R4 — No scheduled-job pattern exists in the enclave; the poller is a cron elsewhere

**Measured**: `grep periodic|cron infra/jobs/*.hcl` returns nothing — every Nomad job here
is a service or a batch dispatch. The existing periodic thing in this repository is a
**GitHub Actions schedule** (`corpus-refresh.yml`).

**Decision**: the poller runs as a scheduled workflow, matching 033, rather than introducing
a periodic Nomad job. That keeps the trigger where the proposal has to land anyway, and it
means an estate without the enclave running still gets intake detection.

## R5 — The detonation range cannot be the test fake, and the guard is why

**Decision**: a purpose-built range as its own Nomad job, with no real authority source.

**Measured**: `tests/harness/fake_identity_fabric` is test-only, and
`tests/unit/test_fake_fabric_is_fault_injection_only.py` is merge-blocking — every
conformance row resolving authority through it must declare `FAKE_FABRIC_IS_FAULT_INJECTION`
naming the failure mode injected, with the assertion message: *"Either move the row to the
production fabric, or declare what failure mode it is injecting — SC-001 permits the second
and nothing permits silence."*

**Rationale**: reusing the fake means amending that guard so the fake has a legitimate
non-test life. That is weakening a control to accommodate a convenience — the same move this
repository refused when it declined psycopg rather than loosen the licence gate. The range
gets its own posture instead: no authority source at all, no route to any real estate,
canaries seeded, full audit. Being operated, it carries a named trigger in ADR-0053
(Principle VI).

**Alternatives considered**: promoting the fake (rejected above); detonating only in dev
estates (rejected — ADR-0053's whole point is one pipeline with one trigger difference, and
this makes two).

## R6 — The analyzer is an agent definition, not a module

**Decision**: dispatch the analyzer through the existing seam as a registered definition with
its own ceiling and tier.

**Measured**: `src/core/authority/bindings.py` resolves a definition's `packs`, `binding_map`
and `tier` from a trust-fabric record, refusing a malformed tier with `malformed_record`.
`infra/jobs/agent-run.nomad.hcl` shows what a dispatched agent gets: an attested workload
identity (`aud = ["vault.io"]`, `ttl = "1h"`, `change_mode = "restart"`), `restart { attempts = 0 }`,
and a repo mount rather than a baked image.

**Rationale**: making the analyzer a definition means its ceiling is checked by the machinery
that already checks ceilings, and its calls are intercepted by the machinery that already
intercepts calls. A module would need all of that rebuilt, and FR-009's "nothing reachable to
be redirected to" would become an assertion about code rather than about a ceiling.

## R7 — The specimen/observer separation is two allocations, and the substrate supports it

**Decision**: specimen and observer are separate Nomad allocations with separate workload
identities; the observer reads the specimen's audit records and spans, never its output.

**Measured**: workload identity is per-task in the jobspec (`identity { name = "vault" ... }`),
so two tasks are two attested identities without inventing a mechanism. The audit trail is
already queryable by correlation ID through the governed read path, which is exactly the
"from outside" channel FR-013 requires.

**Rationale**: FR-013 is the requirement most likely to be quietly weakened, because reading
the specimen's *output* is easier than reading its *records* and produces a nicer report. The
plan therefore makes the observer's input a governed evidence read — a channel that
structurally cannot carry candidate-authored prose, rather than a discipline about what not
to look at.

## R8 — The analyzer's qualification inherits a mechanism and not a number

**Decision**: `evals/intake-seed/` on ADR-0052's mechanism, with a floor calibrated to
intake's attack classes.

**Measured**: `evals/seed/seed.toml` plus `load_seed_set`/`_assert_floor` in
`core/evals/judge.py` implement ADR-0052: human-labelled cases in the repository, reviewed
like code, with a floor of at least 20 cases spanning all four suites including at least
three the judge must REJECT — and a set below the floor **fails** rather than warns.

**Rationale**: the mechanism is exactly right and the number is exactly wrong. ADR-0052's
floor is shaped by the four answering suites; intake has no suites, it has attack classes
(redirection, exfiltration, encoded payloads, reviewer-targeted content — FR-019).
Inheriting "all four suites" would be a category error that still passed, which is the worst
kind. The intake floor is stated in the contract in those terms instead.

## R9 — `OWED` gains a row only if the suite lands late, so it should not

**Measured**: `SUITES` holds five; `OWED` is empty and has been since 021, kept deliberately
because *"the next row to be deferred needs somewhere to be deferred to."*

**Decision**: `intake_analysis` joins `SUITES` **in the same change as the analyzer**, so
`OWED` stays empty. A pipeline shipped ahead of the gate that qualifies its analyzer is
precisely the "ungated input to every intake decision above it" ADR-0053 warns about — and
ADR-0047 would require it be recorded as owed, which is a worse outcome than sequencing it
correctly.

## R10 — What the evidence package must say it does *not* establish

**Decision**: the package carries an explicit limits statement, and FR-027 makes it a
requirement rather than a courtesy.

**Rationale**: ADR-0053 states the honest limit — detonation catches only what the corpus
provokes, so the runtime governance floor remains the backstop. A reviewer handed a clean
package will read "clean" as "safe" unless the artifact says otherwise, and the failure this
feature is most likely to cause is a review that has been reassured rather than informed.
