# Enterprise Agent Harness

**An agentic expert for HashiCorp infrastructure tooling — governed, auditable, and
safe to delegate to.**

## Mission

Put senior infrastructure expertise at everyone's fingertips. Terraform, Vault, and
adjacent tooling are powerful but demand scarce, senior operational skill; the Harness
turns that expertise — captured once in skills, validated designs, modules, policies,
and golden-path workflows — into an agentic expert any team can direct in natural
language: in the IDE, on the command line, over an API, and in a conversational portal.

Security and governance are not the goal here; they are what make the goal reachable.
Every agent action executes under manufactured, evaporating authority mirroring the
requesting human's own permissions — never exceeding them — passes a fail-closed policy
pipeline, and lands in an append-only audit trail joined end to end by a single
correlation ID. Those guarantees are what make it safe to delegate infrastructure work
to an agent at all, and to let non-experts operate expert-grade tooling.

> This project is independent open source. It integrates with HashiCorp and IBM
> products but is not endorsed by, and does not speak for, either vendor.

## What it does

Three families of work, all through the same governed pipeline:

- **Guidance** — answer product and architecture questions from vendor docs and
  validated designs, with citations on every factual claim.
- **Adoption & integration** — do the expert work of bringing a product's features
  into your systems. Example: a developer who wants dynamic database secrets but
  doesn't know where to start points the agent at their Git repository; the agent
  analyzes the application, applies its integration expertise, writes the
  application-specific integration code, and opens a pull request back to that
  repository for the developer to evaluate, test, and merge. Writes always land as
  PRs, scoped to the requester's own repositories — the human stays the merge
  authority.
- **Operation** — governed day-2 work on the estate itself: plan-gated infrastructure
  changes, drift and incident context, lifecycle upkeep, with approvals for anything
  destructive.

## Status

Pre-release, under active development. Interfaces, schemas, and documentation are
subject to change until the first tagged release.

## How this project is governed

This repository practices spec-driven development with
[GitHub Spec Kit](https://github.com/github/spec-kit). Before contributing, read:

- **[Constitution](.specify/memory/constitution.md)** — the non-negotiable principles
  every specification, plan, and implementation is checked against.
- **[Architecture Decision Records](docs/adr/)** — the authoritative, append-only
  record of design decisions (ADR-001 onward). Where any document conflicts with the
  latest Accepted ADR, the ADR wins.
- **[Glossary](docs/glossary.md)** — authoritative definitions for the terms those
  documents use normatively (adapter, provider, capability pack, ceiling, …).
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — how features move from spec to plan to
  implementation, and which changes require security-maintainer review.

Also worth knowing before you contribute:

- **[Testing guide](docs/development/testing.md)** — the test taxonomy, the fakes and
  governance assertions, and the rule that catches everyone out: tests are
  deterministic, evals are statistical, and they never mix.
- **[AGENTS.md](AGENTS.md)** — instructions AI coding agents read automatically in
  Cursor, Claude Code, Windsurf, VS Code, and others. AI assistance is welcome here;
  you remain responsible for what you submit.
- **[Code of Conduct](CODE_OF_CONDUCT.md)** — how we treat each other. Review in this
  repository is technically direct; that applies to code, never to people.

## Security

Found a vulnerability? **Report it privately** — see [SECURITY.md](SECURITY.md), never
a public issue. That document also sets out what this project treats as a vulnerability
(governance bypass, scope amplification, cross-tenant leakage, audit tampering,
credential exposure) and what it does not (an agent doing something the requesting user
was already entitled to do).

## License

Licensed under the [Apache License, Version 2.0](LICENSE). A `NOTICE` file for
redistribution attribution may be added later; it is not required for local
development.

Contributions are accepted under the same license, certified via the
[Developer Certificate of Origin](https://developercertificate.org/) — sign off your
commits with `git commit -s`. No separate CLA is required.
