<!--
Sync Impact Report
- This revision (1.1.0 → 1.2.0, MINOR — three passages follow Accepted ADRs; no principle
  removed or redefined). Motivated by ADR-0049 (Accepted in the same change) and by a
  long-standing mis-statement of ADR-0033.

  1. Quality Gates, durability rows: "grant-expiry **parking**" → "grant-expiry **stop**".
     ADR-0049 supersedes ADR-0026's re-consent rule: a run reaching its grant's end has hit
     an execution bound, recorded and terminal, not a pause awaiting a human. `PARKED` is
     removed from the sealed core in the same change, so a row naming parking would have
     described behaviour that can no longer occur.

  2. Quality Gates: "surface parity across **all four** transports" → "across **every pair
     of implemented** transports". **A correction, not a policy change.** ADR-0033 says
     "the same operation attempted through *any* transport"; it never said all four. The
     row's wording mis-stated the ADR it exists to gate, and Principle X is explicit that
     where a document conflicts with an Accepted ADR, the ADR wins and the document is
     amended. As worded the gate would have bound only once a fourth transport existed —
     catching nothing at two or three, which is when divergence starts.

  3. Principle VIII: "or the run **parks**" → "or the run **stops** with the reason
     recorded". Same removal as (1), different trigger: no eval-qualified model cell is
     available. `SUSPENDED` is the tempting substitute here and is wrong — a cell becomes
     qualified through eval-gated promotion, which is human work, so suspending would
     reintroduce exactly the waiting-on-a-person ADR-0049 removes.

  Propagation: `src/core/run.py` (`PARKED` removed, `SUSPENDED` added),
  `src/core/durability/{checkpoint,resume}.py`, `tests/conformance/durability/rows.py`
  (the named gate row), `specs/005-durable-execution/contracts/conformance-durability.md`.

Prior Sync Impact Report
- Version: 1.0.1 — sourced from architecture v1.14; decision records ADR-0001–0047 plus
  GR-1 in docs/adr/
- This revision (1.0.1 → 1.1.0, MINOR — expands an existing gate; no principle removed
  or redefined): Quality Gates now require that a blocking row no automated check
  executes have a named party responsible for running it before merge, recorded in the
  feature's conformance contract. Motivated by specs/005-durable-execution, whose
  durability rows run against a real Vault and Postgres that the fork-safe CI lane
  cannot stand up — the first blocking rows in this repository with no automated runner.
  No change to what any row asserts.
- Prior revision (1.0.0 → 1.0.1, PATCH — clarifies when an existing gate binds; no
  principle removed, redefined, or expanded): Quality Gates conformance row scoped per
  ADR-0047 — each gate row is blocking from the moment its underlying feature exists, and
  is absent or explicitly skipped, never stubbed green, before then. Motivated by
  specs/004-primary-adapter, the first adapter to reach a gate enumerating rows for
  features scheduled after it. No change to what any row asserts.
- Prior revision (1.0.0): wording condensed throughout (no semantic change to any rule);
  per-transport auth flows and scenario detail delegated to cited ADRs
- Authority: docs/adr/ — where this document conflicts with a later Accepted ADR, the
  ADR wins and this document MUST be amended in the same change
- Propagation: plan-template.md (Constitution Check I–X, plus the named-runner
  obligation added in 1.1.0) · spec-template.md (Traceability) · tasks-template.md
  (gate task types) — synced 2026-07-26
-->

# Enterprise Agent Harness Constitution

Terms used normatively here are defined in [docs/glossary.md](../../docs/glossary.md).

## Core Principles

### Principle I — Build Glue Only (ADR-0001, ADR-0002, ADR-0008, ADR-0017)

The project's goal — simplifying adoption of infrastructure tooling through a governed
agentic expert — is served mostly by adopted components: official MCP servers, upstream
skills, vendor guidance, the organization's own IdP and policy engines. What this
codebase uniquely builds is the framework-agnostic governed core, plus thin glue around
it. The core never imports an agent framework; adapters import the core. An **adapter**
is the thin binding to one agent framework, mapping exactly four concepts onto core
machinery — tools → hook-wrapped MCP calls, state → durability, interrupts → approval
hooks, run context → identity/correlation; anything beyond that mapping belongs in
core. Adopt anything the upstream vendors ship or roadmap; migrate onto and delete
anything they absorb. Ship no gateway or registry product, ever — provider interfaces +
conformance suites are the deliverable.

*Rationale*: Orchestration is commodity and expertise content is adopted; the
governance layer is the one part nothing upstream provides. Duplicating what vendors
maintain creates permanent drift.

### Principle II — Total Interception; One Governed Tool Layer (R5, R11, R15, ADR-0032–034, ADR-0037)

