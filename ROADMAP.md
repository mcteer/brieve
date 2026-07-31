# Roadmap

What ships in what order, and why that order. Derived from the decision record
([`docs/adr/`](docs/adr/)) and the constitution's Quality Gates — not a separate plan.

**This file is guidance, not governance.** Where it conflicts with an Accepted ADR or the
constitution, those win and this file is corrected. Its job is to stop feature sequencing from
being re-derived at the start of every spec.

## How to use it

- **Starting a feature?** Take the top of [Next](#next). If you take something else, say why in
  the spec's Assumptions.
- **Deferring something in a spec?** Every "out of scope" line is a promise. Add it here, or to
  [Demand-driven](#demand-driven--trigger-gated) if it should never be scheduled by default.
- **Landing a feature?** Move it to [Shipped](#shipped), and move any Quality Gate row it
  attached out of [Owed gate rows](#owed-quality-gate-rows). ADR-0047 makes those rows binding
  the moment their feature exists.

## Shipped

| # | Feature | ADRs realized | Gate rows attached |
| --- | --- | --- | --- |
| 001 | Dev toolchain | ADR-0007, ADR-0028 | — |
| 002 | Governed core | ADR-0006, ADR-0009, ADR-0020, ADR-0037 | — |
| 003 | Per-task authority | ADR-0015, ADR-0026 (partial), ADR-0042, ADR-0044 | — |
| 004 | Primary adapter | ADR-0001, ADR-0017, ADR-0019, ADR-0047 | Governance-ordering, fail-closed, governed entry |
| 005 | Durable execution | ADR-0024, ADR-0026, ADR-0048, ADR-0018 (consumes) | All seven durability rows |
| 006 | Deployment module tree | ADR-0025, ADR-0048, ADR-0015, ADR-0007 | — (infrastructure; the durability rows now run under an attested identity) |
| 007 | Control Groups | ADR-0016, ADR-0015, ADR-0048 | — (no new blocking row; component tests against the real Vault) |
| 008 | Northbound API | ADR-0033 (first transport), ADR-0035, ADR-0016 (consumes), ADR-0015 | Seventeen API rows, nine needing the enclave. **Parity deliberately not claimed** — one transport is nothing to compare |
| 009 | MCP surface | ADR-0033 (second transport), ADR-0049 (**resolved by building it**), ADR-0035, ADR-0048 | Fifteen MCP rows. **Surface parity claimed** — the row 008 could not assert, now that there are two transports to compare |
| 010 | Production identity fabric | ADR-0015 (**first feature that reads the registry at runtime**), ADR-0050 (new), ADR-0044 (mirroring seam; credential translation still deferred), ADR-0048 | Identity rows against the live trust fabric, in-allocation. **The gap every prior feature rested on** |
| 011 | Northbound API operations | ADR-0033 (the parity row grows with the catalogue), ADR-0034 (the portal's precondition), ADR-0035, ADR-0016, ADR-0049 (stop as withdrawal, not the pause it removed) | Sixteen operation rows, plus verdict parity over the grown catalogue |
| 012 | The conversational portal | ADR-0034 (**built**), ADR-0051 (new — a turn is evidence, a thread is a view), ADR-0033 (the portal is a consumer, so parity still binds one pair), ADR-0032 (the ungoverned loop, made structurally impossible), ADR-0049 (no pause, asserted as an absence) | Eight containment rows, eight accessibility rows, and the API's first deployment |
| 013 | Capability packs and eval gates | ADR-0004, ADR-0022, ADR-0030, ADR-0031, ADR-0039, ADR-0045 (**built** — the toolset line 008–012 signposted, replaced by product knowledge a definition opts into), ADR-0018 (consumed) | Four of five eval gates blocking against both shipped packs; the fifth (report fidelity) an explicit skip citing ADR-0018, per ADR-0047 |
| 014 | Dispatched resume | ADR-0026 (**the durable half built** — `resume_run` gets its first `src/` caller), ADR-0048 (a resume is a new allocation with a new attested identity), ADR-0049 (grant expiry stops terminally), ADR-0047 (FR-020 re-scoping — 005's rows now asserted through a dispatch) | Ten dispatch-level rows in the durability lane. **Closed ROADMAP gap 0a**, and uncovered four latent defects — the missing grant store, an index with no writer, a sweeper that had never dispatched since 009, an observer that could not be called |
| 015 | Audit egress for tamper-evidence | ADR-0055 (**built** — the rule was settled and nothing existed), ADR-0020 (unchanged — this adds a NEAR destination, not a far one), ADR-0035 (reconciliation runs through the governed read path and is itself audited) | Thirteen rows against a live second store under the collector administrator's credential. **Closed ROADMAP gap 0**, the most consequential gap on this page. Found a reconciler that compared the two copies' hash *claims* rather than their contents — an administrator who rewrote a payload and left `entry_hash` alone passed the comparison |
| — | Federated sign-in and the surface that serves it | ADR-0033 (the API's first *working* deployment), ADR-0016 (claim mappings become readable, so the gate has an effect), ADR-0048 (the API gets its own attested identity), ADR-0057 (the phrasing it left owed, amended) | No new gate class. Three component suites and one conformance row on the real Vault path, plus a unit gate over the API assembly. **Not a numbered feature** — direct work off 016's parking, PRs #76–#80, recorded here because the ROADMAP's own rule is that deferrals and landings are written down where the next planner will see them |
| 017 | Deployment lane | ADR-0047 (**the inverse case it governs** — gates that PASSED while the guarantee was absent, because they asserted about the wrong object), ADR-0048 (a surface's identity is attested, and an assembly asking for the wrong role fails at login), ADR-0033, ADR-0025 | Twenty-one rows against the served surfaces, in a lane that stands them up. **Closed ROADMAP gap 0d.** A gate class no prior lane could run: every other asserts about a process the test constructs, this about the one a deployment constructs. Eight analysis passes before implementation, six of which found something in the surfaces' lifecycle; running it then found two more |

## In progress

*Nothing in progress.*

**016 task-scoped authority is PARKED** (`specs/016-task-scoped-authority`, branch
`feat/016-task-scoped-authority`, 19 of 51 tasks). Specified, planned, and the substrate built
and demonstrated end to end — then stopped, because implementation established that the
narrowing it delivers is one the workload does not want.

These agents are HashiCorp experts who read widely before acting: skills, HVDs, internal
policy, prior art. Breadth of read is how the output gets informed, and an agent denied
context does not fail loudly — it advises badly. Meanwhile the property the narrowing was
meant to buy is already held: authority is manufactured per allocation from an attested
identity and expires in an hour.

[ADR-0057](docs/adr/0057-context-hungry-agents-want-breadth-not-narrower-reads.md) records the
decision and the three triggers for re-opening it. The research — Vault is the resource server
and cannot perform the exchange, the entity-alias binding, the `jti` trap — is kept in
`specs/016-task-scoped-authority/research.md`.

> **A feature has no number until `/speckit-specify` creates its directory.** Refer to unstarted
> work by name. Guessing the next number reads as a fact, propagates into merged documents, and
> is wrong the moment anything is specified out of order.
>
> **Numbers are identifiers, not sequence.** 005 was assigned to durable execution before the
> local environment was understood to precede it — and then 005 shipped first anyway, because
> the blocking part of the environment turned out to be one Makefile target. The order of work
> here does not match numeric order and is not meant to. Renaming a merged spec directory would
> churn every reference to it for no gain.

> **A feature has no number until `/speckit-specify` creates its directory.** Refer to unstarted
> work by name. Guessing the next number reads as a fact, propagates into merged documents, and
> is wrong the moment anything is specified out of order.
>
> **Numbers are identifiers, not sequence.** 005 was assigned to durable execution before the
> local environment was understood to precede it — and then 005 shipped first anyway, because
> the blocking part of the environment turned out to be one Makefile target. The order of work
> here does not match numeric order and is not meant to. Renaming a merged spec directory would
> churn every reference to it for no gain.

## Next

Ordered by dependency first, then by which owed gate row it closes. Each entry names what it
unblocks — that is the argument for its position, and the thing to challenge if you disagree.

### Northbound surfaces — split into four (ADR-0033, ADR-0034, ADR-0035)

**One feature per transport, not one feature for four.** ADR-0033 requires all four to yield the
same verdict and equivalent audit events, and that parity is asserted *between* them — but
building four surfaces in one pass means getting parity right across four things that are all
still moving. Splitting lets each land against a settled core.

**The API goes first**, because the other three consume it rather than reimplementing the
authorization path. A CLI that talks to the core directly is a second authorization path
wearing a different name.

| # | Transport | Notes |
| --- | --- | --- |
| 008 | **API** | ✅ Shipped. The surface the others consume. Carries the audit plane as a governed read path |
| 009 | **MCP** | ✅ Shipped. The persistent service coding IDEs talk to. Carries the dependency health checks and the resume sweeper decided in ADR-0049 — both needed a long-lived home, and this is it — plus the continuous evidence-stream verification 008 deferred here, and the second CI lane |
| — | CLI | **Tabled** (2026-07-28) — see below |
| 012 | **Portal** | ✅ Shipped. Threads, the client, and the API's first actual deployment — 008 built `create_app` and nothing had ever served it. **Answering is not here**: estate-state and grounded guidance need an eval-gated model binding, and follow capability packs |

**Gate row, no longer owed:** surface parity. It stayed owed through 008 because parity
cannot be asserted against a single surface. **009 amended the row and satisfied the amended
version** — it was worded "across all four transports", which two cannot satisfy, so it now
binds across every pair of implemented transports (constitution v1.2.0). That makes it bind
at each transport rather than only at the fourth, which is the difference between catching
divergence when it starts and catching it long after.

**The CLI is tabled, and ADR-0033 is not withdrawn.** API, MCP, and the portal cover
substantially every persona: services and automation reach the API, editors reach MCP, and
people who do not live in an editor reach the portal (ADR-0034). A CLI would be a fourth
way to reach the same four operations, for an audience already served by two of them.

Tabled rather than declined — no ADR is superseded and nothing is deleted. If a demand
appears that the other three genuinely cannot meet, ADR-0033 still describes how a CLI
would work, down to the device authorization grant it would use.

**What this costs, stated because it is easy to miss:** ADR-0033 makes parity a *test*
rather than an intention, and a transport that is never built is a pair the test never
covers. That is fine only because 009 amended the row to bind across every pair of
**implemented** transports — had it stayed worded "across all four", tabling one would have
left the row permanently unsatisfiable, and this decision would have been a constitutional
change wearing the clothes of a scheduling one.

**Why here:** the first features that ship something a user touches directly. They need the
authorization core (002/003) and the approval gate (007) settled behind them; attempting them
earlier means building transports over guarantees still in motion.

### Portal answering — estate-state and grounded guidance (ADR-0034, ADR-0039)

**Unnumbered, and after capability packs**, which is not a preference but a dependency:
ADR-0039 makes an `ask` binding inexpressible without a green Qualified Model Matrix cell,
and the eval gates that green a cell are that feature's. 012 split these out on exactly
that evidence — the platform installs zero model providers on purpose, so these would be
its first model call.

What it inherits, so it does not rediscover it: the corpus is settled (HashiCorp Validated
Patterns — 33 documents, stable per-section anchors, **no version metadata anywhere**, so
change detection must be content-based), and ADR-0039 has already decided the rule it will
be tempted to bend — *ask answers, it never acts*.

### Capability packs and eval gates (ADR-0004, ADR-0022, ADR-0030, ADR-0031, ADR-0039, ADR-0045)

> Previously headed "009", which guessed a number this file's own rule says not to guess —
> and it was wrong the moment MCP was specified first. Unnumbered until its directory exists.

Packs, prompts, and skills as pinned, eval-gated artifacts; the Qualified Model Matrix; per-role
model bindings; competency tiers.

**Why here:** brings Principle VIII online, which no feature has needed yet — the eval-gate
machinery does not exist. It depends on nothing in 007/008 strictly, so it can move earlier if
content work becomes the priority; it sits here because a pack with no surface to invoke it and
no approval path is hard to evaluate end to end.

**Owed gate rows:** all Eval gates (must-deny safety, must-decline scope, citation accuracy,
estate-state fixtures, report fidelity).

### Automated skill intake — the supply-chain sentinel (ADR-0053)

**Unnumbered, per this file's own rule** — no directory exists and nothing is specified.
[ADR-0053](docs/adr/0053-automated-skill-intake-gauntlet.md) is **Proposed**.

Automates the intake gauntlet ADR-0004 requires, so analysis starts when upstream publishes
rather than when a person notices, and the reviewer reads evidence instead of raw upstream
text. A poller dispatches a narrow-ceilinged analysis agent in the hardened isolation tier; a
textual diff and an automated adversarial read run first; a clean static read proceeds to
differential detonation against the golden-task corpus in a canary-seeded range, with the
observer and the specimen as separate workload identities. The evidence package attaches to
the version-bump pull request.

**Why beside capability packs:** skill adoption ships there, so intake has nothing to gate
until packs exist. 013 built the promotion path — provenance, injection lens, eval — with the
lens pattern-based and the review human. This is what feeds it.

**The human gate is unchanged.** The pipeline raises the review's floor and never replaces
its ceiling; the analyzer's verdict may block promotion and never satisfies the approval.

**Owed before it can be specified:** the analyzer is itself eval-gated executed content and
needs its own eval class — seeded-hostile corpus, must-flag rate, false-positive budget,
calibration for lenient drift. And the honest limit stays in the record: detonation catches
only what the corpus provokes, so the runtime governance floor remains the backstop.

### Deferred disclosure and code mode (ADR-0040, ADR-0041)

> Previously headed "010", which guessed a number this file's own rule says not to guess —
> and it was wrong the moment the identity fabric was specified first. Unnumbered until its
> directory exists.

Productizes deferred tool/capability disclosure, and ships code mode — but only with verified
per-call hook parity, which ADR-0041 makes an unconditional gate rather than a default.

**Now covers model-written orchestration of both tools and sub-agents**
([ADR-0054](docs/adr/0054-model-written-orchestration-parity.md), **Proposed**). Two upstream
projects bear on this: Monty, whose external-function seam is the sandbox's only exit and whose
`start()`/`resume()` pauses *at* that seam — which makes ADR-0041's parity condition
structurally satisfiable rather than hoped-for — and DynamicWorkflow, where each sub-agent is
an async function in a model-written script and the whole tree runs in one tool call.

ADR-0054's addition is that **a sub-agent invocation is a delegation, not a tool call**, and
binds host-side to the governed delegation path: act-chain narrowing under the sub-agent's own
registered ceiling, the roster drawn from the registry so the model composes the call graph and
never the agent set, `reveal()` as disclosure economics for agents, `max_agent_calls` as a
host-enforced bound, and the model-written script itself as a first-class audit artifact.

**Why here:** all of it is efficiency gated on proving governance survives it. Neither disclosure
nor code mode is worth doing before there is enough tool surface for the efficiency to matter,
and orchestration is worth less still before there are packs to orchestrate.

**Track, do not build on.** Both upstream projects are outside their own stability commitments
— Monty's banner says so and DynamicWorkflow's import path carries an `experimental` segment.
Watch signals are in ADR-0054; the one that matters most here is DynamicWorkflow's
**durable-workflows extension**, because workflow state entering checkpoints invokes the
credential-free-checkpoint condition (ADR-0026).

**Owed gate rows:** tool-call parity under deferred disclosure; and, if orchestration is
adopted, per-delegation parity plus the two break fixtures ADR-0054 names — a host handler that
bypasses `invoke_tool` must fail, and an unregistered roster entry must refuse at construction.

### Multi-tenancy (ADR-0046)

One platform, isolated tenants, using the products' own isolation primitives.

**Unnumbered, per this file's own rule** — it had been headed `011`, which 011 then went to. Guessing a number reads as a fact and is wrong the moment anything is specified out of order, which is exactly what happened.

**Why last of the scheduled set:** it multiplies every guarantee above it. Isolating tenants
before the things being isolated are stable means doing the work twice.

## Demand-driven / trigger-gated

Deliberately unscheduled. Each needs a recorded trigger before it enters [Next](#next) — that is
the decision, not an omission.

| Item | ADR | Trigger |
| --- | --- | --- |
| CLI transport | ADR-0033 | **Demand.** API, MCP, and the portal cover the personas; a CLI would be a fourth route to the same operations for an audience two of them already serve. ADR-0033 still specifies it — device authorization grant, same authorization core — so this is a scheduling decision, not a design one. Tabled 2026-07-28 |
| Second framework adapter (LangGraph) | ADR-0017 | Demand. The ADR makes it explicitly demand-driven; 004's FR-014 forbids shipping it speculatively |
| Dedicated workflow-engine durability provider | ADR-0024, ADR-0028 | A named trigger: scale, an existing deployment, or a requirement the library provider cannot meet |
| Wire-level guardrail (second protection layer) | ADR-0014 | Optional by design; in-process hooks are the primary layer |
| Retrieval | ADR-0029 | Runs in the Postgres a deployment already has — needs that Postgres to exist first |
| Row-level security on the evidence store | 008 | The tenant boundary on evidence reads is enforced by the application, not the database. `exists_outside_tenant` shows why that matters: the SQL role can see that rows exist under another tenant even though no content crosses. Postgres RLS moves the enforcement a layer down and is the right eventual home |
| RFC 8693 + RAR authority manufacture | **Closed by [ADR-0057](docs/adr/0057-context-hungry-agents-want-breadth-not-narrower-reads.md)**, and not by building it | Principle IV describes manufacture as "attested workload identity → control-plane Vault → **RFC 8693 + RAR** against ceiling policies"; what runs is a JWT auth-method login. **ADR-0056 established the mechanism** by reading the substrate rather than inferring it — Vault is the RESOURCE SERVER and cannot perform the exchange, its OIDC token endpoint accepting `authorization_code` and nothing else. **ADR-0057 then established that the narrowing is not wanted here**: these agents read widely before acting, so breadth of read is how the output gets informed, and the property the narrowing was for — just-in-time, short-lived, attested — is already held. `task scope` is satisfied for reads by per-allocation manufacture with a bounded TTL. RAR remains the mechanism for WRITE and ACT scopes when those enter a ceiling. **Owed — discharged 2026-07-31 (#77)**: ADR-0048 carries an appended amendment with the Decision left in place, the glossary's "effective authority" is corrected and gains a RAR entry, and Principle IV describes attested manufacture bounded by a ceiling and a lifetime. Constitution 1.2.0 → 1.3.0, MINOR on the v1.2.0 ADR-0033 precedent — a correction, not a policy change |
| Brokered credential translation | ADR-0044 | Principle IV names the broker's rotated management token as **the platform's single permitted standing credential**, and the mechanism it exists for does not exist. Until 010 the branch wrote a placeholder string and returned `allow`; it now refuses `broker_not_implemented`, which makes the gap visible when a deployment configures a brokered product. The entitlement-mirroring check in front of it is real and enforced |
| `no_default_ceiling_policy` on registrations | ADR-0050 | Vault appends `default` and `default-ceiling` to every registration unless this is set, which nothing here has ever set — so the effective ceiling has never been the declared one. The added policies are benign; the point is that a difference existed where the mechanism's whole claim is that none does. Setting it changes the posture of every registration and deserves its own decision |
| Ceiling / policy jurisdiction coherence | ADR-0050 | Two records for one definition can disagree: an agent granted a tool whose secrets it cannot read, or the reverse. A consequence of ADR-0044's disjoint jurisdictions rather than a defect, and nothing reports it. A cross-check would be a rule duplicated across engines, which is what ADR-0044 forbids — so the fix is probably an operator-facing report, not a gate |
| Vertical policy/content profiles | ADR-0003 | Horizontal first. Profiles ship as policy and content, not as forks |

## Owed Quality Gate rows

The constitution names these as blocking for adapters and providers. Under ADR-0047 each binds
when its feature lands, and until then must be **absent or an explicit skip citing its deferring
ADR — never a passing stub.**

| Row | Attaches with | Status |
| --- | --- | --- |
| Governance-ordering, fail-closed, governed entry | 004 | ✅ In force |
| Durability scenarios (ADR-0024/0026, as amended by ADR-0049) | 005, amended by 009 | ✅ In force — all seven, both providers, under an attested identity. **Now run by CI** on same-repo pull requests: 009's enclave lane holds the licensed Vault as a repository secret, which a fork-originating run cannot read. Fork pull requests still fall to the agent harness per `AGENTS.md`. The grant-expiry row asserts *stopping* rather than parking — inverted by ADR-0049, not removed |
| Surface parity | 009 | ✅ **In force.** Amended, then satisfied. It read "across all four transports"; 009 has two, so claiming it would have asserted something untrue — the stub ADR-0047 forbids. 009 amends it to bind **incrementally**, across every pair of implemented transports, and satisfies it for the API/MCP pair. Better than claiming or deferring: the gate now binds at two, three, and four rather than catching nothing until the last transport lands, which is well after divergence would start. Compared against `specs/008-northbound-api/contracts/operations.snapshot.json` |
| Tool-call parity under deferred disclosure | Deferred-disclosure feature | Deferred — ADR-0040 |
| Eval gates (packs, models, policies) | 013 | ✅ **In force — four of five.** Must-deny, must-decline, citation accuracy, and estate-state run blocking against both shipped packs, scored on fixtures with a marked live lane behind a named runner. **Report fidelity stays owed** against ADR-0018: `RunReport` does not exist, and per ADR-0047 the row is an explicit skip citing its deferring record rather than a stub. The judge chain terminates at a human-labeled seed set (ADR-0052) |
| Registry isolation (control-plane write denials) | — | **Unassigned** — see gaps below |
| Accessibility (WCAG 2.2 AA, rendered interface) | 012 | ✅ **In force.** A gate class no prior lane could run: every other gate asserts something about a process, this one about a rendered page. Twenty-one rows: a vendored, pinned axe ruleset over every page state, **plus a keyboard-and-screen-reader harness** that walks the real tab order against visual position, reads the browser's own accessibility tree over CDP, measures focus indicators and target sizes, and re-renders under the reflow and text-spacing criteria. **No named runner is owed** — what was once a manual checklist runs in CI, and it found three defects on its first run. What stays outside a browser's reach (whether the words are good; any specific screen reader's behaviour) is recorded in the contract |

## Open records

One ADR remains **Proposed** and is expected to resolve rather than linger. Neither blocks the
sequence above, but a Proposed record that quietly becomes permanent is a failure of the process
([`docs/adr/README.md`](docs/adr/README.md)).

- **ADR-0011** — harness-first SDKs at the perimeter; awaiting the evidence ADR-0012 produces.
- **ADR-0012** — ✅ **Accepted 2026-07-29.** Harness-as-runtime leads. Decided on the platform's own construction rather than the early-adopter cohort the ADR named, because there is no cohort yet — recorded that way in the ADR's Resolution, since a record claiming evidence that never arrived is worse than one admitting its basis.

## Known gaps in the record

Found while deriving this file. None blocks work; all three make the record harder to reason
from, and each is worth its own small change.

### 0a. `resume_run` has no production caller — **CLOSED by 014, 2026-07-30**

**Found 2026-07-29 while tracing 013's dispatch path. Closed by
[`specs/014-dispatched-resume`](specs/014-dispatched-resume/).**

`resume_run` was invoked from tests and from nowhere in `src/`, so 005's conformance rows —
"a disrupted run resumes and completes", "re-observe, never re-execute" — were true of the
function and not of the dispatched path. The entrypoint ignored `RUN_STEP_INDEX`, called
`start_governed_run`, and began its loop at zero.

**Closed with evidence rather than with a wiring change.** All ten dispatch-level rows in
[`specs/014-dispatched-resume/contracts/conformance-resume.md`](specs/014-dispatched-resume/contracts/conformance-resume.md)
pass against the live enclave: a real allocation killed mid-flight by the scheduler resumes in
a second allocation and completes with exactly one execution per step, re-observation decides
both directions against real Vault with the shipped observer, a suspension names its product
and the sweeper revives it unaided, the revival budget is bounded and terminal, lapsed consent
stops the run, and fencing holds through a real overlap.

**Four defects it uncovered on the way**, each invisible for the same reason — the only thing
that would have exercised it was the caller that did not exist:

1. The `grants` table did not exist. `checkpoints.grant_id` had resolved to nothing since 005
   and carried the 15-minute credential id, so consent expiry was unevaluable.
2. `record_suspension` had no callers at all — the suspended-run index had a reader and no
   writer.
3. **The sweeper had never dispatched anything since 009**, reaching the scheduler on a
   loopback address that belongs to the container rather than the host.
4. `VaultWriteObserver` could not be called: it required an argument the `Observer` protocol
   does not pass, so every interrupted Vault write suspended its run rather than resolving.

### 0b. The collector credential was a hand-written password — **CLOSED by 015, 2026-07-30**

**Raised by Dan while reviewing 015, three times, because the first two answers were also
wrong.** The platform held `harness_shipper` as a fixed password written into a Vault KV path
by bring-up, where every other database credential it uses is Vault-managed. 015 defended this
with claims that had not been checked: that federation was unavailable across an
administrative boundary (backwards — federation is the mechanism *for* crossing one), that
removing the standing credential needed a second Vault, and that rotation needed bespoke
automation. None were true.

**Closed by onboarding the account as a ROOTLESS static role**
([`audit-egress.tf`](infra/modules/trust-fabric/audit-egress.tf)). `self_managed = true` means
Vault holds no privileged account at the collector: it connects *as* `harness_shipper` and
rotates that account's own password on a 24-hour period. The maximum privilege obtainable
through this Vault at the destination — by an operator with the root token, or by anyone who
compromises it entirely — is the shipper's own `INSERT`/`SELECT`. Seeding the collector's root
instead, which is how a database is normally registered, would have let whoever controls this
Vault define a role granting `UPDATE` on `shipped_entries`: exactly the tampering ADR-0055
exists to prevent. Rootless is not the convenient option, it is the one that survives the
threat model.

**The bootstrap password is a non-event**, which is the general principle worth keeping: Vault
rotates on import, so the seed in `roles.sql` stops authenticating the moment onboarding
succeeds, and the password in force afterwards is known to nothing but Vault. Same disposition
`rotate-root` gives the state store. A row asserts the seed is dead rather than trusting it.

**Three rows** in [`test_credential_rotates.py`](tests/conformance/evidence/test_credential_rotates.py):
the seeded password authenticates nothing; a forced rotation changes the credential and kills
the old one; and shipping survives a rotation because the shipper reads the current value
rather than caching one — a cached credential fails on a 24-hour cadence, looking like the
collector going down, days after anyone touched the code.

**The boundary never rested on password secrecy**, and this is what made the earlier reasoning
go wrong: it rests on the grant list. An administrator holding the password gains exactly what
the platform already legitimately has, and `probe()` goes on demonstrating `UPDATE`/`DELETE`
refused every pass. Conflating "who knows the password" with "what the account may do" is what
made a second trust store look load-bearing.

**ADR-0044's count stands at one.** There is no second standing credential.

### 0c. A kill between a step's result and its audit entry loses the entry — **CLOSED 2026-07-31**

**Found 2026-07-30 by 015's full gate run**, which failed `test_dispatched_resume`'s
exactly-once row with 399 outcomes for 400 steps. The run's data settled what happened: 400
intents, **400 results**, 399 `TOOL_OUTCOME` events. Every step's effect happened and was
durably recorded exactly once; one produced no audit entry.

**The window.** A step records its result and *then* audits `TOOL_OUTCOME`. A kill between
the two left an effect that happened, was recorded in `results`, and had no entry in the
trail — and the resume correctly did **not** re-execute it, because `closed_intents` saw the
result, so the entry was never written afterwards either.

**The ordering was never the bug.** Auditing first would be worse: a kill between the audit
and the result leaves a `TOOL_OUTCOME` for a step with no recorded result, the resume
re-executes it, and the side effect happens twice. Exactly-once is the more important of the
two properties and the current order is the right trade.

**Closed by recording the skip.** `STEP_REOBSERVED` names each step a resumed allocation did
not execute and why — `result_recorded`, `reobserved_complete`, or `below_checkpoint`. Those
are three genuinely different claims (the step's own record that it finished; a judgement
about an open bracket; a coarser backstop for steps that never bracketed), and collapsing
them to "skipped" would lose the difference an investigator is asking about. "Re-observe,
never re-execute" is now a statement in the trail rather than an inference from counts.

**What the conformance row asserts now**, having previously only bounded the hole at one:
between outcomes and re-observations, no step is silent. Deliberately not a partition — a
step the first allocation ran has an outcome *and* is re-observed by the resumed one, so the
records overlap by design and their counts do not sum to the run's length. An earlier draft
of the assertion claimed a partition and failed on a clean run, which is how the overlap got
noticed.

**Still true, and worth keeping visible**: `TOOL_OUTCOME` carries no step index, so the
reconciliation is by count and by the re-observations' named steps rather than by a per-step
join. Adding the index would make it exact and is a small change to the hooks engine's
payload — worth doing whenever that path is next open.

### 0d. No lane runs a served surface, so `build()` has never been executed by CI — **CLOSED by 017, 2026-07-31**

**Raised 2026-07-31, while wiring the API to a real identity provider.** The API job's
workload identity is `nomad_job_id = "api"`; `service.py` asked Vault for the default
`harness` role, whose bound claim is a different job. Every login was refused, the allocation
died in `audit_sink.migrate()`, and **the northbound surface had never served a request in a
deployed enclave.** It surfaced by running `portal-up` and reading the allocation logs, which
nothing in CI does.

The specific bug is fixed (#79). The gap is what let it live: **no lane executes
`service.build()`.** `make dev-up` brings up Vault, Nomad, Postgres, the mcp service and
agent-run; `portal-up` brings up the API and the portal and is never run by CI. Component
tests call `create_app` with doubles, so the assembly — the one code path with no coverage by
construction — is exercised by nothing.

That is the common cause behind a pattern this file has recorded five times under different
names: `resume_run` with no production caller (014), a sweeper that had not dispatched since
009, an observer the protocol could not call, an egress loader reading a `VAULT_TOKEN` no
allocation has (015), and claim mappings nothing read back (#78). Each was found separately
and fixed separately. **They are one absence seen five times**, and 015 already wrote the
answer for a single service in
[`test_the_service_ships.py`](tests/conformance/evidence/test_the_service_ships.py), whose
docstring counts four of them and names the shape: *"a capability that is correct, tested,
and wired to nothing."*

**The mitigation is a lane that stands the served surfaces up and puts a real request through
each.** Not a health check — a request that traverses the assembly, the attested identity, and
the trust fabric, so the row fails for the reason the deployment would. Precedent for the
shape exists twice: the mcp shipping row above, and 012's accessibility lane, which was also
a gate class no prior lane could run.

Open questions worth settling before building:

- **Whether it joins the enclave lane or becomes a third.** Registering these services at
  bring-up once cost the enclave lane ten minutes and left the conformance job unplaceable,
  which is why `portal-up` is separate — recorded in its own header. That constraint has not
  gone away.
- **What "answered" must mean.** A 401 from a surface that booted is a pass; a 401 from a
  surface that never read its configuration is indistinguishable at the socket. The row has to
  assert something only a correctly assembled process can produce.

**Closed by [`specs/017-deployment-lane`](specs/017-deployment-lane/).** `make conformance`
now ends by standing the API and the portal up and asserting each answers **as itself** — an
unauthenticated request returning the surface's own reason code, which a process that read no
configuration cannot produce. Twenty-one rows. The break was demonstrated rather than argued:
the API pointed at a nonexistent Vault role failed the lane, named the API, and printed
`role "no-such-role" could not be found`.

**What it does NOT close, stated because the entry above invites the wrong reading.** Four of
the five instances listed here were already covered — by 014's durability rows and 015's
shipping row, built for those features. This gate's own contribution is the fifth, the API's
start-up, plus making the other four's coverage *checkable* rather than incidental. The full
assessment is in the feature's conformance contract, including the rows it would not have
caught.

**Two defects were found by running it that eight analysis passes had not**: the failure path
reported "answered nothing" while the process's own error sat unread in the allocation's
stderr, and the wait stopped at *placed* rather than at *answering* — so rows failed against
surfaces that were merely young. Both are the shape this whole gap is about, arriving one
level up: a thing that looked right on paper and was wrong when run.

### 0. The audit trail is not shipped off-host, and hash-chaining only *detects* — **CLOSED by 015, 2026-07-30**

**Closed by [`specs/015-audit-egress`](specs/015-audit-egress/), which implements ADR-0055.**
Every entry and every stream head now ships to a second Postgres the platform holds an
append-only credential for and nothing more, and reconciliation is a named, scheduled,
audited operation on both transports. Thirteen rows in
[`contracts/conformance-egress.md`](specs/015-audit-egress/contracts/conformance-egress.md)
run against that store under the collector administrator's credential — including the
consistent truncation that defeats chain, grant, and local head together, and a real
outage that stops the collector's container mid-flight.

**Both open questions were answered in clarification rather than by whoever built it
first**, which is what ADR-0055 asked for: shipping is spooled (draining the entries
already written, so no spool table exists), and a failed *delivery* refuses nothing while
a failed *capture* still refuses the step.

**The claim does not grow.** This detects; it does not prevent. A single-domain compromise
now leaves evidence of itself, an attacker holding both domains still defeats it, and the
lag window — entries written but not yet confirmed at the second copy — is real, bounded by
the ship interval, and reported as a backlog anyone can watch. It also introduces the
platform's **second standing credential**, which ADR-0044 called a constitutional event;
that is named in ADR-0055's Notes and ADR-0044's count is not amended here.

The original entry follows, unedited.


**Raised by Dan, 2026-07-29, during 013's live gate run. The most consequential gap on this
page.** Now **decided** by [ADR-0055](docs/adr/0055-audit-egress-for-tamper-evidence.md)
(**Accepted**) — the rule is settled and nothing is built, so this stays a gap in the
*implementation* rather than in the record.

**One correction to how this entry was first written.** It framed off-host shipping as a
straightforward mitigation without citing
[ADR-0020](docs/adr/0020-otel-only-backends-at-the-collector.md), which already states that
**the audit plane never egresses by default** and that SIEM export is an explicit, configured
act. That is a deliberate posture for regulated estates, not an oversight — so the real
decision is a *tension* rather than a gap, and ADR-0055 is where it is resolved: the trust
boundary that matters is **administrative, not topological**, and a collector the organization
operates under administrators who are not the platform's satisfies tamper-evidence without
becoming the third-party egress ADR-0020's default guards against.

Everything downstream of the audit plane rests on evidence being trustworthy, and today the
whole of it lives in one Postgres this platform operates. The chain is honest about what it
gives: `audit_entries` is append-only *by grant* (the evidence role holds `SELECT` and nothing
on `audit_stream_heads`), and `audit_stream_heads` exists because a hash chain cannot detect
truncation — delete the newest three entries and `seq 0..N-4` verifies perfectly.

**But detection is not prevention, and both tables are in the same database.** An actor with
write access to that Postgres can rewrite entries *and* the head that would have exposed the
rewrite, consistently, and nothing anywhere disagrees. The property the platform claims —
evidence that cannot be mutated or masked — is currently enforced by a grant inside the same
blast radius as the data it protects.

**The mitigation is to ship each entry off-host as it is written**, to a system under
different administrative control: Splunk HEC, an OTLP log endpoint, New Relic, syslog to a
collector — the target matters less than the trust boundary. Tampering then requires
compromising two systems that do not trust each other, and the off-host copy is what an
investigator reconciles against.

**The seam already exists and this is cheap.** `AuditSink` is a protocol
(`core/audit/sink.py`) with two implementations; a fan-out sink that writes Postgres *and*
streams to a collector needs no signature change and no core rework. Two design questions are
real and unresolved:

- **Synchronous or asynchronous.** Principle VI says nothing blocking that could be an async
  emitter — but an emitter that can drop is an evidence gap nobody sees, which is the failure
  this whole idea exists to close. A local durable spool that the emitter drains is probably
  the answer: the write blocks on the spool, never on the network.
- **What a failed ship means.** `start_governed_run` already refuses a run whose
  `AUTHORITY_ISSUED` could not be audited. Whether an unshippable entry should refuse a *step*
  is the same question one layer out, and the answer decides whether this is a governance
  control or a convenience.

Needs an ADR before a feature. It is not 013's work — recorded here while the reasoning is
fresh, because a gap in the evidence plane is the one kind this platform cannot afford to
carry silently.

1. **R1–R17 are referenced but never defined in-repo.** The constitution requires every spec to
   declare which mandated requirements it touches, and the spec template enforces it — but no
   file enumerates them. Every spec to date has cited them from context. They should be written
   down.
2. **The architecture document the constitution cites is not in this repository.** The
   constitution says it is "sourced from architecture v1.14"; that document lives elsewhere.
   Anything it contains that governs — including sequencing — is currently unavailable to anyone
   working only from the repo, which is what made this file necessary.
3. **The registry-isolation gate row has no owning feature.** It is named in the constitution's
   Quality Gates but no ADR defers it and no planned feature attaches it. Noted in 004's
   conformance contract as deriving from Principle IV and ADR-0025 rather than from a deferral.
   Either a feature should claim it or ADR-0047 should distinguish *deferred by decision* from
   *not yet applicable*.

## Maintaining this file

Update it in the same change that lands a feature or defers work — not afterwards. A deferral
recorded only in a spec's "out of scope" list is invisible to whoever plans the next feature,
which is the failure this file exists to prevent.
