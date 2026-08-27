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

## R2 — The one thing that would make this cheap, and it must be tested first

**Decision**: Before building anything, establish whether Nomad 2.0.4's workload identity JWT
carries a **per-allocation** claim, and whether `user_claim` can be pointed at it.

**Why it matters more than any other question here**: if it can, R1 reverses. The alias becomes
per-allocation, the entity becomes per-run, and the whole feature is a changed `user_claim`
plus a templated policy — no minting, no signing, no resource server, no new failure mode on
the run's startup path. That is the difference between a small change and 016's substrate.

**What is already known**: the enclave runs Nomad 2.0.4. The `identity` block in
`infra/jobs/agent-run.nomad.hcl` requests audience `vault.io` with a 1h TTL. Present
`claim_mappings` carry `nomad_namespace`, `nomad_job_id` and `nomad_task` — allocation id is
**not** mapped today, which is not evidence it is absent from the JWT.

**What has to be checked, in order**: whether the JWT contains an allocation-scoped claim at
all; whether `user_claim` may point at it without breaking the `bound_claims` glob that exists
because of the parent-id behaviour; and what an entity per run costs Vault operationally over
an estate's lifetime, since nothing prunes them.

**If it fails**, R3 is the fallback and the cost is real.

---

## R3 — The fallback, and the ADR that constrains it

**Decision**: If R2 fails, the grant is manufactured by the platform and reached by the run
under its **own** attested identity — never handed to it.

**The constraint is recorded, not inferred.** `auth.tf` says why the model-credential grant is
attached to the role rather than fetched and passed down: *"a key handed to an allocation is a
key in the allocation's environment, which is what ADR-0058 exists to avoid."* So the obvious
cheap fallback — the dispatch surface mints a scoped token and passes it in — is closed by an
Accepted record, not by taste.

**The precedent that survives**: 042 already mints a policy-scoped token through
`vault_token_auth_backend_role` with `allowed_policies_glob = ["scratch-agent-*"]`, exactly so
a run cannot mint tokens under real policy names. That shape is reusable; what it does not
solve is how the run reaches the result without being handed it.

**This is where 016's substrate earns its cost, if anywhere**: Vault as resource server
validating a platform-minted JWT is the mechanism that lets a run present something per-run
under its own identity. ADR-0056 established it and it was demonstrated. It is the expensive
answer and must not be adopted before R2 is settled.

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

## R5 — FR-017 is satisfied by not recomputing, not by comparing

**Decision**: Derive a run's workspace **once**, record it, and re-present it on every re-mint.

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
