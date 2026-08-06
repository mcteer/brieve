<!--
Sync Impact Report
- This revision (1.5.0 → 1.6.0, MINOR — one enumeration widened by one; no principle removed
  or redefined). Motivated by ADR-0062, Accepted in this same change.

  **Principle IV's exception list is closed at two, and 038 makes it three.** The clause reads
  "with exactly two named exceptions, both rotated and Control-Group-governed: the management
  token behind the TFE broker (ADR-0044), and the model vendor credential behind the model
  broker (ADR-0058)." Authoring adds a third: the version-control App private key behind the
  authoring credential path (ADR-0062).

  **The alternative was to argue the clause does not bite**, since it bounds credentials "to
  anything it manages" and this platform does not manage the requester's repository. That
  reading is genuinely available — and it is the narrowing v1.4.0 declined when the model
  vendor credential arrived. That revision amended the enumeration in the open rather than
  reasoning the new credential out of it, and `tests/unit/test_no_static_credentials.py`
  records why: "a gate that passes by vocabulary is worse than no gate." **A closed list that
  grows by interpretation is not a closed list**, so this is an amendment rather than an
  argument.

  **MINOR rather than MAJOR**, on v1.4.0's own precedent — which added an exception to this
  same enumeration and called it MINOR. Nothing permitted becomes forbidden and nothing
  forbidden becomes permitted for the two that already existed. The third inherits every
  condition they carry: rotated, Control-Group-governed, trust-store only, read under the
  reading workload's own attested identity, delivered per task, never persisted by any
  workload.

  **The cost is stated rather than absorbed.** Exceptions compound: the argument for a fourth
  is easier than the argument for this one was, because a list of three reads as a pattern
  where a list of two read as a boundary. That is the real price of this revision, and a
  maintainer should be able to weigh it rather than discover it.

  Propagation: `docs/adr/0062-authoring-credentials-are-vended-per-task.md` (new, motivating
  record), `docs/adr/README.md`, `tests/unit/test_no_static_credentials.py` (the gate's
  exemption table, which enumerates what may hold a credential name).

Prior Sync Impact Report
- This revision (1.4.0 → 1.5.0, MINOR — one enumeration narrowed to describe the surfaces that
  exist; no principle removed or redefined). Motivated by ADR-0060, Accepted in this same
  change.

  **The document named a transport this platform does not have, and never will.** Principle II
  read "Northbound: exactly four transports — MCP, API, CLI, portal". Three were built (008,
  009, 012); the CLI was never started, and was formally tabled on 2026-07-28 as a scheduling
  decision with ADR-0033 left standing. ADR-0060 converts that tabling into a withdrawal, and
  this amendment makes the clause describe the platform: **exactly three — MCP, API, portal**.

  **This is the same class of defect ADR-0047 named in tests, one level up.** A stub that
  passes asserts a property nothing holds. A constitutional clause naming a surface nobody
  built asserts a shape the platform does not have — and this is the document every
  `/speckit.analyze` pass measures a specification against, so the false premise sat upstream
  of every future feature's analysis.

  **v1.2.0 fixed the gate and left the count.** That revision changed "surface parity across
  all four transports" to "across every pair of implemented transports", recorded as a
  correction rather than a policy change. It repaired the row that would have bound only at
  four. The enumeration it was gating went unexamined, which is why this is a second edit
  rather than part of that one.

  **MINOR rather than MAJOR.** The versioning rule makes MAJOR the removal or redefinition of a
  principle. Principle II's enforceable property is stated in its own rationale — "interception
  coverage, not protocol uniformity" — and that is untouched. One authorization core, parity as
  a conformance-asserted test, the thin-client rule, and the ADR gate on adding a transport all
  stand exactly as written. Nothing permitted becomes forbidden and nothing forbidden becomes
  permitted; the platform simply stops claiming a fourth surface. Recorded here rather than
  assumed, because a maintainer reading this later should be able to disagree with the call
  rather than only discover it.

  **Three is a ceiling, not a floor.** A fourth transport still requires an ADR — that gate is
  what the enumeration existed to hold, and narrowing the number does not loosen it.

  Propagation: `docs/adr/0060-three-transports-the-cli-is-withdrawn.md` (new, motivating
  record), `docs/adr/0033-four-transports-one-authorization-core.md` (status line only — the
  record is append-only and its Decision section is unchanged), `docs/adr/README.md`,
  `docs/glossary.md` (the surface list), `ROADMAP.md` (Tabled → Withdrawn, in both the
  transport table and the demand-gated backlog), `src/surfaces/__init__.py` and
  `src/surfaces/dispatch/__init__.py` (docstrings restating the count).

