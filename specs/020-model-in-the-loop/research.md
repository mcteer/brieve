<!-- SPDX-License-Identifier: Apache-2.0 -->
# Research: 020 — a model chooses, and the choice is governed

Phase 0. Measured against the tree on 2026-08-01, not inferred.

---

## F1. The new audit event is a real sealed-core change, and smaller than it looks

FR-009a says the plan must not treat this as routine. Measured:

- `AuditEventType` is a `StrEnum` in `src/core/audit/schema.py` with thirteen members.
- **There is no schema version field.** Nothing pins the vocabulary, so adding a member
  invalidates no existing entry and rewrites no hash — `entry_hash` covers an entry's own
  `event_type` value, not the set of possible values.
- Five test modules reference `AuditEventType`; none asserts the enum's exact membership.

**Decision**: add one member. **It is still a Principle V change** — the audit schema is named
sealed core explicitly — and it requires the approved spec and security-maintainer review that
principle demands. The spec is approved; the review is Dan's, who holds every review role here.

**What makes it small is not that the schema is unimportant.** It is that the change is purely
additive to an unversioned enum with no membership assertion, so nothing downstream can observe
a difference except by seeing the new event. Recorded rather than assumed, because "additive"
is exactly the word that precedes most sealed-core regressions.

---

## F2. A choice is not a `pre_decision`, and the distinction is load-bearing

`PRE_DECISION` looks like the natural home and is not. Read at `core/hooks/engine.py:202`, it
records a **hook's** decision about a tool: `hook_name`, `capability_kind`, `outcome`,
`reason_code`.

**Decision**: a new `TOOL_CHOSEN` member, beside `PRE_DECISION` rather than inside it.

**Rationale**: they answer different questions. `PRE_DECISION` says *what governance decided
about this tool*; the new event says *who named the tool and why it was on the table*. Folding
the second into the first would make a reader unable to tell a model's choice from a scheduled
step — which is exactly what SC-002 must be able to prove, and exactly what nobody can prove
today.

