# Implementation Plan: Propose chat — repo URL to phased work to pull request

**Branch**: `spec/047-propose-chat` | **Date**: 2026-08-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/047-propose-chat/spec.md`

## Summary

Ship a **Propose** portal surface (and matching API/MCP operations) where a person pastes a
repository URL and a Terraform-oriented task. The platform validates ownership, acquires the
subject outside the hardened tier (`prepare_authoring_run`), dispatches **`authoring-tier`**
(not bare `agent-run`), runs ordered phases **Research → Plan → Write → Judge → Propose**,
exposes phase progress on the run view for live UI (existing SSE cadence), and on success
returns a real PR URL. Plan uses a **real** `terraform plan` oracle; Judge can deny; either
failure blocks publish (ADR-0047). Ask remains answer-only (ADR-0039).

## Technical Context

**Language/Version**: Python 3.12 (uv-managed); portal Jinja + existing `portal.js` SSE

**Primary Dependencies**: none new. Reuse `gh`/`git` CLIs (ADR-0066), Terraform CLI in the
Plan execution environment, existing authoring modules (038/041), Vault App credential path
(ADR-0062)

**Storage**: durability checkpoint for proposal payload + phase progress; Postgres audit /
run index as today; no new operated datastore

**Testing**: pytest hermetic (intake, phase state machine, fail-closed); enclave rows for
real PR + real plan when enclave has Terraform; named-runner live demo against owned demo repo

**Target Platform**: enclave (Nomad `authoring-tier` + Vault + Postgres); portal HTTPS

**Project Type**: single project — surfaces (API/portal/MCP), dispatch, handlers, infra jobs,
dev allowlist config

**Performance Goals**: phase updates visible within existing SSE poll bound (~2s); full propose
bounded by clone + model + plan + publish (minutes acceptable; UI must show phase, not silence)

**Constraints**: thin portal (ADR-0034); no agent picker on Propose; fabric vocabulary vs
callable registry stay distinct for ordinary runs; fail closed on ownership / plan / judge /
publish; no secrets in phase messages

**Scale/Scope**: Propose intake + phase progress API + dispatcher job/meta + entrypoint
orchestration + real terraform_plan + portal Propose UI + conformance contract. ROADMAP
unnumbered change-proposal intake for Terraform.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*
*Source of truth: [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md)
(v1.6.0).*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Terraform CLI and forge CLIs answer plan/publish; platform routes and gates. No new vendor SDK |
| II — Total Interception; One Governed Tool Layer | **Pass** | Authoring and plan tools stay on the registry/hook path; no direct product API from portal |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Ownership, plan fail, judge deny, publish error → no PR; phase failure stops later phases |
| IV — Zero Standing Credentials | **Pass** | VCS App key remains the named ADR-0062 exception, vended per task; no new standing secret |
| V — Sealed Core, Versioned Seams | **Pass, review owed** | May touch dispatch, surfaces, handlers, durability progress shape. Security review if sealed core schemas change. Named reviewer: Dan |
| VI — Lean by Default | **Pass** | Reuses authoring-tier job + SSE; no new operated component class |
| VII — Anti-Fragmentation | **Pass** | One propose path for API/MCP/portal; phase enum single source |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | Write/plan cells stay matrix-bound; no promotion of unqualified write |
| IX — Evidence Over Claims | **Pass** | PR carries bounded plan evidence; audit joins on correlation ID; portal renders platform words |
| X — The Decision Record Governs | **Pass** | Consumes ADR-0033/0034/0038/0039/0047/0064/0066/0068; no silent ADR conflict |

**Gate result**: **PASS — proceed to Phase 0.**

**Post-design re-check**: still **PASS**. Design wires existing `prepare_authoring_run` and
`authoring-tier`, adds phase progress as a run-view field (not a second authority), and keeps
Ask unable to act.

*Named-runner obligation*: enclave real-PR and real-plan rows when the lane cannot run on a
fork; live demo against `brieve-demo`. **Named runner: Dan McTeer (maintainer).**

## Project Structure

### Documentation (this feature)

```text
specs/047-propose-chat/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── conformance-propose-chat.md
└── tasks.md
```

### Source Code (repository root)

```text
src/surfaces/
├── api/                 # propose intake + run phase fields
├── portal/              # Propose nav, composer, phase strip (SSE)
├── mcp/                 # parity operations
├── dispatch/
│   ├── nomad.py         # authoring-tier job + subject_path meta
│   ├── authoring_dispatch.py  # production caller
│   ├── entrypoint.py    # phase orchestration + checkpoint
│   └── terraform_authoring.py  # NEW: plan evidence compose (mirror policy_authoring)
├── handlers.py          # real terraform_plan (replace fixture for authoring path)
infra/jobs/authoring-tier.nomad.hcl   # Terraform CLI / plan env as needed
infra/environments/dev/               # owned-repo allowlist for demo
```

## Complexity Tracking

| Violation | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| None anticipated | — | Agent-picker reuse rejected by product (spec FR-001) |
