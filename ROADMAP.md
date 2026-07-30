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

## In progress

Nothing. 012 shipped; the next feature has no number until `/speckit-specify` creates its
directory.

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

### Deferred disclosure and code mode (ADR-0040, ADR-0041)

> Previously headed "010", which guessed a number this file's own rule says not to guess —
> and it was wrong the moment the identity fabric was specified first. Unnumbered until its
> directory exists.

Productizes deferred tool/capability disclosure, and ships code mode — but only with verified
per-call hook parity, which ADR-0041 makes an unconditional gate rather than a default.

**Why here:** both are efficiency features gated on proving governance survives them. Neither is
worth doing before there is enough tool surface for the efficiency to matter.

**Owed gate row:** tool-call parity under deferred disclosure.

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
| RFC 8693 + RAR authority manufacture | **Unassigned** | Principle IV describes manufacture as "attested workload identity → control-plane Vault → **RFC 8693 + RAR** against ceiling policies". The implementation is a JWT auth-method login against a named role. The ceiling IS enforced, by the role's `token_policies` — but RAR is what would let a *task* request a narrowed subset at exchange time, which is the "task scope" term in Principle IV's own intersection. The pieces exist unused: the registry exposes `optional_authorization_details`, the identity store has an OIDC provider with `/token` and no clients. Found by 010, which is the feature that reads ceilings and therefore the last honest moment to notice. **Externally backed as of 2026-07-29**: HashiCorp's own validated pattern [`ai-agent-identity-with-hashicorp-vault`](https://developer.hashicorp.com/validated-patterns/vault/ai-agent-identity-with-hashicorp-vault) addresses this exact problem class — agents acting for a user against Vault — and recommends OAuth 2.0 token exchange (on-behalf-of) for attribution, with role-scoped dynamic credentials and correlation-id traceability. That moves the row from *our constitution says something we did not build* to *our constitution agrees with the vendor's field-tested pattern and we did not build it*, which is a stronger argument for assigning it and a starting reference for how. The same document describes the JWT-with-group-claims approach the implementation uses today — as authorization plumbing beneath the exchange, not as an alternative to it |
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

### 0. The audit trail is not shipped off-host, and hash-chaining only *detects*

**Raised by Dan, 2026-07-29, during 013's live gate run. The most consequential gap on this
page.**

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
