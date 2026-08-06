# Data Model: Code mode becomes reachable

**Feature**: 039 | **Date**: 2026-08-05

Almost nothing here is new. 036 built the entities; this records what changes about them when
they become reachable, and the two places where reachability adds a fact the platform did not
have to represent before.

---

## The three layers, and why each alone is insufficient

Stated first because every entity below sits in one of them, and because the feature's own
failure mode is closing one and believing it closed the gap.

| Layer | Today | After | Alone, it gives you |
| --- | --- | --- | --- |
| **Registration** | the tool name resolves nowhere | registered, ceiling-gated | an honest `SandboxUnavailableError` and no code mode |
| **Runtime** | in CI, absent from the run allocation | installed where dispatched work runs | a runtime nothing can invoke |
| **Answer** | the model answers with a bare tool name | the model answers with a name **and arguments** | a program the model cannot express |

**FR-003 names two environments in its own text for this reason.** A plan that registers the tool
and stops has produced a capability reachable in principle and unreachable in fact — which is
this feature's subject, one layer down.

---

## Program (unchanged, newly reachable)

Model-authored code submitted as the body of one governed call.

| Field | Rule |
| --- | --- |
| `program` | the text, recorded **verbatim** in `PROGRAM_SUBMITTED` |
| `program_sha256` | its digest, so the trail can be joined to the artefact |

**Verbatim, and this is 036's argued exception rather than an oversight.** `PROGRAM_SUBMITTED`'s
docstring places it on `TURN_RECORDED`'s precedent: *a person's or model's own words, recorded as
said.* A trail holding a program's **effects** without the program is one nobody can reconstruct.
That reasoning does not transfer to 038's authored artefacts — those are derivatives of somebody
else's private repository — and the distinction is why the two members carry opposite rules.

**Written only when the submission is ALLOWED.** A denied submission leaves the ordinary
`PRE_DECISION` denial and nothing here: a program that never ran caused nothing, and recording it
would put un-executed model output into an append-only trail.

**What reachability changes**: the trail begins carrying programs that ran **in production**.
Until now every `PROGRAM_SUBMITTED` in existence was written by a test.

---

## Program submission (unchanged shape, new caller)

One governed call, decided by the same pipeline that decides every other.

**The registry is the opt-in switch and the ceiling is the decision.** Registration makes the
name resolvable; `authority.py` decides whether *this run* may reach it. A definition whose
ceiling omits the tool has no code mode even though the registry knows the name — which is
036's own stated design and needs no change, only a caller.

**Refusal shapes, which must stay three rather than becoming one:**

| Situation | Refusal | Who decides |
| --- | --- | --- |
| ceiling omits the tool | `authority_insufficient` | the authority hook, like any tool |
| runtime absent | `SandboxUnavailableError` → a stated reason | the handler, before anything runs |
| program ran and failed | the program's own failure | the program |

FR-008 exists because these are three situations calling for three different responses, and an
implementation that collapsed them would tell an operator to fix the wrong thing.

---

## Inner call (unchanged)

A request the program makes. **Every one goes to `invoke_tool`, including names the model
invented** — the seam keeps no blocklist, because the registry is the decision-maker and a second
one would eventually disagree with it.

Three failures are deliberately **not alike**, and the seam's docstring says getting this
backwards *"is the most plausible way this feature ships a hole"*:

- a **policy deny** becomes an in-sandbox failure the program can see and route around — a fact
  about one action;
- an **exhausted bound** propagates and terminates the run — a fact about the whole run, and
  converting it to a program-visible failure would let a program outlive its own budget by
  catching it;
- a **superseded lease** propagates for the same reason: a zombie must stop.

**What reachability changes**: nothing about the rule, everything about whether it has been
tested. See *Budget* below.

---

## Model answer (widened — this is R7's entity)

**The thing the platform did not have to represent before.** Today the model's answer is a `str`:
one tool name, or `NONE`. That is wide enough for a *name* and too narrow for a *program*.

| Today | After |
| --- | --- |
| `output_type=str` | `output_type=` a structured choice |
| the model returns a **name** | the model returns a **name and its arguments** |
| the entrypoint invokes with `_PROBE_ARGUMENTS` | the entrypoint invokes with the model's arguments |

**The shape of a governed step is unchanged, and that is the whole point of choosing this over a
toolset.** The model still only *answers*; the platform still *invokes*; the bracket still wraps
it. Four properties 031 built survive because nothing about the step moved:

