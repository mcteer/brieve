# ADR-0056: Task scope needs an authorization server, and Vault is not one

- **Status**: Accepted
- **Date**: 2026-07-31
- **Relates to**: [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md), [ADR-0048](0048-nomad-is-the-agent-execution-substrate.md), [ADR-0050](0050-harness-ceilings-live-in-the-trust-fabric.md), [ADR-0054](0054-model-written-orchestration-parity.md)
- **Requirements**: R2, R3

## Context

Principle IV states the chain in one line: authority is manufactured per task —
**attested workload identity → control-plane Vault → RFC 8693 + RAR against ceiling
policies** — and effective authority is `user ∩ agent ceiling ∩ task scope ∩ policy`.
[ADR-0048](0048-nomad-is-the-agent-execution-substrate.md) restates it as binding: "Vault
performs RFC 8693 token exchange with rich authorization requests against ceiling policies…
No other path to per-task authority is supported."

**What runs is a JWT auth-method login against a named role.** The allocation presents its
Nomad workload identity to `auth/nomad/role/<name>`, and the token comes back carrying that
role's `token_policies`. The ceiling *is* enforced — by the role binding, which is real and
has conformance rows behind it. What is missing is the **`task scope`** term: the token
carries the agent definition's whole ceiling for the whole run, so a step that needs to read
one path holds everything the definition may ever do, for as long as the run lasts.

[ADR-0050](0050-harness-ceilings-live-in-the-trust-fabric.md) recorded the gap and declined
to close it — "this decision does not close that gap and does not pretend to" — and 010's
research deferred RAR with a named trigger rather than attempting it. It has been carried as
**Unassigned** in the roadmap since, on the reading that the constitution described something
the implementation had not built yet.

**That reading was half right, and the half that is wrong changes the work.** Verified
against the running enclave (Vault 2.0.3+ent) rather than inferred:

- **RAR is real, and it is Vault's.** `authorization_details` is an array of objects of type
  `vault:path_access`, each carrying `path` (exact match only), `capabilities`, and
  optionally `allowed_parameters`, `denied_parameters`, `required_parameters`. Evaluation is
  a genuine restrictive intersection: the request must match at least one RAR constraint,
  **and** the entity's ACL policies must permit the operation, **and** parameter constraints
  must be satisfied. That is Principle IV's intersection, implemented by the substrate.
- **Vault is the RESOURCE SERVER, not the authorization server.**
  `sys/config/oauth-resource-server/{name}` configures *trusted authorization servers*;
  Vault validates their JWTs, resolves the client to an Identity entity, checks the
  `agent-registry` record, and evaluates baseline policies plus — for delegated
  on-behalf-of workflows — the agent's ceiling.
- **Vault does not perform the exchange.** Its OIDC provider's token endpoint accepts
  `authorization_code` and nothing else. This is not an inference from documentation: the
  binary's own request schema says so — *"The authorization grant type. The following grant
  types are supported: 'authorization_code'."*
- **The feature is off here.** `oauth-resource-server` sits in `unactivated` on this enclave,
  and no trusted authorization server is configured.
- **And the registrations already assume it.** Every live registration carries
  `optional_authorization_details: false` — RAR details are *required* on the resource-server
  path. Nothing broke, because nothing uses that path: credentials come from JWT auth, and
  the auth role has no knowledge of the registry, the ceiling record, or RAR.

So the sentence in Principle IV names two things and the platform is missing only one of
them. The `RAR against ceiling policies` half is available and unactivated. **The `RFC 8693`
half has no home in Vault at all**, which means the gap is not "wire up a Vault feature" but
"decide who the authorization server is" — a question the constitution's wording quietly
assumed away by naming Vault as though it were both parties.

## Decision

**Attribution federates to the customer's OIDC provider. Task scope is computed by the
platform. Who mints the final token is a tier, not a fixed answer.**

The product direction is that a customer plugs in their own OIDC provider — Okta, Ping, IBM
Verify, or another. That settles one half of this immediately and, on inspection, cannot
settle the other.

