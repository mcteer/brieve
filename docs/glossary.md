# Glossary

Authoritative definitions for terms used normatively in the [constitution],
[ADRs](adr/), and contributor documentation. When a document and this glossary
disagree, fix one of them in the same change — terms drift or they don't.

[constitution]: ../.specify/memory/constitution.md

## Platform & topology

**The Harness** — this project: a governed runtime for AI agents that help people
adopt, integrate, and operate infrastructure products — from guidance, to authoring
product integrations into an application's own codebase (PR-first), to governed
day-2 operations. (Not to be confused with Pydantic AI's library of the same name; see
*Naming collisions* below.)

**Harness core** — the framework-agnostic majority of the codebase: identity, hook
pipeline, MCP client, policy, durability, telemetry, registry clients, pack loader.
The core never imports an agent framework. It is the layer that authenticates to Vault
and records run state; the agent above it does neither.

**Test harness** (`tests/harness/`) — a *different thing entirely*: the fakes, fixtures,
and assertion helpers tests import, under its own semver seam promise. Nothing to do
with the Harness the product is. When both are in play, write "test harness" for this
one and never bare "harness".

**Enclave** — the default deployment topology (ADR-0025): an isolated, self-scaffolded
Nomad + control-plane Vault + Postgres cluster, built by the project's own Terraform,
sitting adjacent to — never inside — the estates it manages, holding no standing
credentials to any of them.

**Control-plane Vault** (internally "Agent Tier-0") — the dedicated Vault Enterprise
instance that is the agent registry and trust fabric (ADR-0015): agent identities,
ceiling policies, OAuth resource server. Human/CI-managed only; structurally
unreachable by the agents it governs.

**Workload Vault** — any Vault the organization runs as part of its estate. Purely a
managed product target of the Vault capability pack; never part of the control plane.

**Connectivity tier** — Connected / Restricted (allowlisted proxy egress) / Air-gapped
(none); an axis orthogonal to deployment profile (ADR-0021).

**Profile** — Lean (default: no gateway, embedded policy engine, one Postgres) or
Federated (organization-operated gateways/registries integrated via providers)
(ADR-0007).

## Extension model

**Adapter** — the thin binding between the harness core and one agent framework
(Pydantic AI primary, LangGraph fast-follow). Maps exactly four concepts onto core
machinery: tools → hook-wrapped MCP calls; state → durability; interrupts → approval
hooks; run context → identity/correlation. Anything beyond that mapping belongs in
core. Adapters are sealed core: a new one is an upstream contribution validated by the
conformance suite, not a downstream extension.

**Provider** — a versioned interface binding the harness to an external
*infrastructure service* an organization already runs: Registry, Gateway, Eval,
Durability, and Observability providers. Contrast with adapter (binds an *agent
framework*). Providers are extension points, validated by the conformance suite.

**Capability pack** — the unit of *product knowledge*: a manifest of tools (MCP
servers or native tools, each with a risk class), skills, pack hooks, workflows, and
evals for one managed product (Terraform pack, Vault pack, …). New products are new
packs; the core does not change.

**Surface** (or **transport**) — one of exactly four northbound client entry points:
MCP server, REST API, CLI, portal/web UI. All are thin clients of one authorization
core with conformance-asserted parity (ADR-0033).

**Sealed core** — the parts no downstream change may modify: identity flows, hook
engine, registries, audit schema, durability, adapters. Everything else extends
through semver'd seams: hooks, packs, prompt overlays, policy bundles, providers.

**Hook SDK** — the stable interface against which custom pre/post hooks are declared
in configuration, so organizations extend enforcement without forking.

## Identity & authority

**Agent definition** — the design-time, version-controlled declaration of an agent
(HCL): owner, purpose, adapter, packs, allowed tools and risk classes, maximum scopes,
prompt-bundle pins, allowed inter-agent edges. The unit of approval, upgrade, and
audit.

**Agent instance** — one running copy of a definition, registered at bootstrap with a
unique short-lived identity. Unregistered workloads obtain no credentials.

**Ceiling policy** — the compiled maximum authority of a definition, enforced by the
control-plane Vault. No task scope can exceed it.

**Effective authority** — user ∩ agent ceiling ∩ task scope ∩ policy, computed per
task via token exchange (RFC 8693 + RAR). An agent can never exceed the human it acts
for.

