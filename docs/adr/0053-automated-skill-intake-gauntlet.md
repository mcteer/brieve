# ADR-0053: An automated intake gauntlet for skill adoption; the human gate is unchanged

- **Status**: Proposed
- **Date**: 2026-07-29
- **Extends**: [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md)
- **Relates to**: [ADR-0021](0021-connectivity-tiers.md), [ADR-0030](0030-pinned-versus-consulted-artifacts.md), [ADR-0038](0038-integration-uplift-workflows.md), [ADR-0043](0043-judge-screened-precedent-reuse.md), [ADR-0052](0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md)
- **Requirements**: R4 (evidence over claims), R6 (eval-gated promotion)

## Context

[ADR-0004](0004-adopt-skills-as-governed-supply-chain.md) settled that upstream skills are
adopted rather than authored, pinned rather than tracked, and promoted only through a
provenance check, an injection-lens review, and a passing eval run. It also named two costs
plainly, and both have turned out to be the durable ones.

The first is that injection-lens review is a genuinely new review skill. Reading instruction
content adversarially — asking not "is this good advice" but "what could this make the agent
do" — is not ordinary code review, and that capability has to be built and maintained on the
review side. The second is latency: pinning means the platform is always behind the baseline
it adopts, and on a fast-moving upstream that gap is paid every release.

Neither cost is an argument against the discipline. But both are worse than they need to be,
because today the entire gauntlet begins when a person notices upstream moved and sits down
with raw upstream text. The reviewer's first act is reading a diff cold, which is the most
expensive way to spend the scarcest skill in the process. Meanwhile the analysis that *could*
have started the moment upstream published has not started at all.

The tension is that the obvious fix is also the obvious hazard. Automating intake analysis
means pointing a model at hostile-by-assumption instruction content, which is exactly the
attack surface the review exists to guard — and doing it badly would replace a slow human
gate with a fast machine one, which is strictly worse than the status quo. The question this
record answers is not whether to automate the review. It is whether the analysis that
*precedes* the review can be automated without the review becoming a formality.

The platform already has most of the pieces. [ADR-0038](0038-integration-uplift-workflows.md)
established a hardened isolation tier for reading untrusted content, on the premise that
analyzed material is adversarial regardless of who supplied it.
[ADR-0043](0043-judge-screened-precedent-reuse.md) established that a model verdict may gate
a step and fail closed on uncertainty while never substituting for a human approval.
[ADR-0021](0021-connectivity-tiers.md) requires every feature to have an answer for
restricted and air-gapped estates. What is missing is the pipeline that assembles them.

## Decision

**Skill intake runs as an automated, staged gauntlet that produces evidence for a human
reviewer. The human gate is unchanged.** The pipeline raises the review's floor and never
replaces its ceiling: it decides what a reviewer reads, never whether a skill promotes.

Stages run cheapest-first and **fail closed at each**, so a stage that cannot complete
blocks promotion rather than passing the candidate along.

1. **A poller watches the pinned upstream repositories** as a periodic scheduled job.
   Polling rather than webhooks, deliberately: no inbound surface is opened, and polling
   degrades across connectivity tiers where a webhook cannot. Restricted estates poll through
   the allowlisted proxy; air-gapped estates run the identical pipeline against bundle
   snapshots at import time ([ADR-0021](0021-connectivity-tiers.md)), so the gauntlet is one
   pipeline with one trigger difference rather than two implementations.

2. **A new upstream version dispatches an analysis agent** — a registered agent definition
   like any other, ceiling-bound, correlation-ID'd, audited, running in the
   [ADR-0038](0038-integration-uplift-workflows.md) hardened isolation tier. It
   carries **the narrowest ceiling in the fleet**: read the upstream diff, write one artifact
   type — a structured review report — and nothing else. No product tools, no egress beyond
   the pinned source.

3. **The analysis is of the diff, not the corpus.** The pinned-version hash makes the delta
   exact, so cost is proportional to upstream motion rather than to upstream size.

4. **An automated adversarial read** performs the injection-lens pass. Candidate text enters
   the analyzer's context as **delimited data, never as instruction**, and the analyzer emits
   **only a verdict schema**. This posture is structural rather than declared: the analyzer's
   ceiling contains nothing to be redirected *to*, so a successful redirection has no
   reachable effect. Any flag short-circuits to the human with findings attached.