- **The customer's IdP is the identity anchor, always.** It is the only party that can say
  who the human is, and the platform already authenticates humans against it. Nothing here
  changes that, and no design below moves subject authority anywhere else.
- **Task scope is computed by the platform, always.** It derives from the agent registry
  record, the ceiling policy, and what the step is about to do — none of which the customer's
  IdP can see, and none of which it should be asked to model. An IdP that computed our step
  boundaries would be an IdP that had to be redeployed when our step semantics changed. This
  is not a preference about where code lives; it is that the input does not exist on that
  side of the boundary.
- **Vault trusts an issuer, and which issuer is the tier.** `sys/config/oauth-resource-server`
  names *trusted authorization servers*. That is the seam, and it accepts either answer below
  without the rest of the design changing.

**Tier 1 — federated mint, where the IdP supports it.** The platform computes the
`vault:path_access` details and presents them on an RFC 8693 exchange; the customer's IdP
mints the task-scoped token and Vault trusts the customer's IdP directly. **The platform holds
no signing key at all**, which is the strongest form of this and the reason the tier exists.
PingFederate documents the token-exchange grant explicitly, and so does PingAM.

Because the exchange is per run rather than per action (below), the load this puts on a
customer's IdP is one call per launch and one per resume — an ordinary integration, not a
throughput dependency. That difference is what makes this tier realistic rather than
aspirational.

**Tier 2 — platform-minted, where it does not.** The platform performs the second-stage
exchange itself: the customer's IdP token goes in as the subject token, proving who this is
acting for; a short-lived token carrying the task-scoped details comes out; Vault trusts the
platform's issuer. Attribution still comes from the customer's IdP — what the platform adds
is the narrowing, which is the part only it can compute.

**Tier 2 is the default, and saying so is the honest part.** RFC 8693 support is reasonably
available — PingFederate confirmed, others plausible. **RFC 9396 RAR carrying a custom type is
not.** RFC 9396 explicitly permits custom `type` values, so `vault:path_access` is a
legitimate one, but the vendors with documented RAR support are the standards-forward
specialists rather than the enterprise IdPs a customer is most likely to already run. Support
for `authorization_details` in Okta, PingFederate, and IBM Verify was **not established by
this record's research, in either direction** — which is precisely why the shape has to work
without it and improve when it is there.

This is [ADR-0044](0044-authz-doctrine-and-credential-translation.md)'s doctrine applied one
layer in: federate where the other side can validate the claim, and do it ourselves only
where it cannot. The difference from that record is which half is which — here the customer's
IdP owns the *subject* and can never own the *scope*.

**The exchange happens once, when the run is launched — not per action.**

[ADR-0026](0026-delegation-grants-and-per-step-tokens.md) already settles this and this record
had mis-framed it as open. Authority is **two-level**: the user's *delegation grant* — "their
consent to the task, ceilinged by the definition's maximum duration" — is the durable object,
and "per-step tokens are manufactured under it as needed and expire normally." Per-step tokens
are a **lifetime** mechanism, not a scope one. They exist so a leaked token expires quickly,
not so each step carries different permissions.

So the RFC 8693 exchange belongs at **grant issuance**: the user is present, authenticated
against their own IdP, and asking for a task. That is the moment the platform can decide
whether this user may perform this task *and everything it entails*, and it is the only moment
the user is there to be asked. Re-authenticating per action would be asking a question of
somebody who left — which is precisely what the delegation grant exists to avoid, and why
ADR-0026 has a resume "re-exchange **under the surviving grant**" rather than a fresh
authorization decision.

Principle IV's own wording is "authority is manufactured **per task**". Per task is the launch;
per action is the hooks.

