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

**Surface** (or **transport**) — one of exactly three northbound client entry points:
MCP server, REST API, portal/web UI. All are thin clients of one authorization core with
conformance-asserted parity (ADR-0033). ADR-0033 enumerated a fourth, a CLI; it was never
built and [ADR-0060](adr/0060-three-transports-the-cli-is-withdrawn.md) withdrew it. Adding a
fourth still requires an ADR — three is a ceiling, not a floor.

**Disclosure posture** — whether a run presented every tool's schema up front (`eager`),
withheld them until the model searched (`deferred`), or asked for deferral and could not get
it (`eager_fallback`). A property *of a run*, recorded on its start record rather than
inferred — a run believed to be deferring when it is not is the unstated posture this
platform refuses elsewhere (ADR-0040, 036).

**Discovery** — a model searching for a tool it was not shown, and what that search matched.
Recorded as an observation and **never refusable**: disclosure changes what a model knows
about, never what it may do (ADR-0061). Distinct from a tool call in the trail, so "looked
for a way to delete a bucket" cannot read as "tried to delete a bucket".

**Code mode** — a model writing a program that calls tools, rather than emitting one
structured call per turn. Ships in the governed path **only** with verified per-call hook
parity; sandbox safety is not governance (ADR-0041). Entered through the registered
`run_program` tool, so submission is itself a governed call and the registry is the opt-in.

**Sandbox seam** — the platform-owned loop through which every call a model-written program
makes reaches `invoke_tool`. Owned by the platform rather than the runtime because the
runtime does not enforce which functions a program may call: it forwards every unresolved
name to the host, so the host's handler is the security boundary (036, FR-014a).

**Intake gauntlet** — the staged pipeline that analyses an adopted skill's upstream change
before a person reads it: poll, diff, adversarial read, differential detonation, evidence
package. It decides what a reviewer reads and **never whether a skill promotes** (ADR-0053).

**Detonation range** — an operated component with no authority source at all and no route to
any real estate, seeded with canaries, where a presumed-hostile candidate is executed so its
behaviour can be compared with the pinned version's. Deliberately *not* the development
identity fake, which stays test-only (037).

**Canary** — planted material whose appearance anywhere outside the range is proof of
exfiltration. Records carry a canary's **identifier and never its value**: a trail that quoted
canaries would be the exfiltration channel it exists to detect.

**Analysis verdict** — `clean` / `flagged` / `inconclusive`. May block a candidate; **can
never approve one** — there is no such value, so the type cannot express an approval
(ADR-0043).

**Intake seed set** — human-labelled hostile *and benign* cases the analyzer is qualified
against, with a floor that fails rather than warns. The benign clause is what keeps "flag
everything" from qualifying (037, ADR-0052's mechanism).

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

**Effective authority** — user ∩ agent ceiling ∩ task scope ∩ policy. Manufactured per task
from an attested workload identity, bounded by a short lifetime rather than by a per-task
exchange: for read access the ceiling *is* the task scope, deliberately (ADR-0057). An agent
can never exceed the human it acts for.

**Rich authorization request (RAR)** — RFC 9396's `authorization_details`, which the
control-plane Vault **consumes and enforces** against a ceiling. It does not issue them:
Vault is an OAuth *resource server*, and the token must be minted elsewhere (ADR-0056). The
mechanism is held for write and act scopes; read scopes do not use it.

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
adopted from upstream skill repositories with overlays authored here (ADR-0004). Delivered
into a phase's instruction by its **skill binding**, and digest-verified again at that
moment — a skill nothing binds is governed but never executed.

**Skill binding** — the declaration, in a pack manifest, of *which phases receive a skill*
(`phases` on `[[skills]]`, 051). A skill with no binding is adopted, pinned and delivered
nowhere — a legitimate staged-adoption state that the run record keeps distinguishable from
delivery. No platform source names a skill or a binding: adding one is a `pack.toml` edit
and nothing else (ADR-0003). Where a bound skill and the phase instruction differ on a
concrete rule, the instruction governs, and the phase file says so.

**Unsatisfiable recommendation** — a step adopted content recommends that **no registry tool
can perform**, declared per skill in the manifest and stated in the pull request so the work
left to a person is named rather than discovered (051, ADR-0038). Scoped to the *registry*,
not the repository: the eval lane runs `terraform validate`, but no tool lets an authoring
agent run it on the branch it is proposing. A declaration naming a capability the registry
*does* offer fails pack loading, and a declaration whose skill has been bumped without it
being re-examined fails too — the pull request derives from the declaration and never from
the skill's bytes, so one that lags the content understates what remains to be done.

