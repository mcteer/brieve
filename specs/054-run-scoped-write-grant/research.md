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