**Delegation grant** — the durable record of a user's consent to a long-running task;
per-step tokens are manufactured under it and evaporate. Checkpoints hold state, never
credentials (ADR-0026). Persisted in the `grants` table since 014 — before that the record
was built in memory and the `grant_id` a checkpoint carried resolved to nothing, so consent
expiry was unevaluable on the dispatched path.

**Resume** — reviving a disrupted run in a **new** allocation with a new attested identity,
so the prior credential is unobtainable rather than merely forbidden (ADR-0048). A resume is
*declared* by the dispatcher and never inferred from a run's identifiers: a fresh dispatch
reusing a used `run_id` stays a fresh dispatch. Ordered — terminal check, consent, ownership
claim, attempt count, then re-observation — because each step gates the next.

**Re-observation** — resolving an interrupted step by asking the product what happened rather
than assuming. A step whose intent was recorded and whose result was not may or may not have
taken effect, and only the product knows; a non-repeatable tool therefore requires an
observer. `CANNOT_DETERMINE` suspends the run naming the **product**, never the tool, because
the sweeper watches products.

**Resume-attempt cap** — the platform bound on how many times one run may be revived
(`RESUME_ATTEMPT_CAP`, 5). Counted on the checkpoint so it survives the disruption it counts,
incremented after the ownership claim so a failed claim costs nothing, and terminal on
exhaustion — never another suspension, which would wait for a revival that can never come.
Platform-set: never from workflow code, the definition, or dispatch metadata (FR-009c).

**`RUN_RESUMED`** — the audit event recording a revival and what came of it: attempt number
(1-based), outcome (`continued`/`stopped`/`suspended`), reason, and step counts. One event
with the outcome in the payload rather than three types, and written *before* the revived run
does anything, so a trail read in order shows the revival before its consequences.

**Act chain** — the on-behalf-of lineage in exchanged tokens (user → agent A →
agent B); scopes only narrow along it, preserving non-repudiation across handoffs.

**Entitlement mirroring** — the product-domain authorization rule (ADR-0044): agent
action in a product carries the requesting user's own authority — no amplification,
no arbitrary reduction — with the harness-side and product-side checks agreeing
independently. For brokered products, a pre-tool-use check resolves the user's own
effective product entitlements before any shared-grain credential is wielded (the
confused-deputy compensating control).

