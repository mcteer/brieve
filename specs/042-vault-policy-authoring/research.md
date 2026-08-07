# Research: Vault policy authoring, end to end

Every decision below is measured against the tree at the 043 merge (`0b5f30b`), not against
what earlier specs said the tree contains. Where a measurement contradicted the obvious
design, the contradiction is the entry.

## R1 — The impact instrument is ONE tool call, and that is the safety design

**Decision**: `vault_policy_impact` is a single registered tool whose handler performs the
whole sequence — write the scratch policies, mint the scratch token, run the capability
checks, destroy everything — with destruction in a `finally`. There is no separate
`write_scratch` / `mint_token` / `destroy_scratch` tool for a model to call.

**Rationale**: FR-022 says the scratch material is destroyed even when the run fails. If the
sequence were three tool calls, "always destroyed" would depend on a model *choosing* to make
the third call — a rule the model is asked to follow, which is exactly what the spec's central
refusal says this feature must never rest on. One call makes the invariant structural: the
model can request an impact measurement; it cannot request a scratch policy.

A crash *inside* the handler between write and `finally` (process kill, OOM) still orphans —
which is why FR-023's sweep exists and why "always cleaned up" is a claim and not a guarantee.
The one-call design shrinks the orphan window from "model's discretion" to "process death
mid-call"; the sweep covers the remainder.

**Alternatives considered**: three tools (rejected — orphan-by-abandonment becomes a designed
state); a host-side check outside the pipeline (rejected — FR-024 requires the governed
pipeline, and a privileged side channel is the shape Principle II forbids).

## R2 — Two scratch policies per check, because FR-009 is a diff

**Decision**: the handler writes **two** scratch policies — `scratch-agent-<run>-current`
carrying the policy body as it stands in the subject repository, and
`scratch-agent-<run>-proposed` carrying the authored body — mints one token per side, runs
the same capability queries against both, and reports the per-path delta.

**Rationale**: FR-009 requires what the change *alters*, not what the proposed policy
permits. The tempting current-side shortcut — mint a token carrying the *live* policy by name
— would require the token role's `allowed_policies` to include protected names, which would
hand every dispatched run a way to mint tokens under `agent_ceiling`. Routing both sides
through the scratch namespace keeps `allowed_policies_glob = ["scratch-agent-*"]` absolute.

A policy that does not exist yet (a new policy) has an empty current side: every capability
in the proposed side is newly granted, and the evidence says so rather than special-casing.

