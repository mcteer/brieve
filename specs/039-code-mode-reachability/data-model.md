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
| **Channel** | the model answers with a bare tool name | the model issues a tool call with arguments | a program the model cannot express |

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

## Model channel (new — this is R3's entity)

**The thing the platform did not have to represent before.** Today the model's output is a
`str`: one tool name, or `NONE`. That is a channel wide enough for a *name* and too narrow for a
*program*.

| Today | After |
| --- | --- |
| `output_type=str`, no toolsets | a toolset built from the run's **effective scope** |
| system prompt: *"EXACTLY ONE tool name … no punctuation"* | the model issues a tool call with arguments |
| entrypoint invokes the name with `{"path": ..., "cas": 0}` | the framework's tool-call shape arrives at `GovernedToolset` |

**Built from the effective scope, and that is the blast-radius bound.** Giving the agent a
toolset changes how *every* model-driven run behaves, not only code-mode ones — so the toolset is
populated from `effective.tool_names`, the same set the authority hook decides against. A run
whose ceiling omits the program tool sees no new capability, because there is nothing extra in
its toolset to see.

**Why this is not a second calling convention.** `GovernedToolset` already routes every wrapped
call through `invoke_tool` and deliberately never calls `super().call_tool` — *"the framework's
own execution path is never taken — that is the whole point."* This feature is its **first
production caller**. The alternative, extending the string protocol to carry a program beside a
name, would have the platform parse model-authored code with a convention it invented, when the
framework already has one.

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
