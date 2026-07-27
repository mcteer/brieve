# AGENTS.md

Instructions for AI coding agents working in this repository. Read this fully before
making any change. Human contributors should read [CONTRIBUTING.md](CONTRIBUTING.md);
this file is the condensed, imperative version for agents.

## What this project is

A governed runtime for AI agents that operate infrastructure products (Terraform,
Vault, VCS) on behalf of people. Its guarantees are structural: per-task authority
that cannot exceed the requesting human, fail-closed policy enforcement on every tool
call, and an append-only audit trail joined by a single correlation ID. Code that
compiles and passes unit tests can still break these guarantees — most of this file
exists to prevent that.

## Non-negotiable rules

1. **No implementation without an approved spec.** Feature work follows the
   spec-driven workflow below. If asked to "just add" a feature, start the spec.
2. **Never weaken enforcement.** Enforcement code that errors must deny. Never convert
   a deny to an allow, never add an `except` that falls through to permitted, never
   make a hook optional or skippable.
3. **Never write secrets anywhere.** Not in code, config, tests, fixtures, commit
   messages, logs, or PR bodies — including plausible-looking fake ones. Use the test
   harness's credential factories.
4. **Never edit sealed core without an approved spec and a security review request.**
   Sealed core: identity flows, hook engine, registries, audit schema, durability,
   adapters.
5. **Never hand-edit generated spec artifacts.** Files under `specs/` are produced by
   the Spec Kit commands; to change one, re-run its stage.
6. **Never add a core dependency casually.** The dependency tree is audited by
   regulated operators. Adding one requires justification in the PR and is a
   legitimate reason for rejection.
7. **Stop and ask** when a task requires any of the above, or when the constitution and
   the request conflict. Do not work around the conflict.

## Read before planning

1. `.specify/memory/constitution.md` — ten principles; every plan is checked against
   them.
2. `docs/glossary.md` — terms here are precise (*adapter*, *provider*, *capability
   pack*, *native tool*, *ceiling*, *entitlement mirroring*). Use them exactly.
3. `docs/adr/` — the authoritative decision record. If a request contradicts an
   Accepted ADR, say so; the fix is a superseding ADR, not code that disagrees.
4. `docs/development/testing.md` — before writing any test.

## Workflow

Feature or behavior change — run in order, never skip:

```
/speckit.specify   → what and why (never how); declare R-requirements and ADRs touched
/speckit.clarify   → resolve open questions before planning
/speckit.plan      → how; begins with the Constitution Check — a failing check stops here
/speckit.tasks     → ordered task list
/speckit.analyze   → cross-artifact consistency; principle findings block implementation
/speckit.implement → only now write code, against the analyzed task list
```

**The stages are a pipeline, not a checklist — later artifacts derive from earlier ones.**
If a stage's output changes after a downstream stage has already run, re-run every stage
below it. In particular: `/speckit.analyze` routinely sends work back to `/speckit.clarify`,
and any resulting `spec.md` change invalidates the plan and task artifacts derived from the
old spec. Re-run `/speckit.plan` **and** `/speckit.tasks`, then `/speckit.analyze` again —
do not hand-patch `plan.md`, `tasks.md`, or `contracts/` to match a moved spec.

Practical consequences when re-running:

- **Re-running a stage regenerates its artifacts.** Diff before accepting — hand edits
  recorded in `tasks.md` (analyze remediations, gate notes) are not in the spec the stage
  regenerates from, and will be lost unless carried forward.
- **New requirements need new tasks.** An FR added during clarify with no task behind it is
  exactly the coverage gap the next `/speckit.analyze` will flag.
- **Constitution version matters.** If the constitution changed since the plan ran, the
  Constitution Check was performed against a document that no longer exists — re-check and
  record which version you checked against.

Bug fixes and trivial changes (typos, comments, doc clarity) skip the spec: fix, add a
regression test, open a PR linking the issue.

The spec PR merges before the implementation PR opens. Branch names bind them:
`spec/NNN-short-name`, then `feat/NNN-short-name` with the same NNN. After any PR
merges successfully, **delete its head branch** on the remote (and locally if present)
— prefer `gh pr merge --squash --delete-branch`. Do not leave merged branches around.

## Spec Kit artifacts: hard rules

Learned from the first feature cycles; these are review-blocking, not stylistic.

- **Never regenerate a reviewed artifact.** Once a spec, plan, or tasks file has been
  human-edited or human-reviewed, re-running its Spec Kit stage destroys reconciled
  state. Apply corrections as surgical edits to the existing file.
