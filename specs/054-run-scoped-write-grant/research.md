# Research: A run's write grant names only its own workspace

**Date**: 2026-08-27 | **Spec**: [spec.md](spec.md)

FR-009 and SC-006 require the cheapest sufficient mechanism to be established by **evidence**,
with rejected alternatives recorded and what ruled each out. 016 already built a JWT-minting
substrate, so the pull to justify parked work is real and the cheap paths are tested first.

Everything below was measured against the live dev enclave on 2026-08-27 unless marked
otherwise.

---

## R1 — Identity templating cannot tell two runs apart. **This is the finding.**

**Decision**: Vault ACL policy templating over entity or alias metadata is **rejected**. It
cannot express a per-run bound in this estate as it stands.

**Measured**:

- Vault accepts a templated policy: `sys/policies/acl/scratch-agent-{{identity.entity.metadata.run_id}}-*` stored fine (HTTP 204). The mechanism works; the inputs do not exist.
- Nomad dispatch job ids **are** unique per run — `agent-run/dispatch-1787857202-22d75741`.
- But every JWT role uses `user_claim = "/nomad_job_id"`, and the enclave holds **six aliases
  in total**, named by role: `agent-run`, `mcp`, `api`, `mcp-surface`, `conformance`,
  `authoring-tier`. Alias metadata is `{"role": "agent-run"}`.
- The `agent-run` entity (`1990cf78-…`) has **one alias, shared by every dispatched run**.

**Why, and the tree already knew.** `infra/modules/trust-fabric/auth.tf` records it at the
`agent_run` role: *"The identity presents the PARENT id, which is not what `nomad job status`
shows — binding only the derived form fails every login with 'claim nomad_job_id does not
match any associated bound claim values' while the role looks correctly configured."* That is
why `bound_claims_type = "glob"` is there. Somebody paid for this during 010.

**Rationale**: Templating resolves against the entity, and every dispatched run of a definition
shares one. Two concurrent runs would receive identical grants naming each other's workspace —
the defect, reproduced through a different mechanism and harder to see.

**Alternatives inside this option, also rejected**: pre-creating an entity per run (entity
sprawl unbounded by run count, and the entity must exist before the login that would name it);
group membership per run (same ordering problem, and groups are not per-login).

---

## R2 — ANSWERED 2026-08-27: the claim exists, and Branch A is chosen

**Decision**: **Branch A.** `nomad_allocation_id` is present in Nomad 2.0.4's workload identity
JWT, so `user_claim` can name a value that is unique per run. 016's substrate is **not** built.

**Measured**: the identity token was decoded inside a live allocation — the credential never
left it, and only claim names were read out. The claim set is:

```
aud, exp, iat, jti, nbf, nomad_allocation_id, nomad_job_id, nomad_namespace, nomad_task, sub
```

