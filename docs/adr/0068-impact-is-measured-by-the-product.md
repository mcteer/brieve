# ADR-0068: Impact is measured by the product, in a namespace reserved for measurement

- **Status**: Proposed
- **Date**: 2026-08-07
- **Relates to**: [ADR-0047](0047-a-passing-stub-is-worse-than-a-missing-one.md), [ADR-0025](0025-registry-isolation.md), [ADR-0038](0038-the-agent-authors-and-a-person-merges.md), [ADR-0064](0064-authoring-tools-are-platform-tools.md), [ADR-0044](0044-federate-or-broker.md)
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
[ADR-0047](0047-a-passing-stub-is-worse-than-a-missing-one.md)'s exact shape wearing better
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
