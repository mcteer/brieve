# ADR-0057: Read-scope narrowing is the wrong control for context-hungry expert agents

- **Status**: Accepted
- **Date**: 2026-07-31
- **Qualifies**: [ADR-0056](0056-task-scope-needs-an-authorization-server-vault-is-not-one.md) — its mechanism stands; its *applicability* to reads does not
- **Relates to**: [ADR-0026](0026-delegation-grants-and-per-step-tokens.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md), [ADR-0048](0048-nomad-is-the-agent-execution-substrate.md)
- **Requirements**: R2, R3

## Context

[ADR-0056](0056-task-scope-needs-an-authorization-server-vault-is-not-one.md) settled how to
implement Principle IV's `task scope` term — the third factor in
`user ∩ agent ceiling ∩ task scope ∩ policy`, which the constitution describes and nothing
implemented. `specs/016-task-scoped-authority` specified it, planned it, and built the
substrate: a transit-signed grant carrying RFC 9396 `authorization_details`, validated by
Vault as an OAuth resource server against the registered agent's ceiling. It works. The
mechanism was demonstrated end to end — a grant naming one path reached that path and was
refused a second the ceiling permitted.

**Then implementation asked what a narrower grant would actually contain, and the answer was
"the same thing as the ceiling".**

The derivation takes a run's requested tools and unions the paths their manifests declare.
But look at what the platform's secret-reading tool does:

```python
path = str(arguments.get("path", "")).strip()      # chosen by the agent, at call time
record = fabric.read_path(f"secret/data/{path}")
```

The path is an *argument*. `vault_read` genuinely reaches everything in the agent's secret
space, so declaring the whole space is accurate rather than lazy. A run that requests it
entails the whole space; a run that does not request it entails nothing. There is no middle,
and so no narrowing — only a binary between secret-touching runs and the rest.

**The more important finding is why that binary is correct rather than a limitation to
engineer around.** These agents are HashiCorp experts. Before producing anything — Vault
integration code, a Terraform provider, a Sentinel policy — an agent reads widely: adopted
skills, HashiCorp Validated Designs, the organization's own security and compliance policy,
prior art. Breadth of *read* is how the output gets informed. An agent denied context does
not fail loudly; it advises badly, and the failure is invisible in exactly the way a
governance control is supposed to prevent.

So a control that narrows reads makes the product worse while making the trail look stricter.
That is the wrong trade, and it is worth recording as a decision rather than discovered again
by whoever next reads Principle IV and notices the gap.

**Meanwhile the property the narrowing was meant to buy is already held.** Authority here is
manufactured per allocation from an attested Nomad workload identity, carries a one-hour TTL,
and database credentials beneath it are leased at 1h/24h. Nothing standing, nothing that
outlives the run by design. Just-in-time and short-lived is the model, and the estate meets
it — which is the substance of "authority per task" even where the scope equals the ceiling.

## Decision

**For read access, the agent ceiling is the task scope, and that is the intended design.**

- **Reads stay broad, deliberately.** An expert agent's job is to gather context before
  acting. The ceiling bounds what it may ever read; nothing narrows that per run, because a
  run that cannot reach its context produces worse work and says nothing about it.
- **`task scope` in Principle IV is satisfied, for read access, by JIT and short-lived.**
  Attested per-allocation manufacture with a bounded TTL is the operative control. Scope
  equalling the ceiling is not a shortfall against that reading; the intersection's third
  term is a ceiling on what a task *may* narrow to, not a requirement that every task narrow.
- **Where narrowing is worth having is WRITE and ACT**, and that is a different mechanism.
  Committing a policy, pushing a provider, applying to a workspace — those bound naturally to
  a target and a run, and they run through product tools under
  [ADR-0044](0044-authz-doctrine-and-credential-translation.md)'s federate-or-broker rule
  rather than through the Vault secret space. Every ceiling in the estate is read-only today,
  so writes are already refused one layer up.
- **ADR-0056's mechanism is not withdrawn.** Vault is the resource server; the exchange has no
  home in Vault; the platform would mint the token; the signing key lives in transit. All of
  that stands and was proven. What this record changes is *when it is worth reaching for* —
  when a task genuinely entails less than its ceiling, which for read paths it does not.