`nomad_job_id` is the parent (`mcp`, `agent-run`) as [R1](#r1) found. `sub` is
`global:default:<job>:<group>:<task>:vault` — also not per-run. **`nomad_allocation_id` is the
only per-run value**, and it is there.

**What this makes structurally true, which is better than what the spec asked for.** Scope is no
longer something the platform derives, stores and re-presents: Vault evaluates the template
against the caller's **own attested identity** on every request. A widened re-mint is not
refused, it is *unrepresentable* — there is nothing to re-derive and nothing to drift. FR-017
stops needing a guard and becomes a property of the mechanism.

**And the policy names change with it.** `vault_policy_impact` currently derives its names from
a `run_id` **tool argument**. Under Branch A they derive from the allocation the code is running
in, which the model cannot influence at all — strictly better than validating a claimed
argument. The `b7c2a2f` guard stays (FR-007) but becomes belt-and-braces rather than the only
thing standing between a model and another run's workspace.

**Alternatives inside Branch A, and why the cheapest one fails.** Leaving `user_claim` alone and
merely adding `nomad_allocation_id` to `claim_mappings` would avoid the cost in R2a below. It
does not work: the alias stays shared, so two concurrent runs overwrite each other's alias
metadata and the template resolves to whichever logged in last. **Reasoned, not measured** —
worth confirming with two concurrent logins before relying on the conclusion.

---

## R2a — What Branch A costs: permanent entity sprawl

**Decision**: Accepted, and recorded rather than discovered later. It is not a blocker; it is a
bill that arrives slowly.

**Measured**: pointing `user_claim` at the allocation id gives every run its own alias, and
therefore its own Vault identity entity. **Nomad garbage-collects its side and Vault does not.**
The dispatch jobs observed an hour earlier were already gone (`0` retained); Vault's entity
count sits at 11 and has no TTL, no expiry and no sweep.

So the entity count grows by one per Build, permanently, in every estate. At laptop scale this
is invisible. At an estate running Builds continuously it is a store that only grows, and
nothing in this platform currently prunes it.

**What is owed**: not a feature, but a recorded consequence and a follow-up. The sweep that
already exists for orphaned scratch policies is the natural home for an entity sweep, and it
already holds the breadth such a sweep needs.

---

## R3 — The fallback, NOT TAKEN (R2 answered yes)

**Status**: recorded for the reader who asks why the obvious cheap alternative was closed.
Branch B is not built.

**Decision, had R2 failed**: the grant would be manufactured by the platform and reached by the
run under its **own** attested identity — never handed to it.

**The constraint is recorded, not inferred.** `auth.tf` says why the model-credential grant is
attached to the role rather than fetched and passed down: *"a key handed to an allocation is a
key in the allocation's environment, which is what ADR-0058 exists to avoid."* So the obvious
cheap fallback — the dispatch surface mints a scoped token and passes it in — is closed by an
Accepted record, not by taste.

**The precedent that survives**: 042 already mints a policy-scoped token through
`vault_token_auth_backend_role` with `allowed_policies_glob = ["scratch-agent-*"]`, exactly so
a run cannot mint tokens under real policy names. That shape is reusable; what it does not
solve is how the run reaches the result without being handed it.

**This is where 016's substrate would have earned its cost.** Vault as resource server
validating a platform-minted JWT is the mechanism that lets a run present something per-run
under its own identity. ADR-0056 established it and it was demonstrated. **R2 answered yes, so
it is not needed and 016 stays parked** — which is the outcome FR-009 existed to make possible
rather than the one it feared.

---

## R4 — The declaration this derives from already exists and is read by nothing

**Decision**: Derive the run's workspace from the pack manifest's per-tool `paths`, per FR-010.

**Measured**: `packs/vault/pack.toml` declares
`paths = [{ path = "sys/policies/acl/scratch-agent-*", capabilities = ["create","update","delete","read"] }]`
on `vault_policy_impact`. `core/packs/manifest.py` says of the field: *"It arrived with 016,
which intended to derive per-run scope from it. That feature was parked … the declaration
survived on its own merits: `risk_class` sat here unread for two features before 013 gave it
meaning."*

**Two consequences.** The input needs no new authoring, which is what 016's clarification was
protecting. And the declared path is itself the wildcard — so the declaration must gain a
per-run form (a token the platform substitutes) rather than being read as-is. That is a
manifest change, and it is the smallest one this feature needs.

**Alternatives considered**: inferring paths from handler code. Rejected on 016's own
reasoning — a static analysis that breaks the first time a path is computed at runtime, and
fails **open** when it breaks.

---

## R5 — SUPERSEDED by R2: FR-017 needs no mechanism at all

**Decision**: Nothing derives, stores or re-presents scope. Vault evaluates the template against
the caller's own identity per request, so there is no second derivation to disagree with a
first.

**What survives**: `RecordedScope` is still worth having, for FR-011 alone — an auditor asking
what a finished run's authority granted. It is a record, not a control.

**Superseded reasoning, kept because the hazard was real**: derive once, record it, re-present
it on every re-mint.

**Rationale**: FR-017 requires every re-mint — resume, renewal, retry — to be scope-identical,
and the maintainer's reason for it is exact: a re-derivation can widen. Comparing two
derivations catches drift only if the comparison is itself correct and always runs; storing
one derivation removes the class. The recorded scope becomes the thing FR-011 answers with
afterwards, which the spec already needs.

**What still needs a row**: storage does not make drift impossible, it makes it detectable in
one place. A row must present a widened re-mint and see it refused (FR-017), or the guarantee
rests on nothing having gone wrong yet.

---

## R6 — What must not move

**Reads are untouched.** ADR-0057's argument stands and the workload has not changed. Row
coverage must include a read a run could make before and can still make after (SC-005), or a
future change narrows reads by accident and nothing says so.

**The sweep keeps its breadth.** `sweep_scratch_policies` finds orphans by listing the
namespace — precisely what a run must not do. `scratch_sweep` is attached to the service role
and `scratch_policy_check` carries no `list`. Narrowing a run's grant must not touch either.

**The pipeline guard stays.** `b7c2a2f` refuses a call claiming a foreign `run_id`. This
feature is the layer beneath it; FR-007 keeps both, and 042's own comment is the argument —
the ACL is *"the only one that survives a platform bug."*


---

## R7 — Obtaining run authority for a row is harder than 018's, and this is what closes it

**Measured 2026-08-27, three routes tried and closed:**

1. **`auth/token/create` with the run's policy names** — 018's `run_authority()`. Closed by the
   contract itself: such a token has `entity_id: ""`, and the templated grant resolves against
   nothing, so every attempt returns 403 and E4 fails. It would produce a green refusal suite
   asserting nothing.
2. **Read the allocation's JWT and log in with it.** Closed by Nomad: `nomad alloc fs` on the
   secrets directory returns *"Reading secret file prohibited"*. Correct behaviour, and worth
   recording as a thing the platform gets right.
3. **A long-lived probe job matching the `agent-run` role.** Closed by configuration:
   `agent_run_job_id_patterns` is `["agent-run", "agent-run/dispatch-*"]`, listed explicitly
   rather than globbed *"to `agent-run*`, which would also admit a job named `agent-runner`"*.

**What remains, and it is a decision rather than a discovery.** A row needs authority that is
both entity-bearing and agent-run-shaped, and only a real dispatched allocation has it. Two
shapes are available:

- **A declared probe job**, admitted by adding a pattern to `agent_run_job_id_patterns` **in the
  dev and conformance environments only**. It obtains authority through the real login path, so
  the contract holds as written. The cost is that a test-only job id is admissible where the
  enclave is a test enclave — bounded, declared, and absent from production.
- **Assert the composition instead of the token**: that `user_claim` names the allocation, that
  the grant templates on the alias, and separately that Vault's templating denies a foreign name
  — the last already demonstrated (403 on read, write and delete against a 200/200/204
  baseline, same templating shape on a mount that can be minted against). Cheaper, and weaker:
  it proves each link rather than the chain.

**What is already proven end to end**, so neither option starts from nothing: a real dispatched
run took the alias `ab997f55-5a60-d77b-9674-b706e8cb3978` — exactly its allocation id — where
every run previously shared the single alias `agent-run`.


---

## R8 — What Branch A satisfies by construction, and the one thing it cannot

Written after implementation, because several requirements stopped needing machinery and one
stopped being reachable. Recording which is which is the point: a requirement quietly dropped
looks identical to one quietly met.

### Met by construction — no code was written, and none should be

| Requirement | Why it needs nothing |
| --- | --- |
| **FR-017** (scope cannot widen between mints) | Nothing derives, stores or re-presents scope. Vault evaluates the template against the caller's own identity per request; there is no second derivation to disagree with a first. `remint_grant` is not built |
| **FR-011** (what a run's authority granted stays answerable) | The grant is one fixed policy and the alias is the allocation id — both already recorded. A `RecordedScope` record would restate what the estate already answers |
| **FR-002** (enforced where it survives a platform bug) | The refusal is Vault's, reached without entering the dispatch pipeline. Row E8 asserts the probe never touches platform code |
| **FR-016** (a restarted run gets a workspace only it can reach) | A restart is a new allocation, so it is a new workspace by the same mechanism. Row E10 |

### The one that is NOT met, and cannot be under Branch A

**FR-012** — *"A scoped write grant MUST be manufactured only for a run whose requested tools
declare a write path. A run with no such tool MUST receive no write authority at all."*

**Measured**: `token_policies` on a JWT auth role is **static**. Vault attaches the same set to
every login; there is no per-dispatch condition available. Every dispatched run therefore
carries `scratch-policy-check`, whether or not it will ever write.

**What that does and does not mean.** The grant it carries is now bounded to a workspace nothing
else can reach, and which is empty unless the run uses it. The harm FR-012 was written against —
a run that never writes holding *estate-wide* write authority — is closed. What survives is that
a run holding no write need still holds a self-scoped grant, and could create junk in its own
corner of the measurement namespace, which the sweep already clears.

**So the intent is met and the letter is not**, and the letter was only reachable on Branch B:
manufacturing per run is what lets you decline to manufacture. That is the cost of the cheap
path, and it belongs beside R2a's entity sprawl rather than buried.

**This is a maintainer decision, not an editorial one.** Either FR-012 is amended to what Branch
A can hold, or it stands and the feature is knowingly short of it. It is left standing and
unmet, recorded here, rather than rewritten by the implementation that could not satisfy it.

---

## R9 — The implementation does not scale, and the reason is a hard ceiling

**Decision**: **Branch A as built is withdrawn.** `user_claim` reverts to the job, and the
measurement moves to the long-lived surface. The isolation 054 exists for is kept — and
improved — without a per-run identity.

**Measured on the running enclave 2026-08-27**, not inferred:

| | |
| --- | --- |
| One dispatched Build | **73 raft writes, +1 permanent entity** |
| A repeat login by an existing identity | 14 raft writes, **no** new entity |
| This session alone | entities 11 → 69, aliases 6 → 63 |
| `auth/nomad/` entity clients | ~6 → 62 |

**Documented** ([Vault limits](https://developer.hashicorp.com/vault/docs/internals/limits)):
entities shard across 256 storage entries, a **hard 256 MiB cap** on integrated storage —
~480,000 entities conservative, ~1,250,000 best case. This estate is Vault 2.0.3+ent on raft,
so the figures apply directly. **Entities carry no TTL and no expiry field**; the identity
record has `creation_time` and `last_update_time` and nothing else.

### Why this is a tier-0 problem and not a bill

**1. Logins are what hit the wall.** Entity writes happen on every login. When the shard space
fills, logins fail — so every Build fails and the platform is down. The documented recovery
("reconfigure to a larger maximum storage entry") does not apply: on integrated storage 256 MiB
*is* the cap. At 10,000 users × 20 Builds/month the conservative ceiling arrives in **2.4
months**, and because nothing expires, the system arrives and stays.

**2. It degrades long before it breaks.** *"The cost of entity and group updates grows as the
number of objects in each shard increases."* Every login pays it, so Build-start latency rises
with the **cumulative count of Builds ever run**. No steady state, no recovery, and it looks
correct in every test — the worst shape a performance defect can take.

**3. It extends recovery.** Raft snapshots carry the identity store, so a quarter-gigabyte of
entities lengthens snapshot and restore. For a service that may not go down, restore time *is*
the availability number.

**4. Write amplification through one leader.** 73 raft writes per Build, serialised through the
raft leader. Build-start throughput is bounded by raft write throughput.

**Measured versus reasoned, stated plainly**: the writes-per-Build, the entity growth and the
ceiling arithmetic are measured. **What exactly happens at the wall is inferred** — HashiCorp
documents the limit and not the failure mode. For tier-0 that belongs in a load test rather
than in a paragraph.

### The category error, named

Entities express *who you are*. A run's workspace boundary is *what this task may do*. Branch A
carried a task scope in the identity system, which is the distinction ADR-0056 drew when it
established Vault as the resource server rather than the authorization server.

**An agent's identity is per definition — or per definition and tenant. Never per invocation.**
`registry.tf` already builds exactly that with `vault_identity_entity.agent`.

### The replacement, in two independent halves

| Half | Fixes | Keeps |
| --- | --- | --- |
| **Revert `user_claim` to `/nomad_job_id`** | the growth, completely — runs share one identity, which already exists, so nothing accumulates | nothing on its own; isolation is lost again |
| **Move the measurement to the MCP surface** | the isolation, and improves it — runs hold **no** policy-write authority at all, so FR-012 is met in full rather than in part | — |

Either alone is a regression on the other. Together they are better than Branch A **and**
better than what preceded it.

**The surface is the right home and the precedent is already there.** It is long-lived, one
alias, one entity, and it already holds `scratch-sweep` with `list`, `read` and `delete` over
the whole namespace — because the sweeper solves a structurally identical problem: *"something
a dead run left that only a living process can clear."* A measurement needing authority a run
should not hold has the same shape.

### Owed regardless of which way this lands

`vault.identity.upsert_entity_txn` is the metric HashiCorp names for this degradation, and
**telemetry is disabled in this enclave** — `sys/metrics` returns 400. Nothing would have told
us. For a tier-0 service that is its own defect.


---

## R10 — Scoping option C: what moving the measurement actually costs

**Decision**: build it. Recorded here because the estimate was wrong twice and the third one
should be checkable.

**What was wrong before.** "Small, three files" assumed `transport = "mcp"` would route the
call to the surface. **It does not: `transport` is purely declarative.** Nothing in `src/`
reads it at invoke time — it is in the same state `risk_class` was before 013 and `paths` is
now. A dispatched run has no channel to the MCP surface at all.

**What already exists, and is more than expected.** Both served surfaces already verify a
**WORKLOAD** subject kind — `served.py` builds `verifier_for(SubjectKind.WORKLOAD, iss=…,
jwks=…)` from `OIDC_WORKLOAD_ISSUER` / `OIDC_WORKLOAD_JWKS_URI`, and `api/service.py` does the
same. The API job configures both; **the MCP job configures neither.** So the mechanism for a
workload to authenticate to a surface is built and unused, not missing.

**The gap that makes it a substrate change.** Measured on a live allocation: the Nomad workload
identity JWT carries **no `iss` claim** (`aud` is `vault.io`, set by the jobspec's `identity`
block), and Nomad's `/.well-known/openid-configuration` returns 404 while `/.well-known/jwks.json`
answers 200. Nomad emits an issuer only when the server is configured with `oidc_issuer`. An
issuer-keyed verifier cannot accept a token that has no issuer, so configuring Nomad is a
prerequisite rather than an optimisation.

**The eight steps, each independently checkable:**

1. Configure Nomad `oidc_issuer` so workload tokens carry `iss` and discovery answers.
2. Add a second `identity` block to the agent-run task with an audience naming the surface —
   a token minted for Vault must not be replayable at the surface.
3. Configure the MCP job with `OIDC_WORKLOAD_ISSUER` and `OIDC_WORKLOAD_JWKS_URI`.
4. Build the run's client for the impact call.
5. Execute `vault_policy_impact` on the surface, under the surface's identity.
6. Grant the surface `create`/`update` on the scratch namespace, beside the `list`/`read`/
   `delete` it already holds for the sweep.
7. Remove `scratch-policy-check` from the run, and revert `user_claim` to the job (**FR-018**).
8. Rework the rows to the stricter claim: a run reaches **no** scratch policy.

**Why this is worth it over reaping** (the option it was chosen against): reaping keeps the
per-run entity and makes availability depend on a cleanup job keeping pace. This removes the
authority instead of bounding its blast radius, so there is nothing to keep pace with.
