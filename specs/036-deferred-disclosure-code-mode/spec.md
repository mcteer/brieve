# Feature Specification: Deferred disclosure and code mode

**Feature Branch**: `036-deferred-disclosure-code-mode`

**Created**: 2026-08-05

**Status**: Draft

**Input**: User description: "Deferred disclosure and code mode" — the last unbuilt entry on the roadmap with two Accepted ADRs behind it, taken with both halves in scope after the maintainer was shown that the code-mode half has no framework integration to adopt.

## Traceability *(mandatory)*

| Field | Value |
| --- | --- |
| **Requirements (R1–R17)** | **R7 (fail-closed / total interception)** — the whole feature is one question: does an efficiency change move any tool call off the governed path. **R5, R11** (interception coverage, now across two new ways a call can be issued). **R4, R10, R13** (evidence — a code-mode run's *cause* is a program, and a trail holding only its effects cannot reconstruct it). **R16** (sealed core, versioned seams — the adapter changes shape). R12 (lean — a sandbox is a new runtime dependency and must earn it) |
| **ADRs touched** | **ADR-0040** (deferred disclosure — the mechanism ships in the pinned framework and a governed agent refuses it today), **ADR-0041** (code mode ships only with verified per-call hook parity — an unconditional gate this feature must satisfy or decline), **ADR-0054** (**Proposed, and deliberately left so** — its per-delegation boundary is out of scope per FR-015; this feature realizes only the per-call half ADR-0041 already required), ADR-0006 (interception is unconditional and not qualified by execution mode), ADR-0019 (framework dependencies are absorbed at the adapter), ADR-0026 (credential-free checkpoints — sandbox snapshots are checkpoints), ADR-0047 (a passing stub is worse than a missing one — the failure mode this feature is most likely to produce), ADR-0004 (adopted content — the sandbox is adopted content and the obvious package name is the wrong project), ADR-0022/0039 (the Qualified Model Matrix — deferral depends on what a cell can do) |
| **Evidence class** | **attestation-relevant, and the audit schema itself changes.** Discovery becomes a recorded observation (FR-006), which is a sealed-core change under Principle V and obliges an amendment to ADR-0040 (FR-006b). Two new invocation paths also reach tool execution. If either produces an effect the trail does not describe, every governance claim this platform makes about a run becomes conditional on which execution mode it used — which is the property ADR-0041 exists to forbid |

## Clarifications

### Session 2026-08-05

- Q: Is an act of discovery — a model searching for a tool it was not shown — a governed, recorded event? → A: **Recorded, never refused.** Discovery is written to the trail as an observation and is not a decision point: nothing can refuse a search. The trail gains what the model went looking for, including searches that matched nothing, while the authority path stays untouched and disclosure never becomes part of what a run is permitted to do. **This obliges an amendment to ADR-0040**, whose Decision states "No registry, hook, or audit change" — recording discovery is an audit change, and the record must say so rather than the spec quietly contradicting it. See FR-006a.
- Q: The sandbox runtime is pre-1.0 and the roadmap's standing instruction on it is "track, do not build on". How does this feature adopt it? → A: **The platform owns the sandbox seam; the runtime plugs in underneath it.** Governance logic lives on the platform's side of a boundary it defines, so the runtime is replaceable and the parity assertions test the platform's own code rather than a `0.0.x` upstream's behaviour. This follows from what was measured rather than from caution: the sandbox does not enforce the table of functions a program may call — the host does — so the security boundary is already the platform's. Owning it explicitly makes that true by construction instead of by accident.
- Q: Does this feature govern one boundary or two — ADR-0054 adds a second, where a sub-agent invocation is a delegation rather than a tool call? → A: **Per-call only; ADR-0054 stays Proposed and untouched.** The delegation boundary has no substrate to govern: its watch signals are separate from the sandbox's and none are met — the orchestration package still carries an `experimental` import segment, its call contract is unsettled, and the durable-workflows extension has not landed. Governing an object that cannot yet be invoked would be a rule asserting something nothing exercises, which is ADR-0047's failure mode written into an ADR instead of a test.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — A run pays for the tools it uses, and governance does not notice the difference (Priority: P1)

An agent definition carries several capability packs. Today every registered tool's full schema enters the model's context before the task begins, whether or not any of them is used. After this feature, the definition's tools cost a catalog line until the model reaches for one; the schema loads at that moment. The run behaves identically in every governed respect — the same operation is allowed or denied for the same reason, and produces the same audit records, whether its tool was disclosed up front or discovered mid-run.

**Why this priority**: This is ADR-0040, it is Accepted, and it is the owed gate row on the board. It is also the half that is buildable today: the mechanism ships in the pinned framework, so the work is compositional rather than inventive.

**Independent Test**: Run one identical operation twice against the same definition — once with every tool disclosed eagerly, once with disclosure deferred and the tool reached through discovery. Compare the decision, the reason code, and the audit records. They must be identical except for anything that legitimately differs (timing, and the discovery step itself if discovery is recorded).

**Acceptance Scenarios**:

1. **Given** a definition whose tools are deferred, **When** the model has not yet reached for any tool, **Then** the tool schemas are absent from what the model was sent, and the definition's permissions are unchanged.
2. **Given** a deferred tool the model has discovered, **When** it calls that tool, **Then** the call passes the full hook pipeline and produces the same decision and audit records as the eagerly-disclosed call would.
3. **Given** a tool that policy denies, **When** it is reached through discovery rather than eager disclosure, **Then** it is denied for the same reason — deferral changes what the model knows about, never what is permitted.
4. **Given** a model whose profile cannot support discovery, **When** a run starts against it, **Then** the platform states which posture the run is in rather than silently disclosing everything while the operator believes deferral is active.

---

### User Story 2 — The model writes a program, and every call it makes is governed (Priority: P1)

Instead of emitting one structured tool call per turn, the model writes a short program that calls several tools — a loop over twenty resources becomes a few lines rather than twenty round trips. Each call the program makes leaves the sandbox, is decided by the same pipeline that decides a structured call, and is recorded the same way. A call the policy denies fails inside the program exactly as a denied structured call fails.

**Why this priority**: P1 alongside US1 rather than below it, because ADR-0041 makes this conditional on a gate rather than optional: code mode ships **only** with verified per-call parity. A partial answer here is not a smaller feature — it is a decision that code mode does not ship, which is an acceptable and explicitly anticipated outcome.

**Independent Test**: Execute a program that issues several tool calls, including one the policy denies. Assert that the host observed every call, that each passed the governed entry, that the denied one was refused, and that the audit records are indistinguishable from the same calls issued as structured calls.

**Acceptance Scenarios**:

1. **Given** a program that calls three tools in sequence, **When** it runs, **Then** three governed decisions and three sets of audit records exist, and the result of each call is what the governed path returned.
2. **Given** a program that calls a tool the policy denies, **When** it reaches that call, **Then** the call is refused, the refusal is recorded, and the program cannot obtain the effect by continuing.
3. **Given** a program that names something that is not a registered tool, **When** it reaches that name, **Then** the platform refuses it and records the attempt rather than executing anything.
4. **Given** a run interrupted mid-program, **When** it resumes, **Then** the resume is governed by the same rules as any other resume and no credential is present in what was serialized.

---

### User Story 3 — The record says what the program did, and what caused it (Priority: P1)

An auditor reading a run that used code mode can reconstruct not just the effects but their cause: the program the model wrote is part of the record. A reader can see which calls the program made, in what order, under whose authority, and what each was decided to be.

**Why this priority**: P1 because it is not separable from US2 in the way a reporting feature usually is. ADR-0054 states it directly — an orchestration whose effects are recorded and whose cause is not is an orchestration nobody can reconstruct. A code mode whose program is absent from the trail converts every run into a set of effects with no explanation, which is a *reduction* in evidence relative to structured calling, where the model's intent is visible turn by turn.

**Independent Test**: Run a code-mode program, then read the run's evidence through the platform's own governed read path. Establish which calls it made and recover the program text that caused them.

**Acceptance Scenarios**:

1. **Given** a completed code-mode run, **When** its evidence is read, **Then** the program the model wrote is recoverable from the record.
2. **Given** a code-mode run and a structured-call run performing the same operations, **When** both trails are read, **Then** the tool decisions are described identically and the code-mode trail additionally carries its cause.

---

### Edge Cases

- **The search meta-tool reaches governance as an ordinary tool call.** Measured: a model emitting a call named `search_tools` against a governed agent is routed to the governed entry, which finds no such registered tool and refuses. Since discovery is recorded but never refused (FR-006, FR-006a), a search must not arrive at the governed entry as a tool call at all — and the exemption must be structural rather than a match on the name, because a name match is a bypass anyone can trigger by registering a tool called `search_tools`.
- **A model that cannot defer.** Deferral depends on what the model supports. Measured: marking tools deferred against a model without discovery support disclosed every tool anyway and added no discovery affordance. A run silently in the eager posture while an operator believes it is deferred is the unstated-posture failure this platform legislates against elsewhere.
- **A name the program invents.** Measured: a program calling a name declared nowhere — including `open`, `eval`, and `__import__` — reaches the host as a request shaped exactly like a legitimate tool call. The sandbox does not enforce the table of available functions; the host does. Everything therefore depends on what the host does with a name it does not recognise.
- **A program that never calls anything.** Pure computation inside the sandbox produces no governed decisions and no effects. It must not be treated as a failure, and it must not be treated as a governed action either.
- **A program that calls the same tool many times.** Run bounds and the non-repeatable-call bracket already apply per governed call; a program issuing a hundred calls must hit the same bounds a hundred structured calls would, not evade them by being one turn.
- **A program that fails partway.** Calls already made had real effects. The run must be resolvable by observation rather than by guessing, exactly as an interrupted structured run is — the sandbox snapshot is the checkpoint, so resume continues past the calls already made rather than replaying them, and the calls made after resume are governed identically (FR-011a). This interacts directly with the nested-bracket question R11 leaves open: `run_program` is one non-repeatable bracket and each inner call is another, so resume correctness depends on how those nest.
- **Both halves at once.** A code-mode program that reaches for a tool whose schema was never disclosed. Discovery and execution interact, and neither ADR addresses the combination.

## Requirements *(mandatory)*

### Functional Requirements

**Disclosure**

- **FR-001**: The platform MUST support running a definition with its tools' schemas withheld from the model until the model reaches for them, and MUST NOT make that posture change which tools exist or which are permitted.
- **FR-002**: An identical operation MUST produce an identical governance outcome — same decision, same reason, equivalent audit records — whether the tool was disclosed eagerly or reached through discovery. This is ADR-0040's own wording and is the owed gate row.
- **FR-003**: The platform MUST NOT lose the protection that currently causes it to refuse a disclosure mechanism it cannot govern. The existing refusal exists because the governance wrapper is deliberately terminal — nothing downstream of it may produce an ungoverned execution — and a mechanism installed without complaint would appear active while doing nothing.
- **FR-004**: When a run cannot use deferred disclosure because the chosen model does not support it, the platform MUST make the posture the run is actually in observable, rather than presenting the same appearance for both.
- **FR-005**: Deferred disclosure MUST NOT change what is recorded about a tool call.
- **FR-006**: An act of discovery MUST be recorded in the trail — what was searched for and what it matched, including a search that matched nothing.
- **FR-006a**: Discovery MUST NOT be a decision point. Nothing may refuse a search, and a search MUST NOT consume authority, narrow scope, or alter what the run is permitted to do. Disclosure stays outside the authority path; only what the model *knows about* changes.
- **FR-006b**: Because ADR-0040's Decision states "No registry, hook, or audit change", this feature **owes a decision record amending it** — recording discovery is an audit change, and the amendment MUST land in the same change rather than leaving an Accepted ADR contradicted by shipped behaviour. Records are append-only, so ADR-0040's Decision section is not edited.
- **FR-006c**: A discovery record MUST be distinguishable from a tool-call record. An auditor MUST NOT be able to mistake "the model looked for a way to delete a bucket" for "the model attempted to delete a bucket", since one is intent and the other is an act.

**Code mode**

- **FR-007**: Every tool call issued by a model-written program MUST pass the same governed entry as a structured tool call, receiving the same decision under the same authority and producing equivalent records. If this cannot be independently demonstrated, code mode MUST NOT ship in the governed path (ADR-0041, unconditional).
- **FR-008**: The platform MUST refuse any name a program calls that is not a registered tool available to that run, and MUST NOT execute anything on its behalf. This includes names that resemble ordinary language features.
- **FR-009**: The demonstration required by FR-007 MUST be an executable assertion, not a review conclusion. A host-side path that reaches a tool body while bypassing the governed entry MUST fail the suite.
- **FR-010**: Execution bounds MUST apply to a program's **inner** calls at the same grain they apply to structured calls — each inner call checked and counted exactly once, by the existing governed entry, and the bounds set by the platform, never by the program. The act of submitting a program is itself one governed step, so a program making N inner calls consumes N+1 steps of the run's budget; the spec states the +1 rather than claiming a program is free. A program MUST NOT be able to exceed the run's step budget.
- **FR-010a**: A bound reached mid-program **terminates the run**; it is not delivered to the program as a recoverable failure. This is the deliberate difference from a policy denial (FR-007), which the program *does* see as an in-sandbox failure: a denied call is a fact about one action the program may route around, an exhausted bound is a fact about the whole run and there is nothing left to route to.
- **FR-011**: Anything the platform serializes to suspend a program MUST be subject to the existing credential-free-checkpoint discipline, asserted rather than assumed from the sandbox holding no credentials of its own.
- **FR-011a**: A program that resumes after an interruption MUST have its remaining calls governed exactly as its first calls were — each round-trips the governed entry, under the run's **surviving grant** (ADR-0026: resume re-observes, it does not re-authorize), on whatever allocation and identity the resume runs on (ADR-0048: a resume is a new allocation with a new attested identity). The parity property MUST hold **across** the kill, not only before it. And a program interrupted mid-call MUST be resolvable by observation — its already-executed inner calls are not re-executed on resume (the sandbox snapshot is the checkpoint, so the program continues past them rather than replaying them). This is the resume half of US2 scenario 4 and the "fails partway" edge case; without it the feature verifies parity only for runs that never stop, which is not the population that matters.
- **FR-012**: The program the model wrote MUST be recoverable from the run's evidence, through the platform's own governed read path.
- **FR-013**: The platform MUST NOT present a partially-verified code mode as available. Where verification is incomplete, code mode is absent or explicitly refused with the reason stated — never present and unverified.
- **FR-014**: The platform MUST define and own the boundary through which a model-written program reaches anything outside itself. Every decision about whether a call is permitted, and every record of it, MUST live on the platform's side of that boundary.
- **FR-014a**: The sandbox runtime MUST sit beneath that boundary as a replaceable component, and MUST NOT be depended on to enforce anything. The measured basis: the runtime does not enforce which functions a program may call — it forwards every unresolved name to the host, including names resembling ordinary language features — so treating it as an enforcement layer would rest governance on a property it does not have.
- **FR-014b**: The runtime MUST be adopted as *identified* content: the correct upstream project, pinned, provenance recorded (ADR-0004). The obvious package name resolves to an unrelated project on the public index, so naming the artifact correctly is a supply-chain requirement rather than a formality.
- **FR-014c**: The parity assertions required by FR-007 and FR-009 MUST hold against the platform's boundary, and MUST NOT be satisfiable only by the runtime behaving as it does today. A runtime upgrade MUST NOT be able to silently weaken them.

**Scope of governance**

- **FR-015**: This feature governs the **per-call boundary only**. It MUST NOT introduce, govern, or partially support sub-agent orchestration, and MUST NOT change ADR-0054's status. Anything this feature builds that a future delegation boundary would need MUST be left as an ordinary seam rather than a half-built delegation path — a partial delegation mechanism is worse than none, because it would be reachable without being governed.
- **FR-016**: Neither capability MAY change what a definition is permitted to do. Both are efficiency mechanisms and MUST remain pure with respect to authority.

### Key Entities

- **Disclosure posture** — whether a given run's tools were presented up front or withheld until reached for. A property *of a run*, observable, and not a property of what the run is permitted to do.
- **Discovery** — a model searching for a tool it was not shown, and what that search matched. Recorded as an observation, never a decision (FR-006, FR-006a). Distinct from a tool call in the trail, because looking for a capability is not attempting to use one (FR-006c).
- **Model-written program** — the code a model produces in code mode. Both a thing that executes and, per FR-012, a piece of evidence.
- **Call request** — a program's attempt to invoke something by name, as the platform receives it. Notably, a request for a registered tool and a request for something invented are the same shape; what distinguishes them is what the platform does next.
- **Suspended program state** — what the platform holds when a program is paused mid-execution. A checkpoint (FR-011).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For every operation in a representative set, the governance outcome is identical whether the tool was disclosed eagerly or reached through discovery — **100%, with zero tolerated differences**, since a single divergence is the governance gap the whole mechanism is claimed not to create.
- **SC-002**: **The structural invariant.** Before the model reaches for it, an undisclosed tool contributes its name and one-line description and nothing else — no parameter schema, no nested types. Asserted per tool rather than in aggregate, because an aggregate measure passes while one large tool still leaks its schema.
- **SC-002a**: **The benefit.** For a definition carrying many tools, the schema material sent before the model's first tool call is a stated fraction of what the same definition sends today, measured on both postures with the same definition and the same task. Expressed as a ratio against the eager run rather than an absolute budget, so it does not go stale the moment a pack is added — an absolute number either fails for the wrong reason or gets raised until it means nothing.
- **SC-003**: For a program issuing N tool calls, the platform records N governed decisions. **No call is unaccounted for, at any N tested**, including calls that were denied and calls whose names were not registered.
- **SC-004**: A deliberately introduced path that reaches a tool body while bypassing the governed entry causes the suite to **fail**. A suite that stays green with that path present has not demonstrated anything.
- **SC-005**: An auditor can reconstruct a code-mode run's cause from its evidence — recovering the program and the ordered calls it made — without access to anything outside the platform's own records.
- **SC-006**: A run in the eager posture because its model cannot defer is distinguishable, by an operator, from a run in the deferred posture. Neither presents as the other.
- **SC-007**: The platform's behaviour where verification is incomplete is refusal or absence, never silent availability — demonstrated by an assertion, not by inspection.

## Assumptions

- **Both halves are in scope by explicit decision.** The maintainer was shown three measurements — that the disclosure mechanism ships but a governed agent refuses it, that no framework code-mode integration exists in any released version, and that the sandbox is pre-1.0 — and chose both halves knowing the feature may land disclosure plus a documented, demonstrated inability to ship code mode. ADR-0041 anticipates exactly that outcome and calls it acceptable.
- **Efficiency is the benefit, and governance is the constraint.** Where they conflict, the constraint wins without weighing. Neither ADR permits a profile in which the efficiency argument outweighs interception.
- **The existing governed entry stays the only way a tool body executes.** This feature adds ways a call can be *issued*; it does not add a way for one to be *executed*.
- **The sealed core is in play, twice.** Principle V names both the adapter and the **audit schema**, and this feature changes both — the adapter's shape, and the trail's vocabulary once discovery is recorded. It needs a Principle V review; the last several features did not, and a run of features without one is not evidence that this one can skip it.
- **An Accepted ADR is contradicted unless amended in the same change.** ADR-0040 says "No registry, hook, or audit change" and this feature makes an audit change by decision (FR-006b). Shipping the behaviour without the amendment would leave the platform doing something its own record says it does not do — the defect ADR-0060 closed at the constitutional level a day earlier.
- **"No ambient capabilities" is a property of the sandbox, not of the integration.** The runtime reaches nothing on its own, and every attempt to reach something becomes a request to the platform. The platform's handling of those requests is therefore the entire boundary, and it is the platform's code, not the sandbox's.
- **Existing behaviour for definitions that do not opt in is unchanged.** A definition using neither capability must run exactly as it does today.
- **SC-002 was split into two criteria as a default, not a clarification.** The original wording ("materially less") could not fail a test. Two rows replace it because they fail for different reasons: the invariant (SC-002) catches a schema that leaked into context anyway, and the ratio (SC-002a) catches an implementation that leaks nothing yet delivers no saving. The specific fraction in SC-002a is left to the plan, which can measure the real corpus rather than guess at one here.

## Deferred

Recorded so nobody re-derives why these are absent:

- **Sub-agent orchestration and the per-delegation boundary** — the second half of ADR-0054, decided out of scope in clarification (FR-015). Its watch signals are separate from the sandbox's and none are met: the orchestration package still carries an `experimental` import segment, its call contract is unsettled, and the durable-workflows extension — the one that matters most, because workflow state entering checkpoints invokes the credential-free-checkpoint condition — has not landed. **ADR-0054 stays Proposed**, which is the honest status for a decision whose object does not yet exist here.
- **Choosing which definitions use code mode by policy.** Whether code mode is a per-definition setting, a per-pack property, or a platform default is configuration design, and it is meaningless until FR-007 is satisfied.
- **Optimizing what the model is shown during discovery.** Tool descriptions become more load-bearing under deferral — a model can only reach for a capability whose catalog line conveys what it does — but improving the descriptions is content work, not this feature.
- **Streaming or incremental execution of a program.** A program runs and returns; partial results are not surfaced mid-execution.
