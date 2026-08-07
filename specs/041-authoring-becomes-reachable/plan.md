# Implementation Plan: Authoring becomes reachable

**Branch**: `spec/041-authoring-becomes-reachable` | **Date**: 2026-08-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/041-authoring-becomes-reachable/spec.md`

## Summary

038 built the authoring tier — handlers, containment, provenance, the two-task jobspec, the
credential type — and registered none of it. The gap is five layers deep (registration,
vocabulary, entrypoint, jobspec args, credential exchange), and 038's rows are green through
all five because they construct the handlers directly. This feature closes each layer in order,
using the seams that already exist rather than new ones: the trio joins the entrypoint's
registry construction behind `HARNESS_AUTHORING_ROLE`, the jobspec gains the `args` it never
had, `token_for()` gets its App-key exchange, and `open_proposal` gets its first production
handler — `git` push plus `gh pr create`, per the clarified transport determination. A
permanent `write` cell is qualified through ADR-0063's mechanical scorer, GitHub becomes a
named product with a probe so an outage suspension is revivable, and the capability ledger's
three `DELIBERATELY_UNREACHABLE` entries are consumed. One enclave row opens a real pull
request on a real repository, under the proposer task's own attested identity.

## Technical Context

**Language/Version**: Python 3.12 (repository standard, `uv`-managed)

**Primary Dependencies**: No new libraries. Adopted vendor CLIs: `git` (clone/push) and `gh`
(`pr create`) — subprocess-invoked from the proposer task, versions pinned in the task image.
Existing: Nomad (dispatch), Vault (trust fabric, App key at
`harness-authority/data/authoring/vcs-app`), Postgres (durability/audit).

**Storage**: Existing Postgres durability provider (checkpoint + `RUN_CONTINUE` handoff — no
schema change expected; 040 already widened intent records). Vault KV for the App key
(operator-seeded, ADR-0062). No new stores.

**Testing**: pytest — hermetic conformance rows (merge-blocking, `tests/conformance/authoring/`
extended), unit rows for the ledger sweep, and enclave-marked rows that fail-never-skip
(`make enclave-conformance` lane). 038's existing rows must pass **unedited** (FR-017).

**Target Platform**: The local enclave (Nomad + Vault + Postgres on the dev estate) for the
dispatched rows; fork-safe CI fast lane for hermetic rows.

**Project Type**: Single project — governed core (`src/core`) + surfaces (`src/surfaces`) +
infra (`infra/`), per repository layout.

**Performance Goals**: N/A in the web sense. Bounds that matter: subject clone size (see
research R4 — acquisition bound), 4 MiB read budget (exists), 1 h credential TTL (exists).

**Constraints**: The analyzer task holds no attested identity and no egress — the clone happens
pre-dispatch in the dispatching context (FR-027). The token reaches CLIs per invocation via
environment only (FR-023a). Authored content never enters the trail (FR-013, exists).

**Scale/Scope**: ~5 source modules touched (`handlers.py`, `toolset.py`, `entrypoint.py`,
`credential.py`, new publish handler), 1 jobspec, 1 Terraform module (probe/product record),
capability ledger, ~18–24 new conformance rows, 1 qualified `write` cell.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | `git`/`gh` are adopted vendor tools; the publish handler is thin glue around them. No MCP server authored (the registry-review determination, FR-023, is recorded in research R2). |
| II — Total Interception; One Governed Tool Layer | **Pass** | The trio enters through the same registry/hook pipeline as every tool; registration is the opt-in switch. New egress (git push, PR create) occurs **inside** a registered tool's handler in the proposer task, within its existing `github.com` allowlist. The pre-dispatch clone is dispatcher-context work, not agent-initiated egress — stated, and a row bounds it (research R3). |
| III — Fail-Closed, In-Process Enforcement | **Pass** | Unknown tool / outside ceiling / outside task scope all refuse in-process with distinguishable reasons (FR-019). No gateway anchor. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | ADR-0062's exception used as written: App key read under the proposer's own attested identity, token minted per task, never persisted, never checkpointed. Analyzer's identity **absence** is asserted structurally (existing `available()`). The clone credential is minted in the dispatching context the same way (research R5). |
| V — Sealed Core, Versioned Seams | **Pass, review owed** | Registries and the dispatch entrypoint are sealed core; touches are additive (a new registration branch, no signature changes). **Analysis added a second sealed touch**: `core/authority/intersection.py` learns to name the excluding term (T002a) so FR-019's third refusal layer has a mechanism — additive, named here for the review. Security-maintainer review = Dan, per repository roles. |
| VI — Lean by Default | **Pass** | No additional operated component — the MCP server was rejected partly on this ground. `gh` is a CLI in the task image, not a service. GitHub-as-product adds a probe entry, not a process. |
| VII — Anti-Fragmentation | **Pass** | One registry, one conformance suite; the substrate remains the only delta. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | The `write` cell is qualified through ADR-0063's mechanical scorer over the human-authored corpus and bound as an operator record; no auto-tracking. Sonnet 5 per the estate's standing decision, unchanged mid-feature (FR-012b). |
| IX — Evidence Over Claims | **Pass** | Proposal carries provenance + rationale (FR-031); trail carries paths/digests, never content (FR-013); the enclave row's named runner is recorded in the conformance contract (FR-024). |
| X — The Decision Record Governs | **Pass** | ADR-0062/0063/0064 consumed as written. One new ADR owed: the transport determination (FR-023) — recorded as a determination under Principle II's registry-review clause, not an amendment. |

**Gate result**: **PASS — proceed to Phase 0.**

**Post-design re-check (after Phase 1)**: still PASS. The design added no operated component
(R2 confirmed native CLIs), no new credential class (R5 reuses ADR-0062's path for both
callers), and no sealed-core signature change (the entrypoint branch and product-mapping table
are additive). The one new ADR (0066, transport determination) is a Principle II obligation the
plan carries deliberately, not a violation.

*Named-runner obligation (constitution v1.1.0)*: the enclave publish row (E-rows in the
contract) runs in the local enclave lane, which CI cannot reach fork-safely. **Named runner: the
agent harness, driven by the maintainer (Dan), recorded in
`contracts/conformance-authoring-reachable.md`.** The row fails rather than skips when the lane
or the App installation is absent.

## Project Structure

### Documentation (this feature)

```text
specs/041-authoring-becomes-reachable/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── conformance-authoring-reachable.md   # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
src/
├── core/
│   ├── authoring/
│   │   ├── tool.py          # exists — registration functions gain their first callers elsewhere
│   │   ├── credential.py    # token_for(): App-key exchange implemented (removes NotImplementedError)
│   │   ├── acquisition.py   # NEW — pre-dispatch clone of target_repository (FR-026/027/028)
│   │   └── publish.py       # NEW — open_proposal's production handler: git push + gh pr create
│   ├── authority/
│   │   └── intersection.py  # refusal names its excluding term (T002a — A2's mechanism)
│   ├── durability/          # scoped terminal-state scrub of kept requests (T024a, FR-033)
│   └── evals/
│       └── (authoring_corpus/scoring exist; qualification evidence recorded, not new code)
├── surfaces/
│   ├── handlers.py          # trio + publish handler join the platform tables; product mapping
│   ├── probes.py            # github probe joins PLATFORM_PROBES (FR-029)
│   ├── toolset.py           # platform-tool product mapping for dependency_products (FR-029/030)
│   └── dispatch/
│       └── entrypoint.py    # HARNESS_AUTHORING_ROLE branch: analyzer/proposer registry + flow
infra/
├── jobs/authoring-tier.nomad.hcl   # both tasks gain args; meta for subject path from acquisition
├── modules/trust-fabric/           # write-cell binding record; github product record if needed
└── bin/                            # enclave lane glue if needed (pattern: choice-conformance)
tests/
├── unit/capability_inventory.py    # trio leaves DELIBERATELY_UNREACHABLE (FR-015)
└── conformance/authoring/          # new reachability/publish/acquisition rows; 038 rows UNEDITED
docs/adr/
└── 0066-*.md                       # NEW — the transport determination (FR-023)
```

**Structure Decision**: single project, existing layout. Two new core modules (`acquisition.py`,
`publish.py`) stay product-blind — they know git-the-protocol and a forge-CLI contract, not
Terraform or Vault. Everything else is additive edits at existing seams.

## Complexity Tracking

No constitutional violations to justify. The one debatable addition — treating `git`/`gh`
subprocess calls as a new integration style — is resolved by Principle I (adopt vendor tooling)
and recorded in the FR-023 ADR rather than here.
