<!--
Thanks for contributing. Fill this out honestly — sections marked required are checked
in review. "None" and "N/A" are acceptable answers; blank is not.
Security vulnerability? Stop and follow SECURITY.md instead of opening a PR.
-->

## What and why

<!-- What changes, and what problem it solves. The diff shows what; explain why. -->

## Governing artifact (required)

<!-- Link the spec for feature work, or the issue for a fix. -->

- Spec: `specs/NNN-…` <!-- or "N/A — bug fix / trivial" -->
- Issue: #

## Contribution class (required)

<!-- Check one. See CONTRIBUTING.md — this determines the review bar. -->

- [ ] Trivial (docs, typos, comments, tests only)
- [ ] Bug fix
- [ ] Feature / behavior change
- [ ] Capability pack content
- [ ] Provider implementation
- [ ] Hook
- [ ] Policy bundle
- [ ] Sealed core (identity, hook engine, registries, audit schema, durability, adapters)
- [ ] Tool registration (MCP server or native tool)
- [ ] Portal / UI

## Constitution impact (required)

<!--
Which principles does this touch, and how does it satisfy them? "None — no principle
is implicated" is a valid answer for trivial and most bug-fix PRs. If this amends the
constitution itself, link the amendment PR and its Sync Impact Report.
-->

## Testing

<!-- What you ran and what it proves. Paste failures you fixed, not walls of output. -->

- [ ] `make check` passes
- [ ] New/changed behavior has tests; fixes have a regression test
- [ ] Conformance suite passes (adapters, providers, sealed core)
- [ ] Eval gates pass (packs, prompts, models, policies)

## Governance checklist

<!-- Applies to any change that touches enforcement, identity, tools, or data paths. -->

- [ ] Enforcement paths **fail closed**, with a test proving denial on internal error
- [ ] Correlation ID propagates through new code paths
- [ ] No secret values in code, logs, spans, audit records, tests, or fixtures
- [ ] Side effects are idempotent and safe to retry
- [ ] Scopes only narrow — nothing widens a scope or bypasses an approval
- [ ] Tools reached only through the registry; no direct product API calls from agent code

## Documentation and compatibility

- [ ] User-facing docs updated in this PR
- [ ] New terms added to `docs/glossary.md`
- [ ] Changelog entry added (user-visible changes)
- [ ] New dependencies justified below, or none added
- [ ] **Breaking change to a versioned seam?** If yes, describe the deprecation window
      and migration path — an unmarked breaking seam change will be reverted

<!-- Dependency justification, if any: -->

## Anything reviewers should know

<!-- Trade-offs you made, alternatives you rejected, areas you'd like scrutinized,
     follow-up work you're deliberately deferring. -->

---

- [ ] All commits signed off (`git commit -s`) per the DCO
