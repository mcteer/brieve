# ADR-0064: Version control is a platform capability, not a pack tool target

- **Status**: Proposed
- **Date**: 2026-08-05
- **Amends**: the "pack tool target" clause of [ADR-0038](0038-integration-uplift-workflows.md)
- **Relates to**: [ADR-0037](0037-tool-transport-policy.md), [ADR-0004](0004-adopt-skills-as-governed-supply-chain.md)
- **Requirements**: R5, R6

## Context

[ADR-0038](0038-integration-uplift-workflows.md) says, in one line: *"Version control becomes a
first-class pack tool target, with transport chosen by the standing test
([ADR-0037](0037-tool-transport-policy.md))."* Sound in 2026-07, when the family was a
decision. Building it (038) runs the line into the eval gate.

**A pack is gated by suites that measure expertise.** The five in force —
`must_deny`, `must_decline`, `citation_accuracy`, `estate_state`, `report_fidelity` — all score
*a model answering with a pack's knowledge*. `estate_state` refuses a case without an
`asker_role` and an expected reference set; `citation_accuracy` scores whether claims carry
citations that resolve. Both existing packs carry skills, guidance and a product estate.

**A version-control pack would carry one tool that opens a pull request.** No skills, no
guidance, no estate, no model use. There is nothing for those suites to measure.

Two ways out, both bad. Ship the pack **declaring no suites** — measured, the loader's floor
iterates *declared* suites, so it would escape the gate entirely and become this platform's
first pack outside Principle VIII, first by accident. Or **write twenty-five cases** to clear a
floor for a capability with no expertise, which is the *"gate that passes by vocabulary"* 027
refused.

## Decision

**Version control is a platform capability. `open_proposal` is registered as a platform tool
beside `author_file` and `read_subject`, and no version-control pack exists.**

ADR-0037's standing test still applies and is unchanged: transport is decided at registry review
— MCP where a server exists, is mature and is supported; native otherwise. **That test is about
transport, and it is orthogonal to where a tool lives.**

## Consequences

**This is the argument 038 already made for authoring, carried the rest of the way.** Producing
a file is the same act for every product, which is why `author_file` is platform-level rather
than duplicated per pack. **Publishing a proposal is equally product-blind**: a pull request
against a Terraform module and one against application code are the same act, with the same
containment rules and the same proposal shape. A per-pack copy would be N implementations of one
rule, which is the fragmentation Principle VII forecloses.

**What is lost, and it is a real cost.** The pack loader refuses `observer_required` when a
manifest declares a non-repeatable tool with no observer. A **platform** registration is not
covered by that check, so 038 asserts the property in its own conformance row instead. One row,
against a pack that could not have been gated.

**And a gate genuinely goes away.** ADR-0038's shape had three independent controls on who may
author for what: the definition's ceiling, the **pack's declared workflow**, and the tier. With
publishing platform-level, the pack's workflow no longer gates it — so *"only products whose pack
declares an authoring workflow"* now rests solely on the request validation in
`core/authoring/request.py`. 038 asserts that single check by its own row rather than leaving it
as a property of a module, because a control that used to be one of three and is now one of one
deserves to be visible.

**What is unchanged.** Every other clause of [ADR-0038](0038-integration-uplift-workflows.md) stands as
written: repository analysis in the hardened isolation tier with injection-lens hooks; expertise
skills-first with retrieval on gap; secret references only; and writes landing exclusively as
pull requests scoped to the requester's own repositories with the human as merge authority. This
record amends where one tool lives, and nothing about what the family is permitted to do.