**What this costs, and it is a real edge**: the grant must cover the task's full scope at
issuance, so the platform has to know at launch what the task entails. An agent that decides
mid-run it needs something outside the granted scope cannot quietly acquire it — the step
refuses, and widening requires new consent. That is the correct behaviour and it is also a
constraint on how dynamic a run may be, which lands directly on
[ADR-0054](0054-model-written-orchestration-parity.md)'s model-written call graphs: the model
may choose the *shape* of the work freely, and may not choose authority it was not granted.
Whoever implements this owns the question of how a task's entailed scope is computed at launch
without over-granting to be safe, because over-granting to be safe is how a ceiling becomes
decorative.

**Nothing in the platform signs the Tier 2 token. Vault does, and the private key never leaves
it.**

This was drafted as an open question — a signing key held by a long-lived service is the shape
of a standing credential, and Principle IV permits exactly one, already spent. The question
dissolves rather than needing an answer, and the mechanism was demonstrated end to end against
this enclave before being written down:

- **Transit holds the key.** An `ecdsa-p256` transit key signs the JWT's signing input with
  `marshaling_algorithm=jws`, which produces a JWS-compatible ES256 signature in url-safe
  base64. The private key does not exist in the issuing service, on its disk, or in its
  memory — it exists only inside the trust store, like every other secret here.
- **Vault takes the public half as a static PEM.**
  `sys/config/oauth-resource-server/<name>` accepts `public_keys` — a list of `key_id` and
  `pem` pairs — as an alternative to `jwks_uri`. So the issuer serves **no discovery document
  and no JWKS endpoint**, and there is no public surface to operate or secure. Terraform
  registers the key alongside the profile, the same way it registers everything else.
- **The issuer's only credential is its attested workload identity**, exchanged for a Vault
  token exactly as every other workload's is. Nothing durable, nothing to rotate by hand,
  nothing to leak that outlives the allocation.
- **Revocation is a policy edit or a key rotation**, both in Vault, both immediate, and
  neither requiring the issuing service to cooperate — which matters, because the case where
  you revoke is the case where you do not trust it.

**So Tier 2 introduces no second standing credential**, and the sentence in Principle IV
naming one permitted exception stays accurate. That was the objection that made this question
worth leaving open, and it is answered rather than mitigated.

**Two constraints this pins, and both are worth stating rather than discovering.**
`marshaling_algorithm=jws` is documented as *"currently only valid for ECDSA P-256 key types"*,
so the signing algorithm is ES256 and not a free choice. And the authority to call
`transit/sign/<key>` becomes a load-bearing grant: whoever holds it can mint task scope. That
policy deserves the same care as the ceiling itself, because it *is* the ceiling's issuer.

**A simplification this exposes.** Because the exchange happens once per run rather than per
action, the signing step lives naturally inside the path that already starts runs — which
already holds an attested identity and already talks to Vault. **Tier 2 may need no new
long-lived component at all**, only a step in an existing one. The first draft of this record
assumed a standalone STS and reasoned about its blast radius; on this construction there may
be nothing new to attest, monitor, or keep alive. Whether that holds through the resume path,
where no user is present and the surviving grant is what authorises, is the implementing
feature's to confirm.

## Consequences

The `task scope` term stops being a word in the constitution with nothing behind it. A step
that needs one path holds one path, so a compromised process mid-run cannot spend the rest of
the definition's ceiling — which is the difference between a ceiling that bounds what an agent
may *ever* do and one that bounds what it may do *now*.

**The honest limit, stated because it is easy to oversell**: the hook layer already enforces
policy per action, in-process (Principle II), and this does not replace it — the two operate
at different moments and both are needed. Authority is decided once, at launch, for the task
and everything it entails; every individual action is still checked against it as it happens.
What changes is that the check now runs against a token narrowed to the task rather than one
carrying the definition's entire ceiling. What RAR adds is that the
enforcement survives the process being wrong — a compromised or buggy allocation cannot exceed
its step by simply not asking the hooks. That is defence in depth, and it is worth having
precisely because the in-process check is the one an attacker is already inside of. Anyone
describing this as "now we enforce task scope" would be overstating it; the accurate claim is
"task scope is now enforced somewhere the workload cannot reach."

