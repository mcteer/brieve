# ADR-0056: Task scope needs an authorization server, and Vault is not one

- **Status**: Proposed
- **Date**: 2026-07-31
- **Relates to**: [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md), [ADR-0048](0048-nomad-is-the-agent-execution-substrate.md), [ADR-0050](0050-harness-ceilings-live-in-the-trust-fabric.md)
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

**Adopt Vault's `vault:path_access` RAR as the mechanism for `task scope`, and accept that
the platform must operate the authorization server that mints it.**

- **Vault stays the resource server, and the ceiling stays where ADR-0050 put it.** The
  agent-registry record and its `ceiling_policies` are already the ceiling's home; the
  resource-server path evaluates exactly that record. Nothing about ADR-0050 is reopened.
- **The task-scoped token is minted by the platform, not by the organization's IdP.** Only
  the platform knows what a step is about to do at the moment it does it. An enterprise IdP
  will not mint per-step `vault:path_access` details, and asking it to would put this
  platform's step boundary inside somebody else's release cycle. This is the same reasoning
  ADR-0044 uses to federate where the product validates external identity and broker only
  where it cannot — except that here the thing being asserted is *our* concept, so nobody
  else can assert it.
- **The exchange is RFC 8693 in shape and the platform's own in implementation**: the
  attested workload identity goes in, a short-lived JWT carrying `authorization_details`
  narrowed to the step comes out, and Vault validates it against the ceiling. The
  constitution's chain survives intact; what changes is that "control-plane Vault" names the
  resource server rather than the exchange point, and this record says so plainly rather than
  letting the sentence continue to imply otherwise.
- **It lands beside the JWT auth path, not on top of it.** The existing path keeps issuing
  the credentials it issues today. The RAR path is introduced where the narrowing is worth
  the most first — tool credential issuance, where a step holding the definition's whole
  ceiling is the actual exposure — and the two are reconciled only once the second is proven.
  A big-bang replacement of the authority chain is how a platform loses the property it was
  trying to strengthen.

**Two questions this record leaves open deliberately, because each decides what kind of
control this is and neither should be settled by whoever implements it first:**

**Where the authorization server lives, and what makes it trustworthy.** It signs tokens that
Vault will honour, so its signing key is as load-bearing as anything in the trust fabric — and
a signing key held by a long-lived service is the shape of a standing credential, which
Principle IV permits exactly once and has already spent. The obvious answer is that the key
is Vault-managed (transit, or PKI-issued and short-lived) so the STS holds no durable secret
of its own, and the obvious answer deserves to be checked rather than assumed. The wrong
answer here gives the platform a second blast radius while it is trying to remove one.

**Per step, or per phase.** Principle IV's wording is per *task*, and ADR-0026's per-step
tokens read as per step. An exchange on every tool call is the strictest reading and has a
cost profile nobody has measured — a network round trip inside the hot path of every
governed action, on a platform that already refuses to let delivery gate availability
(ADR-0055). A coarser grain — one exchange per step, or per contiguous run of steps sharing a
scope — may buy most of the narrowing for a fraction of the cost. That is a measurement, not
a preference, and it should be made with numbers.

## Consequences

The `task scope` term stops being a word in the constitution with nothing behind it. A step
that needs one path holds one path, so a compromised process mid-run cannot spend the rest of
the definition's ceiling — which is the difference between a ceiling that bounds what an agent
may *ever* do and one that bounds what it may do *now*.

**The honest limit, stated because it is easy to oversell**: the hook layer already enforces
task scope in-process (Principle II), and this does not replace it. What RAR adds is that the
enforcement survives the process being wrong — a compromised or buggy allocation cannot exceed
its step by simply not asking the hooks. That is defence in depth, and it is worth having
precisely because the in-process check is the one an attacker is already inside of. Anyone
describing this as "now we enforce task scope" would be overstating it; the accurate claim is
"task scope is now enforced somewhere the workload cannot reach."

**Costs, and they are not small.** A new component that mints tokens is a new component to
attest, monitor, rotate, and reason about — and it sits in the credential path of every
governed action, so its availability becomes the platform's. `oauth-resource-server` must be
activated on the trust store, which is a Vault-wide change to how requests are authorized and
deserves its own verification before it is switched on anywhere real. And RAR's exact-match
paths mean the scope has to be computed precisely: a step whose path set is wrong fails
closed, which is correct and will be the first operational surprise.

**What this does not touch.** ADR-0044's federate-or-broker rule is unchanged: this is about
how the harness's own authority is manufactured, not about how product credentials are
translated. The single permitted standing credential remains the TFE broker's management
token, and this record must not add a second — which is exactly why the signing-key question
above is left open rather than answered casually.

## Notes

**Proposed, and nothing is built.** No authorization server exists, `oauth-resource-server` is
unactivated, and no trusted authorization server is configured. What is settled here is the
*shape*: Vault is the resource server, RAR is the mechanism, the platform mints the
task-scoped token, and the two open questions above are the implementing feature's to answer
rather than to resolve by accident.

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