Every agent-initiated external interaction MUST be a registered, hook-wrapped tool call
through the full governed pipeline; egress is deny-by-default, and API calls outside a
registered tool are prohibited everywhere. Transport is a tool property, governed by
one registry with one lifecycle and one metadata schema (owner, risk class, data
classification): **MCP** where a server exists, is mature, and is supported — a
determination made at registry review and revisited each semester, with migration onto
official servers as they mature (Principle I) — and **native** (in-process, typed API
integration) otherwise; authoring an MCP server is never required merely for protocol
uniformity. Registry review MAY
require process isolation (MCP) for secret-touching or destructive risk classes.
Non-tool egress is limited to enumerated classes (model inference via the gateway;
identity via OIDC; telemetry via the collector); adding a class REQUIRES an ADR. Northbound: exactly four transports — MCP,
API, CLI, portal — over one authorization core; the same operation on any transport
MUST yield the same verdict and equivalent audit events (conformance-asserted). The
portal is a thin client: no logic, orchestration, or model calls client-side.

*Rationale*: The enforceable property is interception coverage, not protocol
uniformity.

### Principle III — Fail-Closed, In-Process Enforcement (R7, ADR-0006, ADR-0014, ADR-0019, ADR-0027, ADR-0041, ADR-0044)

Every tool invocation MUST pass pre- and post-execution hooks in an in-process,
fail-closed pipeline; enforcement is never anchored in a gateway, mesh, or external
component. The GovernanceCapability MUST run first among co-resident capabilities and
fail closed (conformance-asserted). Capability loading is itself a hooked, audited,
ceiling-checked event. Policy engines hold disjoint jurisdictions — decision, credential issuance, plan content — and no rule is duplicated across engines (ADR-0044). Code mode ships in the governed path only with verified
per-call hook parity — sandbox safety is not governance; absent that verification,
packs use schema-based calling regardless of context-efficiency advantage.

*Rationale*: Anything bypassable by external misconfiguration is not a guarantee.

### Principle IV — Zero Standing Credentials; Authority Per Task (R2, R3, ADR-0015, ADR-0016, ADR-0025, ADR-0026, ADR-0033, ADR-0042, ADR-0044)

The enclave holds no standing credentials to anything it manages — with exactly one
named exception: the rotated, Control-Group-governed management token behind the TFE
broker (ADR-0044). Authority is manufactured per task — attested workload identity →
control-plane Vault → RFC 8693 + RAR against ceiling policies — and evaporates with
it; effective authority = user ∩ agent ceiling ∩ task scope ∩ policy, so an agent
never exceeds its human. Credential translation follows one rule (ADR-0044): federate
where the product validates external identity; broker only where it cannot. Brokered
action is entitlement-mirrored — the requester's own effective product entitlements
are resolved and enforced pre-tool-use, before any shared-grain credential is wielded
— so product-side authority matches the user's: no amplification, no arbitrary
reduction, harness and product checks independently agreeing. Humans authenticate on
every surface via the organization's OIDC IdP (flows per ADR-0033); no local accounts,
no credential store. Machines use workload identity federation; static API keys are
prohibited without exception. IdP claim-to-role mapping is governed configuration
behind Control Groups. Secret values never enter model context — references only.
Cached or precedent results never carry authority: every requester runs their own
token exchange, scope check, and approvals (ADR-0042). Checkpoints hold state, never
credentials; resume re-authenticates, never replays. Revocation is unilateral and
immediate; restoration is quorum-gated. Agents are structurally excluded from
managing their own platform.

*Rationale*: Non-repudiation and blast-radius containment follow from the identity
architecture or not at all.

### Principle V — Sealed Core, Versioned Seams (R16, ADR-0008, ADR-0024)

Identity flows, hook engine, registries, audit schema, durability, and adapters are the
sealed core. All extension occurs through semver'd interfaces with deprecation windows
and conformance-suite validation; the upgrade promise is defined exclusively in those
terms. Sealed-core changes REQUIRE an approved spec and security-maintainer review.

*Rationale*: Upgrade channels and preflight are only honest if the extension surface is
contractual.

### Principle VI — Lean by Default (R12, ADR-0007, ADR-0025, ADR-0028)

Nothing blocking may be added that could be a library, signed cache, or async emitter.
The Lean/enclave profile is the default; every additional operated component REQUIRES a
named trigger recorded in an ADR.

*Rationale*: Simple-to-adopt dies by a thousand optional dependencies.

### Principle VII — Anti-Fragmentation (ADR-0025, ADR-0046)

Across every deployment substrate, the core, control-plane posture, capability packs,
and conformance suite MUST be identical; the substrate is the only permitted delta.