**Pack phase AGENTS.md** — the executed Build instruction for one pack × one phase
(`packs/<pack>/agents/<phase>/AGENTS.md`, pinned by `[[agents]]` in `pack.toml`). Distinct
from the repository-root contributor **AGENTS.md**, which is human/agent contributor
guidance for this codebase and is never a Build phase instruction (049, ADR-0030).
Unpromoted drafts live under `evals/prompt-tune/candidates/` and are never executed.

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

**Choice** — what a model named as the next tool at a step, recorded in the trail as a
`tool_chosen` event whether or not it was permitted (020). A choice is not a permission
decision: it says who named a tool and why it was on the table, while `pre_decision` says
what governance decided about it. The two are separate events on purpose — a reader must be
able to tell a *chosen* tool from a *scheduled* one, and a refused choice never opens a tool
bracket, so it would otherwise have nowhere to live.

**Chooser** — the seam a model provider or a recording satisfies: given the task, the tools
a definition permits, and any refusals already made at this step, it returns a tool name or
nothing. It never decides permission — the name it returns goes to `invoke_tool`, the same
governed entry a scripted name went to. Substitution happens where the **binding map**
resolves a model, never at the run loop, so every line between "the run needs a choice" and
"a choice came back" is production code in both lanes.

**Re-choice bound** — how many times a model may name a tool at one step before the run ends
terminally (020, FR-004b). Refusals are returned to the model as context, so governance is a
signal and not only a wall; the bound is what keeps that from becoming a suggestion an agent
grinds against. **Per step, not per run** — a run needing several tools must not inherit a
smaller budget because an earlier step took two attempts.

**RunReport** — a typed account of one run, **compiled on demand from its records and never
stored** (ADR-0018, 021). Every field traces to evidence; anything unsupportable carries a status
saying so rather than being omitted. *Reports are presentation; attestation rests on records* —
nothing in the platform may read a report to decide anything, and a report carries no part of a
run's **result**, which is scoped to the subject who started it rather than to the tenant.

**Claim** — one statement in a report, with the records it cites and how well they support it.
Seven statuses, of which five **partition** every claim about an effect: observed, contradicted,
and three distinct reasons for unverified. **No effect is ever asserted from the record alone** —
what a run records is that a tool was *allowed*, which is not the claim that it *happened*.

**Material event** — something in a run a faithful report must mention: a denial, an executed
effect, a terminal state. What the **report-fidelity** corpus labels, and what precision and
recall are measured against.

**Observation** — what a run learned by asking a product whether its effect landed, recorded as
evidence before the run reaches a terminal state. **Made by the allocation, never by a report**:
an observer reads under ambient identity, so at report time it would run under the surface's
authority — an agent never exceeds its human, and a report must not exceed its reader. An
observation is therefore a fact about run-end, not about the product now.

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

**Audit egress** — shipping the trail to a **destination** the platform's own credentials
cannot alter (ADR-0055). Not a backup: a copy the writer can rewrite detects nothing. The
trust boundary is **administrative, not topological** — an organization-operated collector
on the same machine satisfies it; object storage the enclave's own role can write does not.

**Second copy / destination** — the store the trail is shipped to, holding full chain
entries (so it verifies on its own contents) and the platform's own **head observations**
(so a consistent truncation of the first copy contradicts something). Its credential grants
the platform `INSERT` and `SELECT` and nothing else.

**Reconciliation** — the named operation that compares the two copies and reports
divergence by stream and sequence, never by content. Runs through the governed read path
and is itself audited, because reading evidence is audited. It reports that the copies
**differ**, never which one is honest — an attacker holding both administrative domains
defeats it, and the record says so.

**Separation probe** — the platform attempting to `UPDATE` and `DELETE` a shipped record
and requiring both to be refused. `verified` only ever follows a refusal actually observed;
a destination that cannot be probed is `unverified`, never assumed sound. This exists
because "the collector is append-only" is otherwise an assertion in a config file.

**Shipping lag window** — the entries written to the first copy and not yet confirmed at
the second. A **security** measure, not an ops one: it is exactly the set that exists in one
place, so a rising backlog is a widening interval in which a local rewrite would leave no
trace anywhere.