- **Named contracts bind exactly.** If a merged document names a helper, command,
  import path, or file, use precisely that name. Never write "or equivalent," "or
  similar," or a clear-equivalent substitute. If a documented name seems wrong, stop
  and surface it — the fix is reconciling the document, not improvising around it.
- **Verify quotes of other documents.** Before writing "as documented in X," read X
  and confirm it says that. If two merged documents disagree, surface the conflict
  and stop; never silently pick a side or inherit the inconsistency into a new
  artifact.
- **Cite the deciding ADR.** Every requirement that implements an already-decided
  rule cites the ADR that decided it. Traceability cites Accepted ADRs only —
  Proposed records are not governing authority.
- **Plans contain decisions, not alternatives.** "X or Y" in a plan's dependencies or
  tooling means two contributors build different systems. Resolve it in research, or
  mark it `[NEEDS CLARIFICATION]` — never leave the fork open.
- **Every success path has a failure sibling.** When specifying an allow/success
  flow, specify what happens when the body errors, the dependency fails, or the
  record cannot be written. Unspecified failure paths in enforcement or evidence code
  are review blockers.
- **Creating a seam is a commitment.** A new interface, schema, or import path that
  later features or operators will depend on must have its stability properties
  pinned in the contract — canonical encodings, versioning, exact paths — or an
  explicit deferral recorded with "interface stable now." "Decided at implementation
  time" is never acceptable on sealed-core schemas.
- **Never invent facts.** No product names, codenames, copyright holders, email
  addresses, or dates that have not been decided. Use an obviously neutral
  placeholder and flag it for the maintainer.

## Commands

```bash
uv sync              # install/refresh dependencies
make check           # lint + typecheck + unit tests — run before every commit
make conformance     # conformance suite — required for adapter/provider changes
make test-full       # PR-tier tests: integration, scenario, fault injection, adversarial
make dev-up          # local stack (dev identity fabric, Postgres, collector, harness)
pre-commit run -a    # formatting and hygiene
```

Run `make check` before declaring any task complete. Do not report success on work you
have not verified.

### You are the conformance gate

**CI does not run the durability rows, nor the enclave half of the API rows.** The fast
lane is fork-safe and cannot hold a Vault Enterprise licence, so it runs
`make conformance-hermetic`, which excludes them — durability by path, and the
enclave-marked API rows by marker, since `tests/conformance/api/` holds both kinds. No
required check covers either set. Nothing in GitHub will stop a merge that breaks them.

So before merging anything that touches durability, sealed core, an adapter, a provider,
`src/surfaces/`, `src/core/audit/`, or `infra/`:

1. `make dev-up` — the enclave must be **running**, not assumed
2. `make conformance` — all rows: the durability lane and the API evidence rows, both of
   which execute under an attested workload identity rather than a supplied token
3. Merge only if it passed. If the enclave cannot be brought up, **say so and do not
   merge** — report the gap rather than merging past it

This is not ceremony. ADR-0047 says a gate row is blocking from the moment its feature
exists, and for these rows the only thing standing between a regression and `main` is
this step. A conformance suite nobody runs is a conformance suite that does not exist.

The one property you get for free: the durability lane **fails loudly when the enclave is
absent** rather than skipping. You cannot obtain a false green by running it in the wrong
place — only by not running it.

## Repository layout

| Path | What it is | Rules |
| --- | --- | --- |
| `src/core/` | Framework-agnostic governed core | Sealed. Never imports an agent framework |
| `src/adapters/` | Bindings to agent frameworks | Sealed. Glue only — four mappings, nothing else |
| `src/surfaces/` | MCP, API, CLI | Sealed. All four transports share one authorization core |
| `portal/` | Web UI (TypeScript) | Thin client — no business logic, orchestration, or model calls |
| `packs/` | Capability packs (product knowledge) | Extension point. Tools, skills, workflows, evals |
| `hooks/` | Hook implementations | Extension point. Enforcement code — highest review bar |
| `providers/` | Registry/Gateway/Eval/Durability/Observability | Extension point. Ship with conformance tests |
| `specs/` | Spec Kit artifacts | Generated. Never hand-edit |
| `.specify/` | Constitution, templates, presets | Governed. Constitution changes need security review |
| `docs/adr/` | Decision records | Append-only. Supersede, never edit |
| `tests/harness/` | Fakes and assertion helpers | Public API under the semver promise |
| `.github/` | PR template, issue forms, workflows | Use the templates verbatim — do not improvise a PR description |

## Code conventions

- **Python**: fully typed; Pydantic models at every boundary; validation fails loudly,
  never coerces. **TypeScript** (portal): strict, no `any`.
- **Layering**: core never imports a framework; adapters import core. Writing logic in
  an adapter means it belongs in core — move it.