5. **A clean static read proceeds to differential detonation.** The candidate skill is bound
   to a real qualified model and run against the golden-task corpus; the pinned current
   version is run against the same corpus; behaviour is diffed — tool-call attempts, denial
   patterns, must-deny outcomes. **This is ADR-0004's required passing eval run**, automated
   and triggered by upstream motion. It is not a new gate.

   The detonation range is the **development-grade identity stand-in** — the fake authority
   source that feature 010 retires from production — with fake authority, mock estates, zero
   egress, and full audit. The range is seeded with **canary secrets and canary repository
   content**, so exfiltration, echo, or encoding of a canary is caught mechanically rather
   than by a reader noticing.

6. **The observer and the specimen are separate workload identities in separate processes.**
   The specimen executes the candidate and is presumed infected. The observer never shares
   context with the candidate: it reads the detonation run's audit trail and spans **from
   outside**. This separation is the load-bearing one — an analyzer that read candidate output
   into its own context would be the injection surface it exists to inspect.

7. **An evidence package attaches to the version-bump pull request** — textual findings,
   differential results, canary status. **A human reviews and accepts before the skill goes
   live**, and accepted skills still land warn-mode before enforce-mode promotion, per existing
   discipline.

**Doctrine bindings, none of them new:**

The analyzer's verdict **may gate and never approves.** It blocks promotion and fails closed
on uncertainty; it does not satisfy the human approval, which is
[ADR-0043](0043-judge-screened-precedent-reuse.md) and Principle IX's judge rule applied to
intake rather than a fresh exception.

The analyzer is itself **pinned, eval-gated executed content** under Principle VIII, and
therefore needs its own eval class: a **seeded-hostile skill corpus** covering redirection,
exfiltration, encoded payloads, and injection aimed at the reviewer itself; a **must-flag
rate**; a **false-positive budget**; and a **calibration check for lenient drift**. An
analyzer nobody re-qualifies is the ungated input to every intake decision above it — the
same failure [ADR-0052](0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md)
terminates for judges.

## Consequences

The scarcest skill in the process stops being spent on cold reading. A reviewer opens a pull
request that already contains what changed, what the static read found, how behaviour
differed against a real corpus, and whether any canary moved — and spends their adversarial
attention on judgement rather than on comprehension. That is the intended effect and the
whole justification: the review's floor rises because the reviewer starts further in.

The latency cost that ADR-0004 accepted narrows without being eliminated. Analysis begins
when upstream publishes rather than when a person notices, so the gap becomes the review's
own turnaround instead of the sum of noticing, reading, and reviewing. The gap does not close,
and this record does not claim it does.

**The honest limit: detonation only catches what the corpus provokes.** A payload conditioned
on a trigger the corpus does not supply — a date, a hostname, a phrase, an estate shape —
behaves cleanly under test and remains dormant. This is not a gap to be closed by a better
corpus; it is a property of behavioural testing, and any claim that detonation makes intake
safe would be false. That residual is precisely why the human gate stays, why warn-mode
precedes enforce-mode, and why the governance floor — registry deny, authority intersection,
entitlement mirroring, egress classes, pull-request-first merge — remains the real backstop
for anything intake misses. The gauntlet reduces what reaches production unreviewed; it does
not make the runtime controls optional.

The costs are real and concentrate in three places. The analyzer is a new eval-gated artifact
with a hostile corpus that has to be *good* — a seeded-hostile suite that only contains the
attacks somebody already thought of will report a must-flag rate that means nothing, and
building it is the same order of work as building the judge seed set. The detonation range is
infrastructure with a maintenance obligation: a mock estate that drifts from the real one
produces differential results about a system nobody operates. And the two-identity separation
in stage 6 is the kind of constraint that erodes under convenience pressure, because merging
observer and specimen would simplify the implementation considerably and the resulting
vulnerability would be invisible until exploited — which argues for a conformance row rather
than a comment.

This record also foreclosed something worth naming: it does not automate the *decision*. A
future revision that let a green gauntlet promote a skill without a human accepting it would
be a different decision, requiring a new record, and the analyzer's own eval class exists in
part so that the temptation is answerable with evidence rather than with confidence.

## Notes

**Status is Proposed.** No pipeline exists, no analysis agent is registered, and no eval class
is defined. This record captures a design so it can be argued with before it is built; it
claims nothing about the present state of the repository.

Adoption lands with pack intake — see the roadmap entry alongside capability packs, where
skill adoption actually ships.

Open questions this record deliberately leaves open: whether the differential corpus is the
pack's existing golden tasks or a separate intake corpus; how the false-positive budget is
enforced rather than merely stated; and whether the analyzer's own bump takes this same
gauntlet, which is the obvious regress and probably terminates the same way ADR-0052's does.