*Rationale*: One governed golden path per organization, one codebase to certify.

### Principle VIII — Eval-Gated Promotion; Pinned vs Fresh (ADR-0004, ADR-0022, ADR-0023, ADR-0030, ADR-0031, ADR-0039)

Packs, prompts/skills, models, and policies promote only through eval gates — never
auto-tracked; model use only via a definition's binding map (ask / plan / write /
judge / summarize) over eval-qualified Qualified Model Matrix cells (pack × model ×
role), with fallback only to another qualified cell — recorded — or the run stops with
the reason recorded;
upstream skill bumps require provenance checks, injection-lens review, and an eval
pass. Eval-time judge models are themselves pinned, eval-promoted artifacts. What the
agent *executes* is pinned; what it *consults* is fetched fresh with
provenance-at-read. Silent deviation from validated design baselines is prohibited. No
air-gapped claim ships without a passing eval matrix on the target models.

*Rationale*: Ungated drift in any input is an ungated change to production behavior.

### Principle IX — Evidence Over Claims (ADR-0009, ADR-0018, ADR-0020, ADR-0032, ADR-0034–036, ADR-0039, ADR-0043)

One correlation ID joins prompt → hooks → MCP call → product run → audit entry, walkable
both directions; every hook decision is a span. The audit plane is never sampled,
append-only, hash-chained, never egresses by default, and is read only through a
governed tenant-scoped path — evidence access is itself audited. Reports are
presentation; attestation rests on records: RunReports validate against run records,
with read-back before terminal claims, and attestation states its scope (delegated run
vs local loop). A model verdict may gate a step but NEVER satisfies an approval
requirement that policy assigns to a human; audit always distinguishes model gates
from human approvals. Guidance answers carry visible citations; declining beats
confabulation. Cost figures are quoted from the estimator's output, scope-labeled, and
never enter evidence. The core emits OTel only; backends attach at the collector.

*Rationale*: A claim that cannot be reconciled to a record is a liability.

### Principle X — The Decision Record Governs (docs/adr/)

The in-repo ADRs are the authoritative record: append-only, with lineage; superseding
is recorded, never edited in place. Where any document — including this one — conflicts
with the latest Accepted ADR, the ADR wins and the document is amended in the same
change.

*Rationale*: Two sources of truth is zero sources of truth.

## Development Workflow

1. No implementation without an approved spec: specify → clarify → plan → tasks →
   analyze → implement; plans pass the Constitution Check before research begins.
2. Every spec declares the requirements (R1–R17) and ADRs it touches, plus its evidence
   class where compliance-relevant.
3. Review gates (encoded in CODEOWNERS): security maintainers for sealed core,
   identity, hooks, and this document; ops for release-stage; compliance for
   evidence-relevant changes.
4. Policies land in warn mode with telemetry before promotion to enforce mode.

## Quality Gates

- **Conformance suite** (blocking for adapters and providers). Each row below is blocking
  from the moment its underlying feature exists, and before then is absent or a single
  explicit skip carrying the ADR that defers it — never a passing stub (ADR-0047); the
  rows in force are recorded in each feature's conformance contract, and a feature that
  lands without adding its rows is a gate regression. **A blocking row that no automated
  check executes MUST have a named party responsible for running it before merge,
  recorded in that same contract; merging without that run is a gate regression, and
  "the check is not automated" is not a defence.** A gate whose only enforcement is
  everyone remembering is not a gate. Rows: governance-ordering and
  fail-closed assertions; tool-call parity under deferred disclosure (ADR-0040); registry isolation (agent-credential control-plane writes
  observed denied); surface parity across every pair of implemented transports; durability
  scenarios per
  ADR-0024/026 — kill/resume, re-observe-never-re-execute, re-auth-never-replay,
  double-resume fencing, grant-expiry stop, duplicate-side-effect rejection,
  drain-across-upgrade.
- **Eval gates** (blocking for packs, prompts, models, policies): must-deny safety
  suites; must-decline scope suites (ADR-0034/036); citation accuracy and
  refusal-to-confabulate; estate-state fixtures; report fidelity (ADR-0018).

## Governance

- **Amendments**: PRs against this file with a Sync Impact Report, citing motivating
  ADRs; security-maintainer review required; MAJOR changes additionally require the
  ADR-0016 quorum.
- **Versioning**: semver — MAJOR removes/redefines a principle; MINOR adds/expands;
  PATCH clarifies.
- **Review**: every semester review (with the MCP registry and ADRs) and every release
  train for drift against newly Accepted decisions; `/speckit.analyze` findings that
  implicate a principle block `/speckit.implement`.

**Version**: 1.2.0 | **Ratified**: 2026-07-24 | **Last Amended**: 2026-07-28