| Property | Why it survives |
| --- | --- |
| bounded retry on a bad answer | `resolve_step_tool` still validates before invoking |
| `already_chosen` re-observation honesty | the step still resolves a choice before executing |
| `TOOL_CHOSEN` per step | the entrypoint still records what was chosen |
| `choose()` as the step's contract | still returns an answer rather than a side effect |

**The rejected design and its real cost.** Giving the agent a toolset moves execution inside
`agent.run_sync` and bypasses every row of that table. It also makes `GovernedToolset` the
executor — which is what that mapping is *for*, and is a change to what a governed step **is**
rather than a change to what a model may say. `GovernedToolset` therefore **still has no
production caller**, and that is recorded as an open gap rather than closed as a side effect
(R7).

**What widens the blast radius, and what bounds it.** Every model-driven run's model is now asked
for a structured object rather than a bare word, so a model that could produce a valid name can
produce a malformed object. **`resolve_step_tool`'s bounded retry is what absorbs that** — and
it must cover a malformed *object*, not only an unpermitted *name*, which is a different failure
the existing retry was not written for.

---

## Call ordinal (new — this is R8's entity)

**A counter the platform did not need until a program could loop.**

| Field | Rule |
| --- | --- |
| `call_ordinal` | on the run, default `0`. The seam **sets it on entry and clears it on exit**, so outside a program it is always `0` |

**Why it exists.** The idempotency key is `run_id:step_index:tool_name`, and the seam **never
advances `step_index`** — so a program calling the same non-repeatable tool twice produces the
same key twice. Intents are `PRIMARY KEY (run_id, idempotency_key)` inserted `ON CONFLICT DO
NOTHING`, so the second insert is a **silent no-op** while `bracket_call` executes the effect
regardless. One intent, two effects, and resume re-observes once.

**The key folds it in only when non-zero:**

```
ordinal == 0  ->  f"{run_id}:{step_index}:{tool_name}"        # byte-identical to today
ordinal  > 0  ->  f"{run_id}:{step_index}:{tool_name}:{ordinal}"
```

**Byte-identical is not a nicety.** Changing every key would invalidate 014's durability rows and
break resume for any run in flight. The suffix appears only in a situation that could not
previously arise.

**Scoped to the submission, not to the run.** The first draft said only "increment per inner
call" and never said where it stops — and nothing resets a run-level counter between steps
(`run.step_index` is reset by the entrypoint's loop; an ordinal would not be). A run whose step 0
ran a three-call program would carry `3` into step 1, and the next **direct** call would key
`run:1:tool:3`. The byte-identical guarantee would hold until a program ran and then quietly stop
— failing only in the case this feature creates.

**And it is what makes resume coherent**: a re-run program re-issues ordinals 1..N, matching the
intents recorded the first time. A run-scoped counter could not.

**Rejected**: advancing `run.step_index` from inside the seam. It is the *run's* counter — the
entrypoint's loop sets it and the checkpoint reads it — so mutating it from inside a tool would
corrupt the run's accounting to repair the key's.

---

## Budget (unchanged rule, first real measurement)

| Consumed by | Cost |
| --- | --- |
| the submission | 1 step |
| each inner call | 1 step |
| **a program making N calls** | **N + 1** |

**Not a convention — a consequence.** `invoke_tool` calls `bounds.check()` before executing and
`record_progress` after an allowed call, and every one of those calls goes through it. The
arithmetic follows from the seam having exactly one exit.

**States on exhaustion**, and the row asserts the distinction rather than the sum:

| Outcome | The run | Distinguishable because |
| --- | --- | --- |
| program completed | continues | it returned a value |
| a call was denied | continues | the program saw the failure and could route around it |
| **budget exhausted** | **ends** | the bound propagated rather than being handed to the program |

**SC-005 says "demonstrated by measuring it rather than asserting the arithmetic"** for a reason:
an assertion that N calls cost N+1 steps passes against an implementation where the bound never
fires. The row must run a program *out of room*.

---

## Demonstration definition (new, and deliberately not a policy)

One definition in the dev estate whose ceiling names the program tool, existing so SC-001 —
*"in the environment where dispatched work actually happens"* — can be satisfied.

**A fixture, not a decision about who gets code mode.** 036 deferred that as configuration
design and FR-012 keeps it deferred. Registration forces that a ceiling **can** name the tool; it
does not force **which ceilings do**, and a demonstration definition answers the first without
being an answer to the second.

**The line is thin and worth guarding**: the difference between "one definition exists so we can
prove the capability works" and "code mode is now part of the platform's offering" is a sentence
in a variables file. No shipped definition gains it.