**Federate vs broker** — the credential-translation rule (ADR-0044): *federate* where
a product can validate external identity (workload Vault trusts the control plane
over JWT/OIDC; clouds via OIDC workload identity) — zero standing credentials in
either direction; *broker* only where it cannot (TFE: secrets-engine-minted, fresh
leased team tokens per request, backed by one rotated management token — the
platform's sole standing credential, Control-Group-governed).

**Control Groups** — Vault's multi-party approval mechanism, required for every
authority change on the control plane (ADR-0016). Hooks gate what agents *do*; Control
Groups gate what agents *may become*.

## Governance & enforcement

**Hook pipeline** — the ordered, fail-closed pre/post interception around every tool
call: identity injection, registry check, policy, approvals, redaction, audit
(ADR-0006/014). In-process by rule; never delegated to a gateway or mesh.

**GovernanceCapability** — the mandatory framework object implementing the hook
pipeline inside the adapter; conformance-asserted to run first and fail closed
(ADR-0019).

**Risk class** — per-tool classification: read | write | destructive |
secret-touching. Drives approval and plan-gate requirements.

**Egress class** — an enumerated, individually governed category of outbound
communication (managed-product MCP; reference retrieval; model inference; identity;
telemetry). Egress is deny-by-default; adding a class requires an ADR.

**Warn mode / enforce mode** — every policy lands observing-and-logging first, and is
promoted to blocking only with telemetry behind it.

**Agent registry** — the control-plane record of every definition and instance;
registration is enforced (no registration → no credentials), deregistration cascades,
records are never deleted.

**Native tool** — a registered tool implemented as an in-process, typed API
integration rather than an MCP server. Passes the identical hook pipeline, carries the
identical registry metadata and lifecycle. Used wherever no MCP server exists that is
mature and supported (a registry-review determination, revisited each semester);
registry review may require MCP (process isolation) for secret-touching or destructive
risk classes.

**MCP registry** (tool registry) — the governed catalog of every approved tool,
MCP server or native (owner, provenance, schemas, risk classes, data classifications,
review state), with lifecycle: proposed → security review → approved → published →
semester re-certification → deprecated → retired. The pre-hook refuses unregistered,
review-overdue, or version-drifted tools.

**Semester review** — the at-least-twice-yearly re-certification of the MCP registry,
ADRs, and constitution.

## Knowledge & artifacts

**Precedent cache / in-flight index** — two reuse mechanisms (ADR-0042/043): an
in-flight index checked before any tool call fires, surfacing a coordination offer
when the same repo/commit/task-class is already being worked; and a tenant-scoped,
provenance-stamped cache of prior design specs for non-concurrent repeats —
mechanically staleness-checked, judge-screened only on ambiguous survivors,
fail-closed to full resynthesis on uncertainty. Reuse never carries authority: every
requester runs their own token exchange, scope check, and approvals.

**Deferred disclosure** — the default tool-catalog posture (ADR-0040): a tool costs
one catalog line of context until the model reaches for it; schemas load on use.
Disclosure economics only — registry, hooks, and audit are unchanged, and tool-call
parity under deferral is conformance-asserted.

**Code mode** — executing tool calls from model-written code in a sandbox. Ships in
the governed path only with verified per-call hook parity (ADR-0041): sandbox safety
guarantees safe execution, not preserved governance. The candidate sandbox is **Monty**
(Pydantic, experimental as of 2026-07-29), whose relevant property is the
**external-function seam**: it has no ambient filesystem, network, or environment access, so
every external effect is a host-provided function call and execution pauses *at* that seam —
which is what would make parity structural rather than hoped-for (ADR-0054). Watched, not
adopted.

**Dynamic workflow** — model-written orchestration of *sub-agents* rather than tools: the
orchestrator writes one sandboxed script in which each sub-agent is an async function, the
tree runs inside a single tool call, and only the final value returns to its context. The
**roster is pre-declared** — the model composes the call graph, never the agent set. Each
sub-agent invocation is a **delegation**, so per-delegation governance parity is required, not
only per-call: the sub-agent runs under its own registered ceiling, scoped at or below its
parent, on the same correlation ID (ADR-0054). Proposed; upstream is experimental.

**Skill** — pinned, provenance-checked instruction content the agent *executes by*;
adopted from upstream skill repositories with overlays authored here (ADR-0004).

**Supply-chain sentinel** — the proposed automated intake gauntlet for skill adoption
(ADR-0053): a poller watches pinned upstream repositories, a narrow-ceilinged analysis agent
reads the diff in the hardened isolation tier, an automated adversarial read runs before any
detonation, and a clean static read proceeds to differential behaviour testing against the
golden-task corpus in a canary-seeded range. Produces an evidence package for a human
reviewer. **It raises the review's floor and never replaces its ceiling** — the analyzer's
verdict may block a promotion and never satisfies the approval.

**Pinned vs consulted** — the artifact-class rule (ADR-0030): what an agent *executes*
(skills, prompts, policies, models) is version-pinned and eval-gated; what it
*consults* (reference guidance such as HashiCorp Validated Designs) is fetched fresh
with provenance-at-read.

**Provenance-at-read** — recording URL, timestamp, and content hash of retrieved
guidance, archived with the run record, so attestation cites guidance as published at
the moment of the decision.

**HVD** — HashiCorp Validated Design: vendor-published reference architecture,
treated as consulted (fresh) guidance. Precedence: skills < HVD baseline < explicit
organization policy; deviations are recorded in the **deviation register**, never
silently absorbed.

**Qualified cell** — one green (pack × model × role) entry in the matrix, carrying
`qualified_by` (fixture | live) and the judge that scored it. The only thing a binding map
may reference; withdrawn cells refuse at run start, not only at registration (013, D6).

**Competency tier** — what a definition may *compose* (ADR-0045). Bounds workflows, never
tools — the ceiling answers about tools, and no rule lives in two engines (ADR-0044). A
property of the definition, never of the request; tier 1 is fully-paved golden paths only.

**Seed set** (`evals/seed/`) — human-labelled verdicts terminating the judge regress
(ADR-0052). The first judge is qualified against it; every later judge by a qualified
judge. Floor: ≥20 cases, all four suites, ≥3 rejects — enforced, and a set below it fails
the gate.

**Risk class** — per-tool classification `read | write | destructive | secret_touching`,
carried on `ToolRegistration` since 013 (it lived only in this glossary before — research.md
F2). Drives registry review and Principle II's process-isolation provision; never drives
whether the trail is redacted, which every tool gets.

**Qualified Model Matrix** — the set of eval-qualified (pack × model × role)
combinations; the only cells a definition's **binding map** (ask / plan / write / judge / summarize
→ model) may reference (ADR-0022, ADR-0039). Fallback occurs only within qualified
cells, recorded — never to an unqualified model.

