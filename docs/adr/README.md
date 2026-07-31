# Architecture Decision Records

This directory is the authoritative record of why this project's architecture is the way it
is. Each file records one decision: the forces that made it a decision, what was chosen, and
what that choice cost.

**These records govern.** Where any other document — including the constitution — conflicts
with the latest Accepted ADR, the ADR wins, and the conflicting document is amended in the
same change.

## How to read this directory

- **New to the project?** Read [0001](0001-framework-agnostic-core.md),
  [0002](0002-adopt-first-migrate-and-delete.md),
  [0006](0006-in-process-fail-closed-enforcement.md),
  [0007](0007-lean-and-federated-profiles.md), and
  [0015](0015-control-plane-vault-as-trust-fabric.md) first. Most of what follows is
  downstream of those five.
- **Writing a spec?** Your spec must declare which ADRs it touches. If your design
  contradicts an Accepted one, the path forward is a superseding ADR — not code that
  quietly disagrees.
- **Terms unfamiliar?** [`docs/glossary.md`](../glossary.md) defines everything used
  normatively here.

## Conventions

- **One decision per record.** "And also" in a decision is two ADRs.
- **Append-only.** Records are never edited to say something different. To change a
  decision, write a new ADR that supersedes the old one and update the old one's status
  line to point at it. Superseded records stay in place — links written years ago must
  still resolve.
- **Numbering** is zero-padded, assigned sequentially, never reused. Numbers here are
  independent of the numbering under `specs/`; say "ADR-0037" rather than "0037" to avoid
  ambiguity.
- **Amend versus supersede.** An *amendment* changes part of a decision that otherwise
  stands (see [0027](0027-scope-narrowed-to-enclave-and-harness-run-agents.md) amending
  [0012](0012-runtime-versus-attach-posture.md)). A *supersession* replaces it entirely
  (see [0008](0008-no-gateway-or-registry-product.md) superseding
  [0005](0005-adopt-gateway-substrate.md)).
- **Consequences state costs.** A record listing only benefits is marketing. The next
  person to revisit the decision needs to know what it actually cost.
- **Constitutional decisions** — those underlying a principle in
  [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md) — require the
  constitution to be amended in the same change.

## Adding a record

1. Copy [`template.md`](template.md) to `NNNN-short-slug.md` with the next free number.
2. Write it. The Context section is the part that matters most and the part most often
   skipped — it is what a reader in two years needs and cannot reconstruct.
3. Open it as its own pull request. ADRs are reviewed as decisions, separately from the
   code that implements them.
4. If it supersedes or amends an existing record, update that record's status line in the
   same pull request, and add the new row below.