**Alternatives**: a field on the existing tool bracket (rejected in clarification — a refused
choice never opens a bracket, so the most important record would have nowhere to live); reusing
`PRE_DECISION` with a marker field (rejected — a field that changes what an event *means* is a
second event wearing the first's name).

---

## F3. Re-choice after refusal must not re-enter the step's bracket

FR-004a offers a refused choice back to the model; FR-004b bounds it. The subtlety is where the
bound lives relative to the existing loop.

`invoke_tool` already brackets every non-repeatable tool in `core/hooks/engine`, keyed
`{run_id}:{step_index}:{tool}`. **A second choice at the same step produces a different key**,
because the tool name differs — so re-choice does not collide with the bracket, and a refused
choice never opened one.

**Decision**: the bound is a per-step counter, and exhausting it ends the run terminally.
Nothing about the bracket changes.

**The failure this avoids**: a bound implemented as a retry *around* the bracket would make
`{run_id}:{step_index}:{tool}` ambiguous on resume — two attempts, one key, and
re-observe-never-re-execute would have to guess which. That is the durability guarantee
breaking quietly, which is why this is a research finding rather than an implementation detail.

---

## F4. `_tool_for_step` must be removed, not defaulted past

FR-002 forbids the arithmetic selection remaining reachable. The temptation is to keep it as a
fallback when the provider is unavailable.

**Decision**: delete it from the production path. `entrypoint.py` gains no fallback.

**Rationale**: FR-007 already says a provider failure is terminal. A surviving fallback would
be taken exactly when the provider is down — meaning the platform would silently revert to a
scripted sequence at the moment nobody is watching, while every row about governance continued
to pass. **That is this feature's own defect, preserved as a feature.**

**What keeps the durability rows working**: they need several real brackets to be killed
*between*, which a model-driven run produces as readily as a round-robin one. The double (F5)
makes it deterministic where determinism is what a row needs.

---

## F5. The double is a model, not a mock of the loop

**Decision**: the lane's stand-in implements the same interface a real provider does, returning
a scripted sequence of choices. It is injected where the binding resolves a model, not where
the loop asks for one.

**Rationale**: a double injected at the loop would let the loop be tested without the code path
that consults a model — which is precisely the shape 020 exists to end. Injected at the
binding, every line between "a run needs a choice" and "a choice came back" is the production
path.

**FR-011a's fidelity row** compares the double and a real provider against one fixture: same
tools, same task, both must produce a well-formed choice from the permitted set. It asserts
*shape*, not agreement on which tool — two models may reasonably differ, and a row demanding
they match would be asserting a model's judgement rather than the platform's contract.

---

## F6. What a real provider costs, and where it may run

`adapters/anthropic_scorer.py` is the only live provider call in the tree; it runs behind a
marked lane with a named runner. **Decision**: FR-012's demonstration follows that posture —
by hand, recorded, never in the merge lane. The credential lives in `.env` and is never
written to an allocation's environment where scheduler access would expose it.

---

## F7. The seam is `Chooser`, not `pydantic_ai.models.Model` (T003)

T003 asked which `pydantic-ai` model interface a provider and a double must both satisfy.
Measured against `pydantic-ai-slim==2.18.0`: `pydantic_ai.models.Model` is the abstract
provider interface, with seventeen public members — `request`, `request_stream`,
`prepare_messages`, `customize_request_parameters`, `count_tokens`, `profile`, `system`,
`model_name`, and so on.

**Decision: neither the provider-backed chooser nor the double satisfies `Model`. The seam is
`core.choice.Chooser`** — one method, taking the task, the permitted tools, and the refusals
so far at this step, returning a tool name or the empty string.

**Rationale, and it is F5 restated with a measurement behind it.** A double satisfying `Model`
would have to construct `ModelResponse` objects and imitate the framework's message protocol —
so the thing under test would be our fake's fidelity to `pydantic-ai`'s internals, which is not
a governance property and would drift with every framework bump. Worse, it would place the
double *inside the adapter*, one layer below the binding, which is precisely where F5 says it
must not go: everything between "the run needs a choice" and "a choice came back" would still
be exercised, but the binding that selects a model would not be.

`Chooser` puts the substitution exactly at the binding. `build_chooser(model_identifier)`
dispatches on the provider segment of `provider/model@version`, so the lane and production run
the *same* resolution — read the definition's binding map, validate the cell against the
matrix, resolve an identifier, build a chooser for it — and differ only in which provider sits
behind the identifier. A `fixture/…` cell must still be qualified in the matrix and bound by a
definition, so the double cannot be reached by an operator who merely forgot something.

## F8. The provider-backed chooser is an ADAPTER, not core — T007's path is reconciled

T007 says "implement the provider-backed chooser in `src/core/choice/chooser.py`, calling the
model through `build_governed_agent`". **Measured against the tree, that path violates
Principle I**: "The core never imports an agent framework; adapters import the core."
`build_governed_agent` lives in `src/adapters/pydantic_ai/agent.py` and imports `pydantic_ai`
at module scope, so a call from `src/core/` pulls the framework into core's import graph.

`tests/unit/test_core_import.py` guards this in two ways, and the second is the one that
matters here: `test_adapter_is_the_only_framework_importer` scans for the literal
`import pydantic_ai` outside `src/adapters/`, which an indirect import would slip — while still
being exactly the layering inversion the guard exists to prevent. A deferred import does not
help; `adapters/anthropic_scorer.py`'s own docstring records that lesson from 002, where
`core/evals/scoring.py` imported `anthropic` inside a function body and the guard caught it.

**Decision, and it follows a pattern already in the tree rather than inventing one.**

| Lives in | What it holds |
| --- | --- |
| `src/core/choice/chooser.py` | The `Chooser` protocol, the `Choice` record, `resolve_bound_model`, and the `TOOL_CHOSEN` emit. No framework import. |
| `src/core/choice/bounded.py` | The per-step re-choice budget and the refusal loop. No framework import. |
| `src/core/choice/recorded.py` | The fixture chooser — replays a recording, calls no provider. |
| `src/adapters/model_chooser.py` | `ModelChooser`, which calls `build_governed_agent`, and `build_chooser`, which maps a model identifier to one of the above. |

**`src/adapters/`, not `src/adapters/pydantic_ai/`, and the tree decided that too.** The first
draft put it in the framework package and `tests/unit/test_adapter_mappings.py` refused it:
`test_adapter_modules_are_exactly_the_four_mappings` pins that directory to Principle I's four
concepts plus the two modules binding them, and says in as many words that *a fifth behavioural
module is a scope breach, not a refactor*. A chooser is not one of the four — it is a provider
call, and the tree already has a place for those. `adapters/anthropic_scorer.py` sits at the
top level of `adapters/` for exactly this reason and has since 013.

So the division is finer than "core versus adapter": **framework mappings live in
`adapters/pydantic_ai/`; provider calls live in `adapters/`.** Both were found by a guard
rather than by reading, which is the argument for the guards.

This is the **`Scorer` shape, exactly**: the protocol lives in `core.evals.scoring`, the
provider implementation in `adapters/anthropic_scorer.py`, and the suites cannot tell the two
apart. That module's docstring argues the case in its own words — *"In `adapters`, not
`core/evals`, because 002's layering guard forbids a provider import anywhere else and is right
to."* The same sentence applies here with `choice` substituted for `evals`.

**What T007's substance survives intact**: `build_governed_agent` is still the call, it is still
unchanged, and this feature is still its first production caller. Only the file the call is
written in moves — from a package the constitution forbids it in, to the package that exists
for it. Recorded here rather than improvised, per the named-contracts rule, and `tasks.md` T007
is amended to the reconciled path in the same change.

---

## Unknowns remaining after Phase 0

**One, carried deliberately.** Whether a model's choice needs its own hook capability kind, or
whether the existing pre-execution pipeline is the right interception point unchanged. The spec
says no new path to a capability may be introduced (FR-003), which points at unchanged; the
answer is a first-task verification against the running loop rather than a research question.