**Prompt bundle / policy bundle** — the pinned prompt/skill set and the composed
policy set referenced by a definition; versioned independently, pinned together.

**Tiered capabilities (100→400)** — competency tiers for skills and workflows; a
definition pins a tier, from fully-paved golden paths (100) to compositional freedom
(400).

## Evidence & observability

**Correlation ID** — the single identifier joining prompt → hook decisions → MCP call
→ product run → audit entry, stamped into product metadata, walkable in both
directions.

**Audit plane** — the never-sampled, append-only, hash-chained record; reads occur
only through a governed tenant-scoped path, and evidence access is itself audited
(ADR-0035).

**Grounded reporting / RunReport** — a typed report validated against actual run
records before release, with read-back before terminal claims; reports are
presentation, attestation rests on records (ADR-0018).

**Path A / Path B** — the two IDE integration modes (ADR-0032). Path A: delegated run,
executed server-side, fully governed, full attestation weight. Path B: local IDE loop
calling governed meta-tools — every security property holds, but reasoning is
ungoverned, so it evidences tool calls, not agent behavior.

**Thread** — a conversation in the portal: tenant-scoped, subject-owned, persisted run
state (ADR-0034), joined to everything it starts by one correlation ID. **A view, not the
record** (ADR-0051) — it is hard-deletable by its owner precisely because the audit trail
holds what it held, so deleting it masks nothing.

**Turn** — one exchange within a thread. An **accepted** turn (dispatched, declined, or
scope-refused) is written to the trail as `TURN_RECORDED` carrying the message verbatim,
*before* anything acts on it — a declined ask is still an ask. A **pre-acceptance** refusal
(rate-limited, oversized) is written as `TURN_REFUSED` carrying the message's size and
never its content, so a refusal cannot grow the append-only trail by whatever a caller
sends.

**Declined vs refused** — declined means *the platform cannot do this*; refused means
*this person may not*. Kept distinct because conflating them tells someone their access is
fine when it is not, and tells another that it is broken when they simply have none.

**Must-deny / must-decline** — release-gating eval classes: prompts the agent must
refuse for safety, and requests outside the product's declared scope it must decline
with a pointer elsewhere (e.g., audit-grade cost reporting) (ADR-0034/036).

## Process

**ADR** — Architecture Decision Record in `docs/adr/`: the append-only authoritative
record (ADR-0001 onward). Where any document conflicts with the latest Accepted ADR,
the ADR wins.

**Conformance suite** — the shared test suite every adapter and provider must pass:
governance ordering, registry isolation, surface parity, durability scenarios. The
mechanism that keeps abstractions honest.

**ADLC** — the eight-stage agent development lifecycle with role-gated reviews
(ADR-0009); mirrored in this repo by CODEOWNERS gates.

## Naming collisions (read this if you know Pydantic AI)

Pydantic AI ships a capability library called **"Harness"** and calls its framework
objects **"capabilities."** In this project, **the Harness** is our governed runtime
and **capability packs** are our product-knowledge bundles — realized *as* one or more
Pydantic AI capability objects by the adapter. When ambiguity is possible, write
"Pydantic AI Harness" / "framework capability" for theirs.

**"Harness" has a third sense inside this repository**, and it is the one most likely to
mislead: `tests/harness/` is the test-double package. So the word can mean the product,
their capability library, or our test fixtures.

**And a fourth, newer sense: `pydantic-ai-harness` is now a PyPI package name** — their
capability library shipped as a distribution, adjacent to the primary adapter this project
binds through. It is where `DynamicWorkflow` lives
(`pydantic_ai_harness.experimental.dynamic_workflow`). Write the package name in full and
never shorten it to "harness"; the three senses above are unchanged.

The distinction is not pedantic — it decides which layer holds a credential. One process
runs inside the Nomad allocation and contains three layers:

```text
Nomad allocation
└── container
    └── ONE process — "the Harness"
        ├── harness core      ← authenticates to Vault, records run state
        ├── adapter           ← maps the framework's concepts onto core
        └── agent (framework) ← chooses tools; holds no credential, touches no store
```

An agent is not a harness. Reasoning about credentials with the layers collapsed is how
you end up believing the agent can reach its own state store — which it cannot, and must
not.