**Alternatives considered**: single-sided check (rejected — FR-009 unmet, reviewer left to
infer); diffing the HCL textually without Vault (rejected — that is a derived answer, "the
fixture problem wearing better clothes" per the clarification).

## R3 — The scratch mechanism, named end to end

**Decision**:

- **Names**: `scratch-agent-<run-id>-current` / `-proposed`. Derived from the run id inside
  the handler; no argument carries a scratch name, so a model cannot choose one (FR-020).
- **Token role**: `auth/token/roles/scratch-check`, declared by the trust-fabric module, with
  `allowed_policies_glob = ["scratch-agent-*"]`, `orphan = false`, `token_ttl = 60s`,
  `renewable = false`. Tokens self-expire, so an orphaned *token* needs no sweep — only
  orphaned *policies* do.
- **Grants**: a new, separate trust-fabric policy `scratch_policy_check` attached to the
  `agent-run` JWT role: `create`/`update`/`delete`/`read` on
  `sys/policies/acl/scratch-agent-*`, `update` on `auth/token/create/scratch-check`, and
  `update` on `sys/capabilities`. Separate policy rather than lines added to
  `agent_pack_secrets`, on `evidence_database`'s own reasoning: a distinct grant with a
  distinct reason should be revocable on its own.
- **Capability query**: `sys/capabilities` called by the *platform* with the scratch token in
  the body — not `capabilities-self` as the scratch token, because the scratch token is
  minted with `no_default_policy = true` (a token "carrying only the proposed policy" that
  also carried `default` would answer for the union) and without `default` it cannot call
  `capabilities-self` at all.

**Rationale**: every piece is bounded by the product itself. Even with the platform's hooks
removed, the Vault ACL admits nothing outside `scratch-agent-*` — the third, independent
layer under FR-025. The 60s TTL is generous for a handful of capability queries and short
enough that an interrupted run leaves no usable credential.

**Alternatives considered**: `capabilities-self` under the scratch token (rejected — needs
`default`, which dirties "only the proposed policy"); child tokens without a token role
(rejected — a parent can only grant its own policies, so the run's token would need the
scratch policy attached to *itself*, which is a run holding authority to change what bounds
it in miniature).

## R4 — The protected set is published by the module that declares it, and a merge gate keeps the publication complete

**Decision**: the trust-fabric module writes the list of its own `vault_policy` resource
names to `harness-authority/data/protected-policies` at apply time — the same operator-
authored, read-only-to-runs mount that holds ceilings and the matrix, already readable under
`harness_authority_read`. A **unit row** scans `infra/modules/trust-fabric/*.tf` for
`resource "vault_policy"` declarations and fails when any name is missing from the published
list, so the list cannot drift when a policy is added (FR-006).

**Rationale**: FR-006 says derived, never hand-maintained. Terraform cannot reflect over its
own resources, so the module's list is technically hand-written — the derivation is the
merge-blocking scan that makes the hand-written list mechanically verified against the
declarations. This is the same honesty shape as 040's capability inventory: *built and
unlisted* fails a merge instead of being found by accident.

**The runtime alternative was measured and rejected**: deriving the protected set as "every
live policy minus the scratch namespace" reads as more automatic, but in the enclave every
live policy *is* a trust-fabric policy — the derivation would protect everything, US1 could
read nothing, and the feature would pass its safety rows by being unusable. In a customer
estate the same derivation would protect every app policy from the agent, which is the
defect's mirror image.

## R5 — Where the refusal binds: three independent layers, and the row targets the middle one

**Decision** (FR-004, FR-025, SC-002, SC-003):

1. **Request validation, pre-run** — the policy-authoring request names its target policy;
   a target in the protected set refuses `policy_protected` before anything is read
   (US2-1). Lives beside 041's `AuthoringRequest.validate`, in the dispatch surface.
2. **A GOVERNANCE pre-hook in the pipeline** — registered for the run by the dispatch
   surface (product-aware, so `core/authoring` stays product-blind), inspecting
   `author_file` and `vault_policy_impact` arguments: a policy name in the protected set
   refuses and **records the attempt** (US2-3 — the model tried anyway; the act refused).
   This is the layer SC-003's removable-refusal row deletes to prove the safety case can
   lose.
3. **The Vault ACL itself** — `scratch-agent-*` is all the product admits, so even a
   platform bug cannot reach `sys/policies/acl/agent_ceiling` (FR-025's back-stop).

Plus the namespace guarantee: a unit row asserts no trust-fabric `vault_policy` name begins
with `scratch-agent-`, which is FR-020's "reserved namespace no trust-fabric policy can
occupy" as a merge gate rather than a convention.

**Rationale**: 038 already recorded why enforcement lives in hooks — "a conformance row over
a module function would have been green." The three layers fail independently: removing the
hook trips the row; removing the row's target still leaves Vault refusing; adding a
trust-fabric policy into the scratch namespace trips the unit row before it ships.

**FR-005 is inherited, not built**: the injection lens already rides `read_subject`'s POST
phase and records planted instructions without refusing the read. What 042 adds is only the
recording in layer 2 when a planted instruction *escalates* to an attempt.

## R6 — Reading policies: bodies of protected policies are refused, and that is FR-013 done structurally

**Decision**: `vault_policy_read` lists policy names, reads attachments for any policy, and
reads **bodies only outside the protected set**. A protected body answers
`policy_protected`; a missing policy answers `policy_absent` — distinguishable states
(FR-003). No secret path is touched at all: the tool's surface is `sys/policies/acl` and
attachment metadata, so FR-002 holds by construction rather than by filtering.

**Rationale**: FR-013 forbids trust-fabric policy bodies in a proposal. A body that never
enters the run cannot enter the proposal — refusing at read is the structural form, where
scrubbing at composition would be an inspected one (038's containment writes down exactly
this strength distinction). Attachments stay readable: "agent_ceiling is attached to JWT
role agent-run" is wiring, not content, and the clarification already records the platform-
identity read cost honestly.

**Attachment scope, bounded**: attachments are resolved from token roles
(`auth/token/roles`), JWT auth roles (`auth/<mount>/role/<name>`), and identity entities and
groups — the places the enclave actually attaches policies (measured: `auth.tf` attaches via
`token_policies` on JWT roles). Each source is queried by list-and-filter, output bounded
per FR-010 with the bound disclosed. Entity/group scanning caps at the same bound — 029's
lesson is cited on the constant.

## R7 — New tools live in the vault pack; the handlers join the existing platform table

**Decision**: `vault_policy_read` and `vault_policy_impact` are declared in
`packs/vault/pack.toml` and implemented in `src/surfaces/handlers.py`, joining `vault_read`
and `vault_write` in `PLATFORM_HANDLERS`. Both `risk_class = "secret_touching"`, `transport
= "native"`, `product = "vault"`. Nothing lands in `core/authoring` — the product-blindness
gate that caught 041 keeps passing unedited.

**`vault_policy_impact` is `repeatable = true`, and the argument is recorded because the
precedent points the other way**: `vault_write` is non-repeatable because a lost CAS write
must be resolved by observation, not replay. The impact check's *contract* is that it leaves
nothing behind — re-running it overwrites its own scratch names, re-answers, and re-destroys,
so a replay after interruption **heals** the very orphan the interruption created. A
non-repeatable declaration would demand an observer whose honest answer ("did the transient
thing happen?") is useless to a resumer.

**Alternatives considered**: a separate policy-tools module (rejected — `handlers.py` is
already "what a manifest's handler strings may become", and a second table is a second
answer to that question); MCP transport (rejected — no mature Vault MCP server, same
determination the pack already records).

## R8 — The Vault client grows four additive methods; the finding is that today's client cannot write at all

**Measured**: `VaultDatabaseCredentials` has `login`, `read_path`, `list_path`, and a
private `_post`. **Nothing in the platform writes to Vault through the workload identity
today** — `vault_write` is a stub that returns `{"written": True}` without touching the
product, and `agent_pack_secrets` carries no write grant, with a comment recording exactly
this. 042's scratch write is therefore the platform's **first real write to Vault through
the governed pipeline**, and the plan says so rather than assuming the path is worn.

**Decision**: additive methods on the existing client — `write_path`, `delete_path`,
`create_token(role, policies, ttl)`, `capabilities(token, paths)` — reusing the login, TLS
and timeout handling that has been wrong here at least once (the CA-context comment). Sealed
core, additive only, named for Principle V review, on 043's `client_and_model` precedent.

**Alternatives considered**: a second client in the handler layer (rejected — duplicated
login/TLS is Principle VII's drift by copy); hvac dependency (rejected — Principle VI, and
the existing client already speaks the API).

## R9 — Evidence rides the PR body as a platform-authored section; citations are checked at composition

**Measured**: `Proposal` separates `rationale` (agent-controlled, scanned) from `provenance`
(platform-authored) precisely because "the two have different authors and therefore
different trust." The PR body is composed at publish (`--body`), and the store keeps
reference-not-body.

**Decision**: the impact result is formatted **by the platform** from Vault's answers into
the PR body's evidence section — per queried path: current capabilities, proposed
capabilities, delta — alongside the diff and the citations. The model never writes the
impact section; it is Vault's answer, mechanically rendered (Principle IX: a model verdict
never satisfies what evidence must show). Citations in the rationale are resolved against
the pinned corpus manifest at composition; zero resolved citations adds the FR-012
disclosure to `Proposal.disclosures` rather than blocking — declining to claim grounding
beats refusing to propose.

**An authored evidence *file* was rejected**: files in a proposal land in the target
repository when merged, and impact evidence is true of the estate at proposal time — merging
it would fossilise a measurement as repository content.

## R10 — Path extraction is a bounded stanza scan, and Vault validates the whole document anyway

**Decision**: the paths to query are extracted from both policy bodies' `path "…" { … }`
stanzas with a bounded scan (no new HCL dependency — Principle VI), unioned with the paths
whose stanzas the diff touches, capped at a fixed count with the truncation disclosed
(FR-010). Glob paths are queried as written and labelled as such in the evidence.

**Rationale**: the scan does not need to *parse* HCL correctly to be safe, because the
scratch write hands the full document to Vault, whose parser is authoritative — a
syntactically invalid policy refuses at the write and is reported as a **policy error**, not
an impact result (edge case in the spec). The scan only needs to find query candidates, and
a missed stanza means a disclosed bound, not a wrong answer.

## R11 — Orphan sweep lives beside the resume sweeper, under the service identity

**Decision** (FR-023, SC-010): the persistent MCP service — already home to the resume
sweeper and dependency health checks because "both needed a long-lived home" — gains a
scratch sweep: list `sys/policies/acl`, filter `scratch-agent-*`, delete any whose run is
not live, write an audit event naming what was removed and why. The **service** role gets
the list/delete grant; `agent-run` keeps only its own names. Scratch *tokens* need no sweep
(60s TTL, R3).

**Alternatives considered**: an operator make-target only (rejected — "always destroyed" is
checked by a machine or it is a claim); sweeping from the run itself (rejected — the dead
run is exactly the case).

## R12 — The live rows fail rather than skip, and the runner is named

**Decision**: the conformance contract's V-rows marked `enclave` run against the real Vault
and **fail** when it is absent (FR-016, SC-007), on the precedent of 040's M18. The named
runner for every non-automated row is **Dan, before merge**, recorded in the contract per
constitution v1.1.0. The full end-to-end leg (author → impact → real PR) reuses 041's live
authoring lane shape (`tests/evals_live/authoring*.py`) with a policy-repository subject.

## R13 — What 042 does NOT build, measured

- **No second publishing path** — `open_proposal` and the 041 publisher are consumed as-is;
  a row asserts the registry holds exactly one publisher (FR-014).
- **No requester-scoped reads** — `product_mode = "none"` stands; the clarification records
  the cost as owed (FR-018). ADR-0044 translation territory, unbuilt.
- **No new eval lane** — the write cell's mechanical qualification (ADR-0063) and the
  answering/judge cells are consumed unchanged. The impact check is not a model output, so
  nothing here is eval-gated beyond what 041 already gates.
- **No intake surface** — requests stay operator-authored; the intake composition feature
  remains the ROADMAP's successor.
- **No secret paths** — neither new tool takes a secret path argument; `vault_read`'s
  boundary is inherited by construction, not by filter.

## R14 — ADR: one new record

**Decision**: `ADR-0068 — impact is measured by the product, in a namespace reserved for
measurement` (Proposed in this feature). It records: the scratch mechanism and its three
independent bounds; why both sides of the diff route through scratch; why the check is one
tool call; and the orphan window that remains. ADR-0025/0038/0062/0064/0066 are consumed,
not amended.
