# ADR-0069: Governance configuration is requested at a console and decided by the trust fabric

- **Status**: Proposed
- **Date**: 2026-08-07
- **Amends**: [ADR-0026](0026-per-source-model-bindings.md) (moves where a governance change may *originate*; what *decides* one is unchanged)
- **Relates to**: [ADR-0016](0016-quorum-on-authority-changes.md), [ADR-0025](0025-registry-isolation.md), [ADR-0039](0039-per-role-model-bindings.md), [ADR-0047](0047-a-passing-stub-is-worse-than-a-missing-one.md), [ADR-0067](0067-a-model-does-not-judge-its-own-output.md)
- **Requirements**: R2, R3, R4, R5, R7, R11, R13

## Context

Every governance record in this platform is a Terraform apply. The `harness-authority` mount
holds the ask bindings, the Qualified Model Matrix, the protected-policy set, ceilings, role
bindings and claim mappings, and changing any of them requires estate credentials.

**The person who knows the answer is not the person who holds the credential.** Deciding which
model should judge relevance is a judgement about model quality and cost. Holding a token that
can rewrite an agent's ceiling is an infrastructure privilege. Today they must be the same
person, and the two features immediately before this one made that concrete: 043 added
`relevance_cell` to the ask binding and 042 published a protected set, both hand-edited HCL,
both exactly the sort of thing an administrator should be able to change without touching the
estate.

**ADR-0026 rejected deployment configuration on this ground**: *"where a model is reachable
from is assembly while which model is permitted is governance."* That reasoning is correct and
this record does not overturn it.

**A measured finding reframed the problem.** `authority_submit.py` has shipped since 007 — the
surface requests, Vault's Control Groups decide, three native outcomes mapped. It has **never
been exercisable in a deployment**: no policy granted write on any `harness-authority` path,
`vault_policy.authority_change` was attached to no role, and the submitter is constructed
without a token. The conformance rows pass because they run with an operator token. So the
question was not "should we build a governed write path" — one exists — but "should a person
without estate credentials be able to originate a request through it".

## Decision

**A governance change may be REQUESTED at an administrative console and is DECIDED by the trust
fabric.** ADR-0026's line moves at origination and nowhere else.

1. **The console never applies.** It validates, submits through `authority_submit`, and renders
   which of three things the fabric did. There is no code path by which it could decide, and a
   row asserts the module holds no second write path.

2. **The mechanism gets a principal.** An `authority_submit` policy grants `create`/`update` on
   exactly three enumerated records — the ask bindings, claim mappings, and product connections
   — attached to the API's *attested identity*. Not a configured token (a standing credential),
   and not a console service identity (a second thing to bound, when the API already
   authenticates the person). `controlled_paths` is extended to cover those records, closing a
   gap where the configured "gated path" carried no Control Group at all.

3. **Scope is enumerated, not globbed.** Ceilings, the model matrix and the protected set stay
   estate governance. A glob over the mount would have handed over what agents may do and which
   models are qualified, silently.

4. **The `admin` role is disjoint.** It confers configuration authority and *no* audit
   visibility; neither existing role confers configuration authority. Operator and analyst
   answer *what happened*; an administrator answers *what may happen*. A superset in either
   direction is a widening nobody requested, and both directions are asserted.

5. **An administrator cannot grant themselves the role.** Every other protection says yes to
   that request — the grant covers claim mappings, the Control Group decides, the role gate is
   passed. Only this refusal stands between an administrator and a wider one.

6. **A toggle discloses; it never suppresses.** Where a check can be switched off, an answer
   that would have been checked is still given and **says it was not checked**. This is settled
   once here, as the template for every toggle the console grows.

## Consequences

**Governance configuration leaves Terraform for the first time, and the estate keeps writing
it too.** Two writers, one record. Provenance is stamped into the record itself (`set_by`) and
guarded with check-and-set, so "who wrote last" needs no second store — and no second store
means no two answers that disagree exactly when somebody needs to know.

**The ungated posture becomes something the interface must say out loud.** With no quorum
configured a change applies immediately, which is the development default and legitimate. An
interface that looked identical in both estates would be how that posture reaches production
unnoticed, so the console discloses it on every applied change.

**The disclose-not-suppress choice has a cost, stated.** An estate that disables the relevance
gate answers questions whose relevance nobody checked — gap 0g's failure mode, permitted by
configuration. The alternatives were worse: answering silently hides it, and declining means an
administrator who turns off a check has turned off answering. What makes it acceptable is that
every such answer says so, on the answer, where the person reading it will see it.

**Half the requested role vocabulary was declined.** The ask named *research / plan / write /
validate*; ADR-0039's closed set is *ask / plan / write / judge / summarize*. The console
presents the real names with descriptions rather than aliasing the other two, because a display
alias invites a reader to believe a capability exists that does not. No ADR is amended, because
no new capability is being named.

**The next toggle inherits this record rather than re-arguing it.** That is the point of
settling the semantics here: the question — what happens to work that would have been checked —
recurs for every switch an administrator is given, and answering it per setting is how a
platform ends up with three different behaviours nobody chose together.