**Tamper-evidence posture** — `in_force`, `unverified`, `non_compliant`, or `absent`. Only
the first claims protection, and only a passing probe produces it. An estate with no second
copy reports `absent` — stated, never defaulted to something that reads as protected.

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


## Read record

Evidence that someone was **shown** something about a run or a thread — caller, tenant, what,
when, and the correlation id of the thing read. **Never the content.**

Introduced by 022, after nine of seventeen operations were measured returning records and
writing nothing while both surfaces told every connecting client that every operation was
recorded. A read record answers the question an auditor asks *second*: not "what happened" but
"who saw it".

Distinct from an **evidence read**, which is a read of the audit plane itself (ADR-0035). Both
are recorded; they live in different streams because a deliberate review and an idle editor's
`list_runs` polling have profiles too different to share one chain.

## record-access stream

`record-access:{tenant_id}` — one hash-chained stream per tenant, **stable across reads**, where
read records land. Stable rather than per-read: a fresh correlation id each time would make every
record a chain of one, linked to nothing and removable without trace.

**Never the chain of the thing read.** A read record refers to a run by correlation id and is
never appended to that run's chain, because `RunReport` compiles from that chain — a read
appended there would put "who read this run" inside the report of that run, including reads of
the report, growing every time anyone looked.

## Audit disposition

A declared property of an operation: whether it records, and under which rule. Lives on the
operation itself as a required field with no default, so an operation added without deciding is a
construction error rather than a missed edit to a list someone has to remember.

**The rule**: an operation that touches a **run or a thread** records; one that touches neither
does not. Runs and threads are records of *activity*. Agent definitions are *configuration* —
reading one discloses how the platform is set up, not what anyone did with it.

`records_elsewhere` must **name where**. That requirement earned itself immediately: an early
draft of 022 classified `stop_run` that way, and applying the rule revealed there was no where.
It wrote nothing at all.

## Answer

What the platform returns to a question about the guidance corpus: claims, each carrying citations
that resolve, or a **decline**. Two dispositions and no third — a provider failure is not an answer
and does not arrive in this shape, because a reader cannot tell *"the corpus does not say"* from
*"we could not reach the model"*, and those send them to different people.

**Never persisted.** Like a `RunReport`, it has no identity between requests.

## Citation

A pointer from a claim to the section supporting it — a document and an anchor, resolved against
the pinned corpus **before the answer ships**.

**An unresolvable citation is worse than no citation.** It reads as evidence, and a reader who
follows it and finds nothing has been told something false about what this platform knows. So a
claim whose citation does not resolve is dropped, and an answer with nothing left is a decline.

## Corpus pin

The identity of the guidance content an answer was produced from — a SHA-256 of each upstream
document, recorded in `corpus/manifest.json`.

**A digest rather than a version, because the corpus has no version metadata anywhere.** Change can
only be detected by content. The digest also does something a copy cannot: a vendored copy drifts
from upstream silently, while a digest mismatch is loud.

## Decline

Saying the corpus does not support an answer. **A first-class outcome, not an error** — the
required behaviour rather than the polite one, since an answer that cannot be traced is the failure
this platform is built against.

## Estate reference

A pointer from a claim in an estate answer to the audit record supporting it — an entry hash,
resolved **against the asker's own scoped read** rather than against the trail.

**That distinction is the whole bound.** "Exists in the trail" would let an answer cite a record
the asker was never entitled to see, and the citation would read as evidence. Resolving against
what they were actually shown is what makes it structural: nothing outside scope enters the path,
so no answer can carry its shape — including by implication, counts, or absences.

