# Research: Propose chat (047)

**Branch**: `spec/047-propose-chat` | **Date**: 2026-08-13

## R1 — Propose is not Run-with-Author

**Decision**: New Propose intake and UI; do not make the agent dropdown the primary path.

**Rationale**: User rejected agent selection. Authoring request is a dispatch payload with
`target_repository` + `task`, not `agent_definition_id` as the user’s choice.

**Rejected**: Parsing a free-text Run message into AuthoringRequest while keeping the picker —
preserves the wrong mental model and leaves Plan/Judge unwired.

## R2 — Production caller for `prepare_authoring_run`

**Decision**: API/MCP propose handlers call `prepare_authoring_run` before Nomad dispatch;
clone stays outside the hardened analyzer.

**Rationale**: FR-027 / 041 — analyzer must not gain egress to clone. Module already exists;
zero production callers was the gap.

## R3 — Dispatch `authoring-tier`, extend dispatcher meta

**Decision**: Extend `NomadDispatcher` (or a propose-specific subclass used by the API) to
target `authoring-tier` with required `subject_path` (and aligned meta). Stop assuming every
dispatch is `agent-run` meta-only.

**Rationale**: Jobspec already requires `subject_path`. Today’s dispatcher cannot satisfy it.

**Rejected**: Running authoring tools on `agent-run` — breaks tier isolation and empty-egress
analyzer posture.

## R4 — Phase progress is platform truth, SSE is cadence

**Decision**: Persist ordered phase states on the run (durability and/or run view fields).
Portal SSE continues to poll `get_run` / `get_run_result` and renders `phases` — no new
capability (012 D8).

**Phase enum (user-visible, stable strings)**: `research`, `plan`, `write`, `judge`, `propose`
with states `pending` | `active` | `completed` | `failed` and optional `reason` (user-safe).

## R5 — Entrypoint orchestrates phases; checkpoint carries proposal

**Decision**: Analyzer path advances Research → Plan → Write → Judge, then `compose` +
checkpoint including `evidence`; proposer half publishes only if checkpoint present and prior
phases completed. Fix evidence round-trip noted in terraform-pr-demo-handoff.

**Rationale**: Spec FR-005/006/010/011; 041 two-task split is the seam for plan-before-propose.

## R6 — Real `terraform plan` oracle

**Decision**: Replace fixture-only plan for the propose/authoring path with a subprocess
invocation of Terraform CLI producing structured, redacted evidence. Failed final plan →
phase `plan` failed, no PR.

**Rationale**: ADR-0047 / ROADMAP; FR-009, SC-005.

**Rejected**: Shipping Propose with fixture plan “until later” — would be a gate that cannot
lose.

## R7 — Owned repositories allowlist

**Decision**: Resolve `owned_repositories` from deployment configuration (dev: explicit set
including the demo repo). Validate pasted URL after normalization to the same identifier
space used by acquisition/publish.

**Rationale**: `AuthoringRequest.validate` already refuses `repository_not_owned`.

## R8 — Judge fail-closed

**Decision**: Judge phase invokes a deny-capable check before publish (reuse sufficiency /
structured criteria patterns where fit). Always-allow is invalid. Deny → `judge` failed.

## R9 — Ask isolation

**Decision**: No propose operations on Ask routes; regression row SC-004 / FR-012.

## R10 — Parity

**Decision**: API and MCP expose propose + phase progress; portal is thin (ADR-0033/0034).