## Index

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-framework-agnostic-core.md) | A framework-agnostic governed core with thin framework adapters | Accepted |
| [0002](0002-adopt-first-migrate-and-delete.md) | Build glue only — adopt upstream capability, and delete what upstream absorbs | Accepted |
| [0003](0003-horizontal-first-vertical-profiles.md) | Build horizontal; verticals ship as policy and content profiles | Accepted |
| [0004](0004-adopt-skills-as-governed-supply-chain.md) | Adopt upstream skills as a pinned, governed supply chain | Accepted |
| [0005](0005-adopt-gateway-substrate.md) | Adopt an existing gateway and registry substrate | **Superseded** by 0006, 0008 |
| [0006](0006-in-process-fail-closed-enforcement.md) | Enforcement lives in-process and fails closed | Accepted (one clause superseded by 0008) |
| [0007](0007-lean-and-federated-profiles.md) | Two deployment profiles; nothing blocking that could be a library | Accepted |
| [0008](0008-no-gateway-or-registry-product.md) | Ship no gateway or registry product — provider interfaces are the deliverable | Accepted |
| [0009](0009-adlc-stages-and-observability-planes.md) | An eight-stage agent lifecycle, and three observability planes joined by one correlation ID | Accepted |
| [0010](0010-enablement-as-versioned-product-layer.md) | Enablement is a versioned product layer, not documentation | Accepted |
| [0011](0011-harness-first-sdks-at-perimeter.md) | Harness-first for structural guarantees; extension SDKs at the perimeter | **Proposed** |
| [0012](0012-runtime-versus-attach-posture.md) | Harness-as-runtime leads; governance-attach is the committed second posture | **Proposed** — amended by 0027 |
| [0013](0013-adopt-agent-security-framework-taxonomy.md) | Adopt the vendor Agent Security Framework taxonomy | Accepted |
| [0014](0014-two-layer-runtime-protection.md) | Runtime protection is two-layered — in-process hooks, plus an optional wire-level guardrail | Accepted — amended by 0027 |
| [0015](0015-control-plane-vault-as-trust-fabric.md) | A dedicated control-plane Vault is the agent registry and trust fabric | Accepted |
| [0016](0016-control-groups-gate-authority-changes.md) | Control Groups gate what agents may become; hooks gate what agents do | Accepted |
| [0017](0017-primary-adapter-selection.md) | Pydantic AI is the primary adapter; the second adapter is demand-driven | Accepted |
| [0018](0018-grounded-reporting.md) | Reports are compiled from records, never composed from memory | Accepted |
| [0019](0019-adapter-on-framework-capabilities.md) | Restructure the adapter on framework capabilities; governance runs first | Accepted |
| [0020](0020-otel-only-backends-at-the-collector.md) | OTel-only in core; observability backends attach at the collector | Accepted |
| [0021](0021-connectivity-tiers.md) | Connectivity tiers are a third deployment axis | Accepted |
| [0022](0022-qualified-model-matrix.md) | Models ship as an eval-qualified matrix, pinned per definition | Accepted — extended by 0039 |
| [0023](0023-validated-designs-as-judgment-layer.md) | Vendor validated designs are the architectural-judgment layer | Accepted |
| [0024](0024-durability-provider-seam.md) | Durability is a provider seam; the default is a library, not a service | Accepted |
| [0025](0025-enclave-is-the-default-topology.md) | The agent management enclave is the default topology | Accepted (default-versus-edition under review) |
| [0026](0026-delegation-grants-and-per-step-tokens.md) | Long-running execution — delegation grants, per-step tokens, resume as re-observation | Accepted |
| [0027](0027-scope-narrowed-to-enclave-and-harness-run-agents.md) | Narrow the product to the enclave and the agents it runs | Accepted |
| [0028](0028-product-identity.md) | Product identity — simple, elegant, efficient | Accepted |
| [0029](0029-retrieval-in-existing-postgres.md) | Retrieval runs in the Postgres already deployed — no vector database | Accepted |
| [0030](0030-pinned-versus-consulted-artifacts.md) | Executed artifacts are pinned; consulted artifacts are fetched fresh | Accepted |
| [0031](0031-retrieval-telemetry-as-authoring-backlog.md) | Skills and retrieval are complementary; retrieval telemetry ranks the authoring backlog | Accepted |
| [0032](0032-delegated-run-versus-local-loop.md) | Two integration paths, differentiated by what is governed | Accepted |
| [0033](0033-four-transports-one-authorization-core.md) | Four transports over one authorization core | Accepted |
| [0034](0034-conversational-web-ui.md) | A conversational portal, as a thin client of the API | Accepted |
| [0035](0035-audit-as-a-governed-read-path.md) | Estate-state queries, and the audit plane as a governed read path | Accepted |
| [0036](0036-cost-estimation-boundaries.md) | Cost is estimated and gated, never managed or reported | Accepted |
| [0037](0037-tool-transport-policy.md) | Tool transport policy — MCP where mature, native tools otherwise | Accepted |
| [0038](0038-integration-uplift-workflows.md) | Integration and uplift work is a first-class workflow family | Accepted |
| [0039](0039-per-role-model-bindings.md) | Definitions pin per-role model bindings, not a single model | Accepted |
| [0040](0040-deferred-tool-disclosure.md) | Tool and capability disclosure is deferred by default | Accepted |
| [0041](0041-code-mode-requires-hook-parity.md) | Code mode ships only with verified per-call hook parity | Accepted |
| [0042](0042-duplicate-detection-and-precedent-cache.md) | Duplicate detection and precedent reuse — two mechanisms, neither skipping governance | Accepted |
| [0043](0043-judge-screened-precedent-reuse.md) | Judge-screened precedent reuse, fail-closed on uncertainty | Accepted |
| [0044](0044-authz-doctrine-and-credential-translation.md) | Authorization doctrine — two domains, entitlement mirroring, federate before broker | Accepted |
| [0045](0045-tiered-capabilities.md) | Skills and workflows are authored in competency tiers | Accepted |
| [0046](0046-multi-tenancy.md) | One platform, isolated tenants — using the products' own isolation primitives | Accepted |
| [0047](0047-conformance-gate-rows-attach-as-features-land.md) | Conformance gate rows attach as their features land — deferred rows are absent or explicitly skipped, never stubbed green | Accepted |
| [0048](0048-nomad-is-the-agent-execution-substrate.md) | Nomad is the agent execution substrate, and its workload identity is the attestation | Accepted |
| [0049](0049-consent-to-start-is-consent-to-finish.md) | Consent to start a run is consent to finish it; dependencies are monitored, not escalated | Accepted |
| [0050](0050-harness-ceilings-live-in-the-trust-fabric.md) | The harness-domain ceiling is its own record in the trust fabric | Accepted |
| [0051](0051-a-turn-is-evidence-a-thread-is-a-view.md) | A turn is evidence; a thread is a view | Accepted |
| [0052](0052-the-first-judge-is-qualified-by-a-human-labeled-seed-set.md) | The first judge is qualified by a human-labeled seed set | Accepted |
| [0053](0053-automated-skill-intake-gauntlet.md) | An automated intake gauntlet for skill adoption; the human gate is unchanged | Proposed |
| [0054](0054-model-written-orchestration-parity.md) | Model-written orchestration: per-call and per-delegation governance parity | Proposed |
| [0055](0055-audit-egress-for-tamper-evidence.md) | Tamper-evidence requires a copy outside the writer's blast radius | Accepted |
| [0056](0056-task-scope-needs-an-authorization-server-vault-is-not-one.md) | Task scope needs an authorization server, and Vault is not one | Accepted |

## Reviews

Structured reviews that produced decisions but are not themselves decisions:

| Record | What it covers |
| --- | --- |
| [GR-1](GR-1-gap-review.md) | Gap review — shared-responsibility dispositions (data lifecycle, module-registry integrity, control-plane disaster recovery, cost delegation). Produced [0045](0045-tiered-capabilities.md) and [0046](0046-multi-tenancy.md) |

## Open records

Two records remain **Proposed** and are expected to resolve rather than linger:

- **[0011](0011-harness-first-sdks-at-perimeter.md)** — awaiting the evidence
  [0012](0012-runtime-versus-attach-posture.md) is designed to produce.
- **[0012](0012-runtime-versus-attach-posture.md)** — an experiment with a defined decision
  point. It is partially amended by
  [0027](0027-scope-narrowed-to-enclave-and-harness-run-agents.md); when the decision point
  is reached it should be resolved to Accepted with a stated outcome, or superseded.

A Proposed record that has quietly become permanent is a failure of this process. Both are
reviewed on the recurring review cadence.