**Costs.** Tier 2 means a token-minting step in the run-start path — possibly not a new
component at all, per the signing decision above, but certainly new code on the path that
starts every governed run, so its correctness becomes the platform's availability. Tier 1 trades that for a
dependency on a customer's IdP being reachable and correctly configured at launch — a
different failure mode, and a smaller one now that it is not in the path of every action: a
run that cannot start is a clear refusal, where a run that cannot take its next step is a
partial failure mid-flight. `oauth-resource-server` must be activated on the
trust store either way, which is a Vault-wide change to how requests are authorized and
deserves its own verification before it is switched on anywhere real. And RAR's exact-match
paths mean the scope has to be computed precisely: a step whose path set is wrong fails
closed, which is correct and will be the first operational surprise.

**A deployment question this creates and does not answer**: two tiers mean two configurations
to support, and the tier a customer lands in depends on their IdP's capabilities rather than
on anything the platform chooses. Detecting that — reading the IdP's discovery document for
token-exchange and RAR support, and saying plainly which tier an estate is in — is work the
implementing feature owns, because an estate that silently fell back to Tier 2 while its
operator believed it was federated would be exactly the kind of unstated posture this platform
legislates against elsewhere.

**What this does not touch.** ADR-0044's federate-or-broker rule is unchanged: this is about
how the harness's own authority is manufactured, not about how product credentials are
translated. The single permitted standing credential remains the TFE broker's management
token, and this record must not add a second — which is exactly why the signing-key question
above is left open rather than answered casually.

## Notes

**Accepted 2026-07-31, and nothing is built.** `oauth-resource-server` is unactivated, no trusted
authorization server is configured, and neither tier exists. What is settled here is the
*shape*: Vault is the resource server, RAR is the mechanism, attribution federates to the
customer's IdP, task scope is computed by the platform because the inputs live nowhere else,
who mints the final token is a tier chosen by what the customer's IdP can do, the exchange
happens once per run rather than per action, and Tier 2's signing key lives in Vault's transit
engine so no service holds one. No open questions remain in the shape; what is left is
construction, and the two places it could still go wrong are named above — computing a task's
entailed scope without over-granting, and confirming the resume path needs no standing issuer.

**What this record's research did and did not establish.** Verified directly against the
running enclave: Vault's supported grant types, the RAR structure and its intersection
semantics, the resource-server configuration path, the activation state, and the live
registrations' flags. Verified from vendor documentation: PingFederate's and PingAM's
token-exchange grant. **Not established, in either direction**: whether Okta, PingFederate, or
IBM Verify support RFC 9396 `authorization_details`, and whether Okta or IBM Verify support
RFC 8693 at all. Those are the questions that decide how often Tier 1 is reachable, and the
implementing feature should answer them against the specific IdPs a first customer actually
runs rather than against the market in general.

**Externally backed.** HashiCorp's own validated pattern
[`ai-agent-identity-with-hashicorp-vault`](https://developer.hashicorp.com/validated-patterns/vault/ai-agent-identity-with-hashicorp-vault)
addresses this problem class — agents acting for a user against Vault — and recommends OAuth
2.0 token exchange for attribution with role-scoped dynamic credentials. Vault 2.0's native
AI-agent support is the substrate half of the same picture. That moves this from *our
constitution describes something we did not build* to *our constitution agrees with the
vendor's field-tested pattern, and the vendor ships one half of it*.

**A correction this record makes to the roadmap.** The gap was carried as though the pieces
existed unused — "the registry exposes `optional_authorization_details`, the identity store
has an OIDC provider with `/token` and no clients". The first is accurate but means something
different from what was implied: it is a flag governing whether inbound JWTs may omit RAR
details, not storage for them. The second is a dead end for this purpose — that endpoint does
`authorization_code` and will not perform an exchange. Anyone starting from the roadmap entry
would have spent a day discovering that, so it is written down here instead.
