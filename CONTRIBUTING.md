# Contributing to the Enterprise Agent Harness

Thank you for your interest in contributing. This project is governed differently than
most open-source repositories, and ten minutes here will save you hours later:
**features begin as specifications, not code**, and every contribution is checked
against a written constitution. If you internalize one thing, make it this — a pull
request that arrives as unexplained code, however good, will be redirected into the
spec process rather than reviewed as-is.

**Contents**

- [Before you start](#before-you-start)
- [Where things live](#where-things-live)
- [Reporting bugs and requesting features](#reporting-bugs-and-requesting-features)
- [What kind of contribution is this?](#what-kind-of-contribution-is-this)
- [The spec-driven workflow](#the-spec-driven-workflow)
- [Development setup](#development-setup)
- [Coding standards](#coding-standards)
- [Engineering conventions](#engineering-conventions)
- [Authoring capability packs](#authoring-capability-packs)
- [Dependencies and supply chain](#dependencies-and-supply-chain)
- [Security practices for contributors](#security-practices-for-contributors)
- [Branching](#branching)
- [Testing expectations](#testing-expectations)
- [Documentation requirements](#documentation-requirements)
- [Accessibility](#accessibility)
- [Continuous integration](#continuous-integration)
- [Pull request process](#pull-request-process)
- [Code review](#code-review)
- [Versioning, deprecation, and releases](#versioning-deprecation-and-releases)
- [Proposing architectural change](#proposing-architectural-change)
- [AI-assisted contributions](#ai-assisted-contributions)
- [Project governance](#project-governance)
- [Communication](#communication)

## Before you start

Read, in this order:

1. **[The constitution](.specify/memory/constitution.md)** — ten principles every spec,
   plan, and implementation must satisfy. Reviewers check against it; so should you,
   before writing anything.
2. **[The glossary](docs/glossary.md)** — terms like *adapter*, *provider*, *capability
   pack*, *native tool*, and *entitlement mirroring* have precise meanings here. Using
   them loosely is the most common source of review friction.
3. **[The Architecture Decision Records](docs/adr/)** — the authoritative, append-only
   record of why things are the way they are. If your idea contradicts an Accepted ADR,
   the path forward is proposing a superseding ADR, not code that quietly disagrees.

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md). Participation implies
acceptance. Security vulnerabilities go through [SECURITY.md](SECURITY.md) — never
through public issues.

## Where things live

Working from a clone rather than the GitHub web UI? Everything the process depends on
is a file in the repository. The templates in particular are worth reading directly —
GitHub presents them automatically in the browser, but if you are composing a commit
message and PR body in a terminal, you need to know they exist and what they ask for.

| Path | What it is |
| --- | --- |
| `.specify/memory/constitution.md` | The ten principles. Every plan is checked against it |
| `.specify/templates/` | Spec, plan, and task templates used by the Spec Kit commands |
| `specs/NNN-feature-name/` | Per-feature spec, plan, and tasks — generated, never hand-edited |
| `docs/adr/` | Architecture Decision Records; `template.md` is the format for new ones |
| `docs/glossary.md` | Authoritative definitions for terms used normatively |
| `docs/development/testing.md` | Test taxonomy, fakes, governance assertions, eval authoring |
| `.github/PULL_REQUEST_TEMPLATE.md` | **The required PR description format.** Copy it into your PR body if your tooling doesn't populate it |
| `.github/ISSUE_TEMPLATE/bug_report.yml` | Required fields for a bug report |
| `.github/ISSUE_TEMPLATE/feature_request.yml` | Required fields for a feature request |
| `.github/ISSUE_TEMPLATE/config.yml` | Issue routing; blank issues are disabled |
| `AGENTS.md` | Instructions AI coding agents read automatically |
| `SECURITY.md` | Private vulnerability reporting — never use the issue tracker |
| `CODE_OF_CONDUCT.md` | Community standards and enforcement |
| `tests/harness/` | Fakes and assertion helpers for writing tests |

If you open pull requests from the command line (`gh pr create`, or a plain `git push`
plus the web form), the PR template is not always filled in for you — read
`.github/PULL_REQUEST_TEMPLATE.md` and paste it in. A PR arriving without the template's
sections will be asked to add them, which costs everyone a round trip.

## Reporting bugs and requesting features

**Before filing**: search existing issues and discussions. For anything that looks like
a vulnerability, stop and follow [SECURITY.md](SECURITY.md) instead.

Blank issues are disabled — every report arrives through a form. The forms live at
`.github/ISSUE_TEMPLATE/` and are presented automatically when you open an issue on
GitHub; read them there if you are working from a clone.

**Bug reports** — [`.github/ISSUE_TEMPLATE/bug_report.yml`](.github/ISSUE_TEMPLATE/bug_report.yml).
The form requires the environment detail that makes a report actionable: harness
version, deployment profile and substrate, connectivity tier, adapter and pack
versions, expected versus actual behavior, and a reproduction. Two things the form
cannot enforce and you must get right: for governance behavior include the correlation
ID and the relevant hook decision — "it denied my tool call" without one is usually
unactionable — and **redact before filing**. Never paste raw audit records, tokens,
real infrastructure identifiers, or customer data.

**Feature requests** — [`.github/ISSUE_TEMPLATE/feature_request.yml`](.github/ISSUE_TEMPLATE/feature_request.yml).
The form asks for the problem before the solution: who is blocked, what they are trying
to accomplish, and why existing extension points don't suffice. Requests that would
change architecture are ADR conversations — the form asks you to flag that, and the
discussion will move there.

**Triage**: maintainers apply `type/*`, `area/*`, and `class/*` labels, plus
`needs-spec` when a request must enter the spec workflow. `good-first-issue` and
`help-wanted` mark work that is genuinely available; if an issue has an assignee, ask
before starting. Issues without a reproduction or clear problem statement get one
follow-up request and are closed as `needs-info` after 30 days of silence — reopening
with the missing detail is always welcome.

## What kind of contribution is this?

Different contribution classes carry different review bars. Identify yours first; it
determines everything downstream.

| Class | Examples | Bar |
| --- | --- | --- |
| **Trivial** | Typos, doc clarity, comment fixes, test-only improvements | PR directly; no spec |
| **Bug fix** | Restoring behavior a spec or ADR already defines | Linked issue + PR with a regression test; no spec |
| **Feature / behavior change** | New functionality, changed behavior, new integration | Full spec-driven workflow |
| **Capability pack content** | Tools, skills, workflows, evals for a managed product | Spec workflow + eval gates; skills additionally need provenance + injection-lens review |
| **Provider implementation** | A Registry/Gateway/Eval/Durability/Observability backend | Spec workflow + the relevant conformance suite passing |
| **Hook** | Custom pre/post-tool-use enforcement | Spec workflow + fail-closed behavior demonstrated in tests |
| **Policy bundle** | New or changed policy content | Spec workflow; lands in warn mode with telemetry before any enforce-mode promotion |
| **Sealed core** | Identity flows, hook engine, registries, audit schema, durability, adapters | Spec workflow **+ security-maintainer review, mandatory** — no exceptions |
| **Tool registration** | New MCP server or native tool | Registry lifecycle (proposed → security review → published); transport per the exists/mature/supported test |
| **Portal / UI** | Web surface changes | Spec workflow + accessibility conformance |

One clarification on the sealed-core gate, ratified during spec 001: creating empty or
marker-only stub packages under sealed-core paths (layout reservation — `__init__.py`,
`py.typed`, READMEs) does not by itself trigger security-maintainer review. The gate
attaches when behavior lands in those paths: identity, hooks, registries, audit
schema, durability, or adapter logic.

Not sure which class you're in? Open a discussion issue before writing anything. "Sealed
core" is defined precisely in the constitution (Principle V) — if your diff touches those
paths, the security gate applies whether or not you intended it to.

## The spec-driven workflow

This repository uses [GitHub Spec Kit](https://github.com/github/spec-kit). A feature
travels through ordered stages, each producing a reviewable artifact under
`specs/NNN-feature-name/`:

1. **`/speckit.specify`** — the specification: *what* and *why*, never *how*. Must
   declare which mandated requirements (R1–R17) and ADRs it implements or touches, and
   its evidence class where compliance-relevant.
2. **`/speckit.clarify`** — resolve the spec's open questions before planning.
3. **`/speckit.plan`** — the technical plan. Begins with a **Constitution Check**; a plan
   that fails it does not proceed, it gets redesigned or the spec is withdrawn.
4. **`/speckit.tasks`** — the ordered task list derived from the plan.
5. **`/speckit.analyze`** — consistency check across spec/plan/tasks. Findings that
   implicate a constitutional principle block implementation.
6. **`/speckit.implement`** — only now does code get written, against the analyzed task
   list.

**Reviewing a spec.** Six questions, learned from the first feature cycles — a spec
that passes all six is usually sound; a "no" on any is a finding to raise, not a nit:

1. Does every requirement that implements a decided rule cite the ADR that decided
   it — and are all cited ADRs Accepted, not Proposed?
2. Does anything the spec promises contradict or under-deliver a merged document
   (CONTRIBUTING, AGENTS.md, the testing guide)? Specs routinely contain
   "docs must match reality" clauses, which make such conflicts self-falsifying.
3. What interfaces, schemas, or paths does it create that later work will depend on
   — and is each one's hardest stability property (canonical encoding, versioning,
   exact names) either in scope or explicitly deferred with the interface stable?
4. Is the failure path specified for every success path — tool errors, dependency
   failures, records that cannot be written?
5. Which review gates does the contribution class trigger, and will the record show
   they ran?
6. Are all named contracts bound exactly — no "or equivalent" language anywhere in
   the spec or its design artifacts?

When clarification markers are resolved, the checklist notes record *how*: answered
directly by a human, or resolved by an agent under explicit delegation and reviewed
afterward. Both are legitimate; an unrecorded resolution is neither.

**The spec PR precedes the implementation PR.** Specs are reviewed and merged as their
own pull requests; the implementation PR links its governing spec. This is not ceremony
— it is how a reviewer distinguishes "the design is wrong" from "the code doesn't match
the design," and how the two get fixed in the right place.

**Working with the generated artifacts**: files under `specs/` are authored through the
command flow, not hand-edited afterward — if a spec needs to change, re-run the stage so
plan and tasks stay consistent. Agent command directories (`.claude/`, `.cursor/`, etc.)
are per-developer and gitignored; `.specify/` is committed and governed. Amendments to
the constitution itself follow its Governance section: PR against
`.specify/memory/constitution.md` with a Sync Impact Report, citing motivating ADRs,
security-maintainer review required.

## Development setup

Supported development platforms: Linux and macOS natively; Windows via WSL2.

```bash
git clone https://github.com/<org>/<repo>.git && cd <repo>
uv sync                  # Python toolchain and dependencies
uv run pre-commit install  # formatting, linting, and hygiene hooks
make check               # lint + typecheck + unit tests — your inner loop
make conformance         # the conformance suite — required before any adapter/provider PR
make test-full           # PR-tier tests: integration, scenario, fault injection, adversarial
make dev-up              # local stack: dev-mode identity fabric, Postgres, collector, harness
```

These six commands are the stable contract; their implementations may evolve, their
names will not. `make dev-up` brings up a local stack running the same harness that runs
in production, hooks in **warn mode**, with dev-mode backing services — so "works
locally, fails governance in CI" should not happen; if it does, that is itself a bug
worth filing. The portal (Node/TypeScript) has its own setup in its package directory.

Most contributors never need real infrastructure: the test harness provides fakes for the
identity fabric and product APIs. If your change genuinely requires a live Terraform or
Vault estate, say so in your spec — maintainers can advise on the minimum viable setup
rather than having you stand up an enclave.

## Coding standards

- **Commits**: [Conventional Commits](https://www.conventionalcommits.org/), with scopes
  matching contribution classes — `feat(pack): …`, `fix(core): …`, `docs(adr): …`.
  Squash-merge is the default; make the PR title a valid conventional commit.
- **Sign-off**: every commit carries a [DCO](https://developercertificate.org/)
  `Signed-off-by` line (`git commit -s`).
- **Python**: typed throughout; Pydantic models at every boundary — validation failures
  are loud, never coerced silently. Formatting and linting are enforced by pre-commit;
  don't argue with the formatter in review.
- **TypeScript** (portal): typed strictly, no `any` in reviewed code; the portal is a thin
  client — no business logic, orchestration, or model calls client-side (constitution,
  Principle II).
- **Layering**: the core never imports an agent framework; adapters import the core. If
  you find yourself writing logic in an adapter, stop and move it to core — an adapter
  containing more than glue means the abstraction is wrong.
- **Secrets**: never in code, fixtures, tests, or history — including "obviously fake"
  ones that scanners can't distinguish. Test credentials come from the test harness's
  factories.

## Engineering conventions

These exist because this project's guarantees are structural. Code that ignores them
compiles, passes unit tests, and quietly breaks the product's central claims.

- **Observability is not optional.** Propagate the correlation ID through every new code
  path — it is what joins prompt → hook decision → tool call → product run → audit entry.
  Every hook decision emits a span. Emit standard OTel only; never import a vendor
  observability SDK into core (backends attach at the collector).
- **Never log secret values, tokens, or raw credentials** — log references, hashes, and
  metadata. Captured prompt/completion content is subject to redaction and capture
  policy; if you are adding a new data path, say in your spec which data class it carries
  and how it is redacted.
- **Fail closed.** Enforcement code that errors must deny, never allow-on-exception. Any
  `except` around a policy, identity, or hook path needs a test proving denial on
  failure. This is the single most common source of security review rejection.
- **Side effects must be idempotent and fenced.** Anything that mutates external state
  carries a stable side-effect key and tolerates replay: runs resume by *re-observing*
  outcomes, never re-executing them. If your tool cannot be safely retried, that is a
  design problem to raise in the spec, not a caveat to note in a docstring.
- **No standing credentials in code you write.** Authority is manufactured per task and
  evaporates. If your design needs a long-lived credential, it needs an ADR.
- **Errors are typed and actionable.** Raise domain exceptions from the shared hierarchy;
  include the correlation ID; never swallow. User-facing failures should say what was
  denied and why — without leaking what the user isn't entitled to see.
- **Context economics matter.** Tool schemas and prompts consume context budget; deferred
  disclosure is the default posture. New tools ship with concise schemas and clear
  descriptions — verbosity is a real cost, not a style preference.
- **Least context across seams.** Hooks, providers, and extensions receive the
  narrowest inputs that serve them — specific fields, not container objects. Handing
  a mutable run, a secret, or an audit sink across an extension boundary is a review
  blocker even when today's callers are all trusted: seams outlive their first
  callers.

## Authoring capability packs

Packs are the most common substantial contribution and have their own shape. A pack
contributes product knowledge — not core behavior — through its manifest:

- **Tools** with declared risk classes (read | write | destructive | secret-touching) and
  transport chosen by the exists/mature/supported test; every tool registered before use.
- **Skills** at competency tiers (100→400), pinned with provenance. Adopted upstream
  skills require a provenance check, injection-lens review, and an eval pass — never
  auto-tracked bumps.
- **Workflows** composed from registered tools, with approval and plan-gate requirements
  stated explicitly.
- **Evals** — golden tasks for correctness plus the must-deny and must-decline classes
  relevant to the pack's surface. A pack PR without evals is incomplete; eval regressions
  block promotion even when unit tests pass.

New packs land behind their eval gates in warn-mode policy before any enforce-mode
promotion. If your pack introduces a new product integration, expect the tool
registration lifecycle (security review) to run in parallel with your PR.

## Dependencies and supply chain

- **Lockfiles are committed and authoritative.** Dependency changes go in their own
  commit, never bundled into a feature diff.
- **License compatibility is checked in CI.** Copyleft and source-available licenses
  (GPL/AGPL/BUSL/SSPL family) are not acceptable in the core dependency tree; if you need
  something under one, raise it before writing code. Contributions must be your own work
  or compatibly licensed, with provenance stated in the PR.
- **Core dependency additions need justification** in the PR description — the dependency
  tree is part of the audit surface regulated operators re-scan at every review. "It has a
  nice API" is not sufficient; a reviewer pushing back on a new core dependency is doing
  their job.
- **SBOM and provenance**: releases ship signed with an SBOM. Don't add build steps that
  fetch unpinned artifacts at build or run time.
- **Automated updates** are proposed by bots and reviewed like any other PR; security
  updates take priority and may be fast-tracked by maintainers.
- **GitHub Actions are pinned to full commit SHAs**, with the version tag as a
  trailing comment. Tags are mutable references; a compromised upstream tag runs
  arbitrary code in CI with this repository's permissions. Automated update PRs may
  bump the SHA and comment together.

## Security practices for contributors

- **Vulnerabilities**: report privately per [SECURITY.md](SECURITY.md). Do not open a
  public issue, and do not include a working exploit in a PR.
- **If you commit a secret** — even to a fork, even briefly — treat it as compromised.
  Notify maintainers immediately via the security channel, rotate it, and do not attempt
  to fix it by force-pushing over the history alone.
- **Threat-model your hooks.** A hook is enforcement code: state in your spec what it
  denies, what happens when it errors, and what an attacker who controls tool arguments
  could do. Hook PRs that only demonstrate the allow path will be sent back.
- **Untrusted content**: repository contents, retrieved guidance, tool results, and model
  output are untrusted input. Never let them determine control flow without validation,
  and never interpolate them into policy decisions or generated commands unescaped.
- **CI from forks** runs without secrets by design. If your change needs privileged CI, a
  maintainer will run it — don't work around the restriction.

## Branching

Trunk-based, short-lived branches. `main` is protected: no direct pushes, always
releasable, linear history via squash-merge.

- **Naming declares the class and its governing artifact**: `spec/NNN-short-name` for a
  spec PR; `feat/NNN-short-name` for its implementation — same NNN, and `feat/NNN` does
  not open until `spec/NNN` has merged; `fix/issue-NNN`, `docs/…`, `chore/…` for the rest.
  Keep feature branches alive for days, not weeks — if one is aging, the spec's task
  breakdown was too coarse; split it.
- **Release branches per channel**: `release/vX.Y` is cut from `main` at each release
  train. Stable and LTS branches receive backports only.
- **Main-first backports**: fixes land on `main`, then cherry-pick to affected release
  branches (label `backport/vX.Y`), so `main` is never missing a fix that shipped. The
  sole exception is an emergency hotfix branched from a release branch — it must
  forward-port to `main` in the same PR series; an unforwarded hotfix is treated as an
  open regression.
- **LTS branches take security and critical fixes only** — never feature backports. The
  12-month promise to regulated operators is stability; there is no such thing as a small
  feature backport.
- **Keeping current**: rebase on `main` rather than merging it in; force-push to your own
  branch freely, but re-request review afterward.
- **Delete the branch on merge.** Once a PR is successfully merged, delete its head
  branch on the remote (and locally if you still have it). Squash-merge via
  `gh pr merge --squash --delete-branch` is the preferred path; if you merge another
  way, delete the branch immediately afterward. Stale feature branches are noise —
  history lives in `main`.
- **Spec Kit tooling note**: the `specify` scripts create a single `NNN-short-name`
  branch. This repository keeps the two-branch convention — rename the generated
  branch to `spec/NNN-short-name`, and open `feat/NNN-short-name` only after the spec
  PR merges.

## Testing expectations

**Read [the testing guide](docs/development/testing.md) before writing tests here.** It
covers the rule that catches everyone out — tests are deterministic, evals are
statistical, and they never mix — plus the fakes, the governance assertion helpers,
fault injection for durability scenarios, and how to author evals.

Every PR: unit tests for what it changes; a regression test for what it fixes. Beyond
that, by class:

- **Adapters and providers** — the shared **conformance suite** must pass, including
  governance-ordering, fail-closed, registry-isolation, surface-parity, tool-call parity
  under deferred disclosure, and the durability scenarios. The suite is the definition of
  correct; a failing conformance run is a blocking finding, not a discussion point. New
  provider seams ship *with* their conformance tests.
- **Packs, prompts/skills, models, policies** — the relevant **eval gates**: golden tasks,
  must-deny and must-decline suites, citation accuracy where guidance is involved.
- **Hooks** — demonstrate fail-closed behavior explicitly: the test proving your hook
  *denies* when it should matters more than the one proving it allows.
- **Durability-affecting changes** — exercise kill/resume, re-auth-on-resume, and
  double-resume fencing, not just the happy path.
- **Schema and migration changes** — include forward-migration tests and, where state is
  durable, a demonstrated upgrade path from the previous released schema.

**Test data**: fixtures are synthetic. Never commit real customer data, real
infrastructure identifiers, or production audit records — including in eval corpora. Eval
cases derived from real incidents must be scrubbed and reviewed before contribution.

**Flaky tests** are treated as failures. Don't retry-loop around one; quarantine it with a
linked issue, or fix it. A test disabled without an issue is a review blocker.

## Documentation requirements

Documentation lives with the code and ships in the same PR:

- **Behavior changes update user-facing docs** in the same PR. "Docs to follow" is not
  accepted for merged behavior.
- **New terms go in [the glossary](docs/glossary.md)** — with its self-enforcement rule: if
  a document and the glossary disagree, one of them gets fixed in the same change.
- **Public API and interface changes** update their reference docs and, for seams, the
  compatibility matrix.
- **Changelog**: user-visible changes carry a changelog entry, prompted by the PR
  template (`.github/PULL_REQUEST_TEMPLATE.md`).
- **Operational changes** (new component, new config, new failure mode) update the
  operations docs — including what breaks and what degrades, since "stale, not stopped" is
  a design promise that has to stay accurate.

## Accessibility

Portal contributions meet **WCAG 2.2 AA**. This is a hard requirement, not a best-effort
target: public-sector operators are legally bound (Section 508 and equivalents), and an
inaccessible surface disqualifies the product for them entirely. Practically: keyboard
navigability for every interaction, visible focus states, semantic markup with ARIA only
where semantics are insufficient, contrast compliance, no information conveyed by color
alone, and screen-reader-sensible streaming output. Automated checks run in CI; they catch
a minority of issues, so manual keyboard and screen-reader passes are expected for new
views.

## Continuous integration

Every PR runs: lint, type checks, unit tests, spec-artifact lint, license compliance,
secret scanning, and — by contribution class — the conformance suite, eval gates, and
accessibility checks. Required checks must be green before merge; advisory checks are
labeled as such.

Reproduce failures locally with `make check` and `make conformance` before pushing again;
CI is not a debugger. If a failure looks like infrastructure rather than your change, say
so in a comment rather than blind-retrying — repeated retries on a genuinely broken check
hide signal from everyone.

CI gate scripts are enforcement code. Every script backing a required check must be
demonstrably capable of failing — shipped with a test that runs it against a
violating input and asserts non-zero exit. A gate that always passes is a hole
wearing a checkmark, and adding one is a review blocker.

## Pull request process

1. Link the governing spec (feature classes) or issue (bug fixes).
2. Fill the PR template at [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)
   — GitHub populates it automatically when you open the PR. Complete every required
   section, including constitution impact; "none" is an acceptable answer, an empty
   section is not.
3. Keep PRs scoped to one spec or one fix. As a rule of thumb, a PR that takes more than
   an hour to review honestly is too big; reviewers may ask you to split, and splitting
   early is faster than splitting after review.
4. Mark drafts as drafts. Ready-for-review means CI is green and you have read your own
   diff.
5. Review gates depend on what you touched: **security-maintainer review** for sealed
   core, identity, hooks, tool registrations, and the constitution; **ops review** for
   release machinery; **compliance review** for evidence-relevant changes. One approving
   review from each applicable gate, plus one general maintainer approval. Maintainers
   will route your PR if it isn't obvious — say in the description what you believe it
   touches.
6. Re-request review after force-pushes.
7. After merge, delete the head branch (remote and local). Do not leave merged branches
   around — see [Branching](#branching).

Maintainers aim to acknowledge new PRs within a few business days. A redirect into the
spec process is a normal outcome for code-first feature PRs, not a rejection of the idea.

## Code review

**As an author**: explain *why* in the description — the diff already shows *what*.
Respond to every comment, even if only to disagree and say why. Don't force-push
mid-review without saying so. Assume good faith in terse comments; reviewers here are
reading for security properties, and that reads as blunt.

**As a reviewer**: review against the constitution, the spec, and the conventions above —
not personal preference. Distinguish blocking findings from suggestions explicitly (prefix
non-blocking comments with `nit:` or `suggestion:`). Say what would make it mergeable
rather than only what's wrong. Approve when it meets the bar and improves on the status
quo; perfection is not the standard, guarantees are.

**Deadlocks**: if author and reviewer cannot converge in two rounds, escalate rather than
grinding — ask a second maintainer to weigh in, or move the disagreement into the ADR
process if it is really about design. Unresolved design disagreements are decided per
[project governance](#project-governance); security-maintainer objections on sealed-core,
identity, or hook changes are not overridable by consensus.

## Versioning, deprecation, and releases

Everything versioned here follows [Semantic Versioning](https://semver.org/) — breaking =
MAJOR, additive = MINOR, fixes = PATCH — enforced most strictly on the **extension seams**
(hook SDK, provider interfaces, pack manifest schema), because the operator upgrade
promise is defined exclusively in their terms (constitution, Principle V). **An unmarked
breaking change to a seam is the most serious review failure this project recognizes.**

**Deprecation procedure**, in order: (1) mark deprecated in code and docs, naming the
replacement and the removal version; (2) emit a runtime deprecation warning where
feasible; (3) provide a migration path — automated where possible, documented always; (4)
keep it working for at least one full MINOR cycle, and for seams, one full release-channel
period; (5) remove only in a MAJOR release, listed in the changelog and upgrade notes.
Removing something that was never formally deprecated is a breaking change without a
window, and will be reverted.

**Releases** are cut by maintainers from `main` on the published trains (stable quarterly,
regular monthly, LTS annually). Release notes are generated from conventional commits and
changelog entries — which is why commit hygiene matters to people who will never read your
diff. Contributors don't cut releases, but accurate changelog entries and clear
breaking-change markers are what make the notes trustworthy.

## Proposing architectural change

Design disagreements are welcome; undocumented design drift is not. To change an
architectural decision: open an ADR PR that supersedes the existing entry (append-only —
supersede, never edit), with the constitution amended in the same change if the decision
underlies a principle. Small design questions fit in a spec's clarify stage; if your spec
review keeps circling a "why" question, that's the signal it is really an ADR
conversation.

## AI-assisted contributions

AI assistance is welcome — this project exists to make agentic work governable, and
[AGENTS.md](AGENTS.md) configures agents to work correctly in this repository.

The rules are simple and non-negotiable: **you are responsible for everything you
submit.** Understand your diff well enough to defend every line in review; "the model
wrote it" is not an answer to a review question. Verify that generated code doesn't
introduce dependencies, licenses, or patterns that violate the standards above —
generated code is a common source of plausible-but-wrong governance handling, especially
around fail-closed behavior and credential lifetimes. Your DCO sign-off attests that you
have the right to contribute the code, which requires having actually vetted it.
Disclosure of AI assistance is not required; competence is.

## Project governance

**Roles**: *contributors* (anyone), *maintainers* (merge rights in their areas), and
*security maintainers* (required approvers for sealed core, identity, hooks, tool
registrations, and constitutional amendments). Current maintainers and their areas are
listed in the repository's about page; ask in a discussion if you're unsure who owns an
area.

**Decisions** are made by consensus among maintainers where possible. Where consensus
fails, the relevant area maintainers decide; architectural questions go to the ADR
process, where the written record is the decision. Security-maintainer objections within
their domain are blocking and are not resolved by vote — this asymmetry is deliberate,
and it mirrors the asymmetry the product enforces on its own users.

**Becoming a maintainer**: sustained, high-quality contribution in an area, demonstrated
judgment in review, and nomination by an existing maintainer with no sustained objection.
There is no contribution quota; the bar is trust, and reviewing others' work well is the
fastest path to it.

## Communication

- **GitHub Discussions** — design questions, proposals, and anything open-ended.
- **Issues** — bugs and actionable feature requests.
- **Security channel** ([SECURITY.md](SECURITY.md)) — vulnerabilities and leaked
  credentials, always privately first.

Read the glossary before any of them. Welcome aboard — the process here is heavier than
most projects, deliberately: it is how a security-critical codebase stays reviewable by
the regulated organizations that depend on it.