Same rule as a [citation](#citation): one that does not resolve drops its claim, and an answer
with nothing left is a [decline](#decline).

## Route

Which source a question needs: **guidance** (the pinned corpus), **estate** (the tenant's own
records), or **neither**.

Asking happens in one place, so the platform decides rather than making the caller declare it.
Deterministic — no model, no clock, no state — because a model router would put Principle VIII's
gates on routing and have to be scored against recordings, which is the defect this lineage keeps
closing. **`neither` is a real answer**: a router that always returned a source would answer
questions from material that was never about them.

Ties break toward estate, because that misroute declines visibly and gets rephrased, while the
other returns a plausible answer from the wrong source and nobody finds out.

## Scope

What an asker may see: their tenant, and the audit event types their **roles** map to.

Computed from the authenticated subject, never accepted from the request — a caller-supplied scope
is a request to widen. It **narrows the query** rather than filtering results, so out-of-scope
records are never read at all and the access record shows what was actually asked for.

**Empty refuses.** A subject whose roles map to nothing is refused before any read happens, so the
refusal leaves no access record — there was no access. Empty never means "everything".

## Propose

The portal (and matching API/MCP) surface where a person pastes a **repository URL** and a
task; the platform runs ordered phases (Research → Plan → Write → Judge → Propose) and opens
a pull request. Distinct from **Ask** (answers, never acts) and from **Run**’s agent picker.
See `specs/047-propose-chat/`.

## Ask binding

The operator-authored record naming, **per source**, which qualified cell an ask may use. Lives in
the trust fabric beside the [ceiling](#ceiling) and the Qualified Model Matrix; read-only to the
platform; **absent means refuse**.

**A run binds through its agent definition. An ask has neither a run nor a definition**, which is
why this record exists rather than reusing that mechanism. Deployment configuration was rejected
deliberately: *where* a model is reachable from is assembly, *which* model is permitted is
governance, and a binding in a jobspec would make Principle VIII configurable by whoever deploys.

Per-source because the two halves are different work — an operator can qualify a model to
summarise a tenant's records without licensing it to cite documentation.

## Cell disposition

What the ask record says about **how the authorising cell was resolved**: `pinned`,
`fallback:<reason>`, `refused:<reason>`, or `not_applicable`.

It describes the resolution outcome **and only that**. A refusal that happens *after* resolution
succeeded — an empty [scope](#scope), an unreachable provider — keeps `pinned` or `fallback`,
because the record's `disposition` field already says the ask failed later, and overwriting the
resolution outcome would erase the fact that governance passed.

`not_applicable` is the unroutable decline: no source was consulted, so no cell question arose.

## Model credential

The static API key a model vendor requires, held **once, in the trust store**, at
`model-credentials/<vendor>`. Operator-written, Control-Group-governed in production posture,
rotated in place. The platform reads; it never writes.

**The second of Principle IV's two named standing-credential exceptions** (ADR-0058, constitution
v1.4.0). A model vendor validates no workload identity — there is no audience to present and no
token to exchange — so [ADR-0044](adr/0044-authz-doctrine-and-credential-translation.md)'s
federate-or-broker rule routes it to the broker branch.

**Delivered, not derived.** Vault mints lesser material for products with a credential API; a
vendor key has none, so there is nothing to derive from. What makes this safe is **lifetime**: it is
obtained at task start under the reading workload's own attested identity, held in process for
exactly one task, and never persisted — not to a checkpoint, a log, the trail, or model context.
Two tasks are two reads.

**Revocation is a store operation.** Delete or rotate the record and the next task's fetch refuses,
with no restart. A task already in flight completes on the authority it holds, like every other
per-task grant.

Distinct from [brokered material](#brokered-material), which is the *derived*, lesser credential a
product with a credential API can mint. Naming both "brokered" would hide the property that makes
one need governance where the other needs only scope.

## Model authority

What the ask record carries to say **how a model call was permitted**:
`vault:model-credentials/<vendor>@v<version>` — a location and a rotation generation, **never a
value and never a hash of one**. A hash of a low-entropy-format secret is an oracle.

The version is the whole point. It makes *was this call made before the leak or after the
rotation* answerable from the record alone, which a bare path could not.

Empty on every refusal that precedes the fetch. An ask refused for an unqualified cell never
obtained a credential, and a reference there would claim an authority nobody exercised.

Sits beside [cell disposition](#cell-disposition), which says *whether* the model was allowed to
answer. Together they keep three failures apart: the cell was not qualified, the credential could
not be obtained, or the vendor did not answer — three failures, three people to go to.

## Brokered material

The **derived, lesser** credential the platform obtains on a caller's behalf for a product that
exposes a credential API — a scoped database role, a short-lived certificate. Compensated by
scope: what is handed over is narrower than what the broker holds.

Contrast [model credential](#model-credential), which is **shared-grain**: the vendor offers no way
to derive anything lesser, so the compensation is lifetime and governance instead of scope. The
protocol for one deliberately does not cover the other.

As of 027 the model broker is the platform's **first working broker**; `BrokeredMaterialSource` in
`core/authority/entitlements.py` remains a Protocol nothing implements, and the TFE path will
inherit the shape built here rather than the other way round.