Prior Sync Impact Report
- This revision (1.3.0 → 1.4.0, MINOR — one exception added and one absolute softened to a
  bounded rule; no principle removed or redefined). Motivated by ADR-0058, Accepted in this
  same change.

  **Principle IV forbade something the platform now does, and saying so in the open is the
  point.** Two sentences moved, in two different paragraphs, and they had to move together:

  1. "with exactly one named exception" → "with exactly two named exceptions", the second
     being the model vendor credential, carrying the same rotation and Control-Group
     governance the first one does.
  2. "static API keys are prohibited without exception" → "prohibited as workload
     credentials", with the exceptions bounded by where they are held (the trust store only),
     whose identity reads them (the reading workload's own, attested), how they are delivered
     (per task), and what is forbidden regardless (persistence by any workload).

  Amending only the first would have left the second flatly contradicting it — which is the
  contradiction this amendment exists to end, reproduced in miniature.

  **Why this was unavoidable rather than convenient.** ADR-0044's federate-or-broker rule
  already decided it: a model vendor authenticates with a static key and validates no workload
  identity, so it lands in the broker branch. The doctrine anticipated this; the constitution's
  wording had not. Three consecutive features (024, 025, 026) built a governed answering
  capability that no person could use, each recording the deferral rather than resolving it,
  because resolving it required this edit.

  **MINOR rather than MAJOR**, on the versioning rule that MINOR adds or expands: no principle
  is removed and none is redefined. What changes is that a second exception is named, under the
  same governance as the first. The record is honest that this is a real reduction in the
  strength of the zero-standing-credentials guarantee — ADR-0058's Consequences says so
  plainly — and MINOR reflects the shape of the edit, not a claim that it is free.

  **Shipped WITH the capability, never after it.** A plan that merged the broker first would
  have left the platform contradicting its own constitution in the interval, which is worse
  than either state alone.

  Propagation: `docs/adr/0058-model-credential-brokering.md` (new, motivating record),
  `docs/glossary.md` (model credential, model authority, brokered material),
  `tests/conformance/identity/test_posture_matches_constitution.py` (the deployment must not
  contradict the amended text), `tests/unit/test_no_static_credentials.py` (one named module
  exemption, at the same grain and in the same change).

Prior Sync Impact Report
- This revision (1.2.0 → 1.3.0, MINOR — one passage corrected to describe a mechanism that
  exists; no principle removed or redefined). Motivated by ADR-0056 and ADR-0057, both
  Accepted 2026-07-31.

  **Principle IV described something the substrate cannot do.** "attested workload identity →
  control-plane Vault → RFC 8693 + RAR against ceiling policies" conflated two RFCs. Vault
  CONSUMES RFC 9396 rich authorization requests — reading `authorization_details` from a
  presented JWT and enforcing them against a ceiling — and does NOT perform RFC 8693 token
  exchange: its OIDC provider's token endpoint accepts `authorization_code` and nothing else,
  established in ADR-0056 from the binary's own request schema. Vault is an OAuth *resource
  server*; the endpoint is even named `sys/config/oauth-resource-server`.

  What runs, and is correct: the allocation presents its Nomad workload identity to a JWT
  auth-method role and receives a token carrying that role's ceiling policies with a one-hour
  TTL. Manufactured per allocation from an attested identity, bounded in time, nothing
  standing — which is the principle's substance, unchanged.

  **MINOR, not MAJOR, on the same reasoning v1.2.0 applied to the ADR-0033 wording**: this is
  a correction, not a policy change. The principle's requirements are untouched — zero
  standing credentials, authority manufactured per task, evaporating with it, never exceeding
  the human. Only the sentence naming the mechanism was wrong, and it was wrong from
  ratification rather than being changed now. Nothing that was permitted becomes forbidden and
  nothing forbidden becomes permitted.

  Also added, because its absence is what let the error stand: task scope MAY narrow the
  ceiling and is not required to. ADR-0057 records why read scopes deliberately do not — these
  agents read widely before acting, and narrowing that makes the output worse while making the
  trail look stricter.

  Propagation: `docs/adr/0048-nomad-is-the-agent-execution-substrate.md` (amendment appended,
  Decision left in place — the record is append-only), `docs/glossary.md` (effective authority;
  a RAR entry added).

Prior Sync Impact Report
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
identity via OIDC; telemetry via the collector); adding a class REQUIRES an ADR. Northbound: exactly three transports — MCP,
API, portal — over one authorization core (ADR-0060; the CLI is withdrawn); the same operation on any transport
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

### Principle IV — Zero Standing Credentials; Authority Per Task (R2, R3, ADR-0015, ADR-0016, ADR-0025, ADR-0026, ADR-0033, ADR-0042, ADR-0044, ADR-0058)

The enclave holds no standing credentials to anything it manages — with exactly three
named exceptions, all rotated and Control-Group-governed: the management token behind
the TFE broker (ADR-0044), the model vendor credential behind the model broker
(ADR-0058), and the version-control App key behind the authoring credential path
(ADR-0062). Authority is manufactured per task — attested workload identity →
control-plane Vault, bounded by the definition's ceiling and by a short lifetime — and
evaporates with it; effective authority = user ∩ agent ceiling ∩ task scope ∩ policy, so an
agent never exceeds its human. **Task scope may narrow the ceiling; it is not required to.**
For read access the ceiling is the task scope by design, because an expert agent denied
context advises badly and silently (ADR-0057). RFC 9396 rich authorization requests, which
the control-plane Vault consumes and enforces, are the mechanism for narrowing **write and
act** scopes when a ceiling carries them (ADR-0056). Credential translation follows one rule (ADR-0044): federate
where the product validates external identity; broker only where it cannot. Brokered
action is entitlement-mirrored — the requester's own effective product entitlements
are resolved and enforced pre-tool-use, before any shared-grain credential is wielded
— so product-side authority matches the user's: no amplification, no arbitrary
reduction, harness and product checks independently agreeing. Humans authenticate on
every surface via the organization's OIDC IdP (flows per ADR-0033); no local accounts,
no credential store. Machines use workload identity federation; static API keys are
prohibited as workload credentials — the three named exceptions above are held only in
the trust store, read under the reading workload's own attested identity, delivered per
task, and never persisted by any workload. IdP claim-to-role mapping is governed configuration
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

**Version**: 1.6.0 | **Ratified**: 2026-07-24 | **Last Amended**: 2026-08-05
