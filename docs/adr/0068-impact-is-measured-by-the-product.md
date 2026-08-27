# ADR-0068: Impact is measured by the product, in a namespace reserved for measurement

- **Status**: Proposed — amended 2026-08-26: Terraform's instrument is no longer a
  merge-blocking gate (see *Amendment* below). The Vault decision is unaffected.
- **Date**: 2026-08-07
- **Relates to**: [ADR-0047](0047-conformance-gate-rows-attach-as-features-land.md), [ADR-0025](0025-enclave-is-the-default-topology.md), [ADR-0038](0038-integration-uplift-workflows.md), [ADR-0064](0064-version-control-is-a-platform-capability.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md)
- **Requirements**: R5, R7, R11, R2, R3

## Context

The change-proposal workflow asks an agent to propose a change and a person to merge it. What
makes the proposal reviewable is not the diff — a reviewer can read a diff — but an answer to
*what would this actually do*. Terraform has one: `terraform plan` is the product's own engine
answering that question.

**Vault has no plan-equivalent for a policy as a whole.** A policy document is inert until
something holds it. `sys/capabilities` answers *what a token could do on this path*, which is
the right question asked of the wrong subject: the token that would hold the proposed policy
does not exist, because the policy does not exist.

Three ways to close that gap were available.

**Derive the answer.** Parse the HCL, reason about capability semantics, and report the
difference. This is the tempting one — no writes, no cleanup, no new grant — and it is
[ADR-0047](0047-conformance-gate-rows-attach-as-features-land.md)'s exact shape wearing better
clothes. A derived answer agrees with Vault until Vault's semantics differ from the derivation
in some case nobody thought of, and the gate is green either way. This platform already
declined to make Terraform the first product for the same reason: its `terraform_plan` handler
is self-described as *"a shape, not a plan"*, and a soundness gate built on a fixture is green
forever.

**Ask the model.** A proposal whose "impact" is model prose is a review that has been
*reassured* rather than informed — 037's finding, and Principle IX is unambiguous that a model
verdict may gate a step and never satisfies what evidence must show.

**Ask the product.** Write the proposed document under a throwaway name, mint a token carrying
only it, and ask Vault. This requires the platform to **write to Vault**, which is why it needs
a record: it is the first thing a dispatched run in this estate has ever been permitted to
write to the trust fabric, and Principle IV says agents are structurally excluded from managing
their own platform.

## Decision

**Impact is measured by the product, inside a namespace reserved for measurement.**

`vault_policy_impact` writes `scratch-agent-<run-id>-current` and
`scratch-agent-<run-id>-proposed`, mints one 60-second token per side through a bounding token
role, asks `sys/capabilities`, and destroys both policies in a `finally`.

Four properties make this acceptable rather than merely convenient:

1. **One tool call.** Splitting write / mint / check / destroy into separate tools would make
   "always destroyed" depend on a model *choosing* to make the last call — a rule the model is
   asked to follow, which is the thing this feature's central refusal must never rest on. A
   model can request a *measurement*; it cannot request a *policy*.

2. **Names are derived, never supplied.** The scratch names come from the run id inside the
   handler. A governance hook refuses a call that carries one, and the handler would not honour
   it — two layers, because a hook can be unregistered and a handler that trusted an argument
   would then be the whole of the protection.

3. **Both sides go through scratch.** The obvious shortcut for the current side — mint a token
   carrying the *live* policy by name — would require the token role's `allowed_policies_glob`
   to admit real policy names, which hands every dispatched run a way to mint tokens under
   `agent-ceiling`. Two throwaway policies keep the glob absolute.

4. **Nothing is ever attached.** The scratch grant carries no path that can attach a policy to
   an entity, role, or auth mount, and a merge-blocking scan asserts that. A measurement that
   can be attached is a grant, and it would outlive the check that created it.

**The bound belongs to the product.** `allowed_policies_glob = ["scratch-agent-*"]` and an ACL
scoped to `sys/policies/acl/scratch-agent-*` mean Vault refuses everything else — with every
check this repository owns bypassed. That is the third of three independent refusal layers
(request validation, governance hook, product ACL) and the only one that survives a platform
bug. A conformance row exercises it with the platform's hook disabled, because a back-stop only
ever tested behind a working front-stop has never been tested.

## Consequences

**A dispatched run now holds a write capability against the trust fabric.** That is a real
reduction in the platform's posture and is stated rather than absorbed: before this, every
grant a run carried was read-only, and `agent_pack_secrets` deliberately carried no write with
a comment recording why the obvious reason to add one turned out not to need it. What bounds it
is the *namespace*, not the absence of the verb.

**The orphan window is real and is not hidden.** A process killed between the write and the
`finally` leaves scratch policies standing — a grant nobody decided to make. The sweep in the
persistent service is what makes "always destroyed" checkable rather than merely claimed, and
the honest statement is: destroyed on every path the process survives, swept otherwise.
Sixty-second tokens mean the *credential* half needs no sweep.

**Every future product needs its own instrument, named.** This record does not generalise to
Terraform or Nomad; it says what Vault's instrument is and why. Naming the instrument per
product is what keeps the workflow honest rather than generic — and the next product's ADR
should be able to say "a fixture, and here is why that is acceptable" or "a real instrument,
and here it is", not inherit an argument made about a different engine.

**The cost of the alternative is recorded too.** Deriving the answer would have cost nothing to
build and would have been wrong in exactly the cases where a policy review matters — the
unusual capability, the glob that does not mean what it looks like, the KV v2 path prefix.
Those are the cases a reviewer most needs the product's own answer for.

## Amendment — 2026-08-26: Terraform's plan is withdrawn as a gate

**Nothing in the Decision above changes.** That decision is Vault's instrument —
`vault_policy_impact`, its scratch namespace, its bounding token role and its three refusal
layers — and it stands as written. What is withdrawn is a *different product's* application of
the pattern: 047 made `terraform plan` a merge-blocking gate on Propose, and that gate is gone.

**Why, in this record's own terms.** The thesis here is that impact is measured by asking the
product rather than by deriving an answer or asking a model. Terraform's plan was named in the
Context above as the clear case of a product that already answers *what would this actually
do*. It does — **of the environment it is run against**. The gate ran it in the dispatch
container with `-backend=false` and no state, against an estate that is not the one the change
is for. That is the product's own engine answering a question about somewhere else.

So the withdrawal is not a retreat from this ADR; it is this ADR applied more strictly. A
fixture is green forever, which is the failure mode named above. A real instrument pointed at
the wrong subject is worse in one specific way: it is *believable*. The same configuration can
plan clean in that container and fail on apply where it is going, and a reviewer who saw a
green plan has been reassured — the exact outcome the "ask the model" option was rejected for.
The Vault design avoids this by construction, because it measures the policy in the Vault it
would live in; the Terraform gate had no equivalent because the target estate is the
requester's, not the platform's.

**Where the measurement went.** To the person receiving the pull request, who plans it against
their own state, credentials and backend — the only place the answer is true. That is a weaker
guarantee for the platform and it is stated rather than absorbed: Propose no longer carries
plan output as evidence, and soundness of the Terraform itself is now the reviewer's. Judge
deny, ownership failure and publish error still block a PR.

**The Consequences above anticipated this.** *"Every future product needs its own instrument,
named"* — and *"this record does not generalise to Terraform or Nomad"*. Terraform's instrument
was named in 047 and has now been withdrawn there; spec 047 carries the dated note and R7 no
longer lists a failed plan among the conditions that stop a PR. If Terraform is ever to have a
gate in this platform again, it needs an instrument that can reach the estate the change is
for, and this record is the argument for why nothing less will do.