- **`specs/016-task-scoped-authority` is parked, not abandoned**, with its research intact.
  The substrate work exists on `feat/016-task-scoped-authority` and is not merged, because a
  capability that is correct, tested, and wired to nothing is a shape this repository has paid
  for four times (ADR-0055's Notes; ROADMAP gaps 0a and 0c).

**What survives into the tree**: the pack manifest's `paths` declaration and the loader's rule
that a `secret_touching` tool must carry one. Not as scope input — nothing reads it at runtime
— but because a tool whose reach is discoverable only by reading its handler makes its own
review guesswork, and load time is the cheapest moment to require the author to say it.
`risk_class` sat unread for two features before 013 gave it meaning and was worth having
throughout.

## Consequences

Principle IV's description and the implementation stop disagreeing, without building a
mechanism the workload does not want. That is the cheaper of the two honest resolutions, and
the one that leaves the product better rather than merely more conformant.

**A correction is owed to two records, and this one does not make it.**
[ADR-0048](0048-nomad-is-the-agent-execution-substrate.md) states that Vault "performs RFC
8693 token exchange with rich authorization requests against ceiling policies… No other path
to per-task authority is supported" — which is not what runs, and after ADR-0056 is known not
to be something Vault can do at all. Principle IV carries the same phrasing. Both should be
amended to describe attested-identity manufacture with bounded lifetime as the supported path,
naming RAR as the mechanism for write and act scopes when those arrive. Amending the
constitution requires its own change with a Sync Impact Report and security-maintainer review
(Governance), so it is named here rather than smuggled.

**What this costs, stated because it is easy to miss.** A compromised allocation reaches
everything in its agent's secret space for up to an hour. That was true before this record and
remains true; what changes is that it is now a decision with reasoning attached rather than an
unexamined default. The mitigations that do bear on it are elsewhere and already in force: the
ceiling bounds the space, the hooks bound the actions, the trail records the reads, and the
credential expires.

**Re-open this when any of three things changes**: a pack ships a tool inherently narrower
than its ceiling; write or act capability enters an agent ceiling; or an estate's compliance
posture requires per-task read scoping regardless of the cost to output quality. The first two
are ordinary; the third is a real possibility in a regulated deployment, and the mechanism
being proven means it is a configuration decision rather than a project.

## Notes

**Found during implementation, which is the point.** 016 was specified, clarified, planned,
tasked, and analysed four times before anyone asked what a narrower grant would contain. The
tell was in plain sight the whole way — a tool taking an arbitrary path argument is telling
you breadth is the point — and four analysis passes over the artifacts did not surface it,
because they checked coverage, cross-references, and internal consistency rather than whether
the premise fit the workload.

That is a limit of artifact review rather than a failure of it: nothing inside the documents
was wrong. The question that resolved it — *what do these agents actually do all day?* — is
one only the person who knows the product could answer, and it took one sentence.

**Nineteen of fifty-one tasks were built.** The substrate is real and demonstrated: activation,
transit key and signing policy, resource-server profile with static public keys, per-agent
entity alias, and the entity baseline policy. The expensive knowledge is in
`specs/016-task-scoped-authority/research.md` and stays there — Vault is the resource server
and cannot perform the exchange; the entity binds through an alias on the **agent-registry**
mount carrying `external_id` and `issuer`, which the typed Terraform resource cannot express;
`jti` is mandatory and its absence reports only in Vault's server log while the caller sees a
bare 403; `use_jwks` defaults true so static keys need it set false explicitly.

Whoever picks this up will not have to rediscover any of it.

### Where the parked work lives — updated 2026-08-03

The Decision above says "the substrate work exists on `feat/016-task-scoped-authority`". That
branch was archived on 2026-08-03 and the branch itself deleted, so the sentence would have
pointed at nothing. The two commits are preserved verbatim under the annotated tag
**`archive/016-task-scoped-authority`** (`git show archive/016-task-scoped-authority`), whose
message carries the same reasoning this record does.

The Decision text is left exactly as written: what changed is where the evidence is kept, not
what was decided. Recorded here because a governed record that points at a deleted branch is
the kind of quiet inaccuracy this repository keeps paying to find — and this one was created by
the cleanup that removed the branch, which makes it ours to correct in the same breath.