- **Errors**: raise typed domain exceptions; include the correlation ID; never swallow.
  User-facing messages say what was denied without disclosing what the user may not
  see.
- **Conventional Commits** with class scopes: `feat(pack):`, `fix(core):`,
  `docs(adr):`. Every commit signed off (`git commit -s`).

## Governance patterns — apply to every change

- **Propagate the correlation ID** through every new code path. It joins prompt → hook
  decision → tool call → product run → audit entry. Dropping it breaks attestation.
- **Emit spans for hook decisions**; standard OTel only, no vendor SDKs in core.
- **Log references, never secret values.** Hashes and metadata are fine; values are not
  — including in error messages and traces.
- **Fail closed**: every `except` around policy, identity, hook, or audit code denies.
  Write the test that proves it.
- **Side effects are idempotent and fenced**: stable side-effect key, safe to retry;
  resumption re-observes outcomes rather than re-executing them.
- **No standing credentials**: authority is manufactured per task and expires. A design
  needing a long-lived credential needs an ADR.
- **Scopes only narrow.** Never widen a scope in a delegation chain or handoff.
- **Tools go through the registry.** Never call a product API directly from agent code;
  transport (MCP vs native) follows the exists/mature/supported test.
- **Keep schemas terse.** Tool schemas and prompts consume context budget; deferred
  disclosure is the default.
- **Pin GitHub Actions by full commit SHA** (version tag as a trailing comment).
  Never add or update an action by mutable tag.
- **CI gate scripts are enforcement code.** Never stub a required check to exit 0,
  and ship every gate script with a test proving it fails on violating input.
- **Pass the narrowest context across any hook or extension seam.** Never hand a
  whole mutable run/state object, secret material, or an audit sink to code outside
  the built-in governance set. If an extension needs a field, add the field — not
  the object that contains everything.
- **Every assertion must be able to fail.** Never assert against an object,
  fixture, or value constructed inside the assertion to satisfy it. A gate-tagged
  test that cannot fail is a governance hole with a green checkmark.

## Testing

Read `docs/development/testing.md` first. The rule that matters most:

> **Tests are deterministic. Evals are statistical. Never mix them.**

Never call a live model in a test — use `stub_model` or `scripted_agent`. Never
`sleep()` — advance `frozen_clock`. Never assert on model wording — assert on
structure and behavior.

Every enforcement test asserts four things: the decision, the audit record, the absence
of side effects, and the absence of leaked secret values. Use the helpers
(`assert_denied_closed`, `assert_audit_chain`, `assert_correlated`,
`assert_scope_narrowed`, `assert_no_secret_values`).

Hook changes require four cases: allows in scope, denies out of scope, **denies on
internal error**, and runs in governance order. Pack changes require their eval suites
(golden tasks, must-deny, must-decline, citation accuracy).

## Pull requests and issues

**Read `.github/PULL_REQUEST_TEMPLATE.md` and fill every required section** — governing
spec or issue, contribution class, constitution impact, testing, the governance
checklist, and docs/compatibility. "None" and "N/A" are acceptable answers; blank is
not. Do not write a PR description from scratch: the template is the required format,
and reviewers check it section by section.

When opening an issue, use the matching form in `.github/ISSUE_TEMPLATE/` —
`bug_report.yml` or `feature_request.yml`. Blank issues are disabled; supply every
required field rather than filing a free-form report.

Keep the change scoped to one spec or one fix. Update docs in the same PR as the
behavior change; add a changelog entry for user-visible changes; add new terms to
`docs/glossary.md`.

**Always delete the PR branch after a successful merge** (remote and local). Prefer
`gh pr merge --squash --delete-branch`. If the merge was done without deleting the
branch, delete it immediately afterward. Confirm with `git fetch --prune` / `gh` that
the remote head is gone before declaring the merge complete.

## When to stop and ask

Stop and surface the question rather than proceeding if:

- The request conflicts with the constitution, an Accepted ADR, or a rule above.
- The change would touch sealed core, identity, hooks, or the audit schema without a
  spec.
- You cannot satisfy a requirement without a standing credential, a widened scope, or
  an allow-on-error path.
- The correct behavior is genuinely ambiguous and the wrong guess would be a security
  property rather than a style choice.
- Tests fail in a way you do not understand. Do not disable, skip, or loosen a test to
  make a build pass — a failing governance test is information, not an obstacle.
- A `[NEEDS CLARIFICATION]` marker is in scope. Never resolve one silently. Default
  to surfacing the questions and waiting; resolve them yourself only when the human
  has explicitly delegated that in this session — and then list every resolution
  prominently for review, so the delegation and its outcomes are on the record.
