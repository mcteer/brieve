# ADR-0050: The harness-domain ceiling is its own record in the trust fabric

- **Status**: Accepted
- **Date**: 2026-07-28
- **Relates to**: [ADR-0015](0015-control-plane-vault-as-trust-fabric.md), [ADR-0044](0044-authz-doctrine-and-credential-translation.md), [ADR-0016](0016-control-groups-gate-authority-changes.md), [ADR-0048](0048-nomad-is-the-agent-execution-substrate.md)
- **Requirements**: R2, R3

## Context

[ADR-0015](0015-control-plane-vault-as-trust-fabric.md) describes the control-plane Vault as
holding "agent identities and registration, compiled ceiling policies". Everything in that
sentence shipped in 006. What it does not say — because nobody had needed it yet — is where
the *other* ceiling lives.

An agent has two ceilings, and they are about different things:

| | Bounds | Enforced by | Vocabulary |
| --- | --- | --- | --- |
| **Credential-issuance ceiling** | Which secrets a run's token may read | Vault, on every read | Policy paths |
| **Harness-domain ceiling** | Which tools an agent may call | The governed core, on every invoke | Tool names, product actions |

[ADR-0044](0044-authz-doctrine-and-credential-translation.md) already requires these to be
disjoint: *"policy jurisdictions are disjoint... no rule is duplicated across engines."*
Until 010 only the first was stored anywhere. The second lived in a Python dictionary inside
`FakeIdentityFabric`, under `tests/harness/`, and every authorization guarantee this
platform makes rested on it.

**The specification for 010 got this wrong in an instructive way.** It described the problem
as a "shape mismatch" — a compiled Vault policy on one side, an `AuthorityScope` on the
other — and asked how to translate losslessly between them. The clarification session
adopted that framing and answered it: store the scope as a first-class field on the agent
definition.

Reading one line of `infra/environments/dev/variables.tf` dissolved the question:

```hcl
allowed_paths = ["secret/data/demo/*"]
```

That is a secret path. It is not a tool, it is not a narrower or wider expression of a tool,
and no translation relates the two — they describe different jurisdictions, exactly as
ADR-0044 requires. There was never anything to translate.

Then Phase 0 research dissolved the *answer* as well. `agent_registry` is a built-in Vault
Enterprise engine, and its `register` endpoint takes a closed parameter set:
`ceiling_policies`, `description`, `display_name`, `entity_id`, `id`, `owner`,
`no_default_ceiling_policy`, `optional_authorization_details`. There is no extension point.
A "first-class field on the agent definition" cannot be added, because the definition is not
ours to extend.

## Decision

**The harness-domain ceiling is a first-class record in the control-plane trust fabric,
beside the registration rather than inside it.** A KV v2 mount, `harness-authority/`,
holding three kinds of record:

```
harness-authority/harness-ceilings/<agent_definition_id>   what a definition may call
harness-authority/role-bindings/<role>                     what a role's holder may delegate
harness-authority/policies/<agent_definition_id>           a temporary narrowing, usually absent
```

Each is authored directly in the core's vocabulary — `tool_names` and `product_actions` —
and carries a `schema_version` so a reader can refuse a record it does not fully understand
rather than enforce a subset of it.

**Written by Terraform from reviewed HCL, and by nothing at runtime.** ADR-0015's division
of labor is the governance: definitions in HCL (design-time, version-controlled, reviewed),
enforcement in Vault. This matters more than it looks — **writing a wider ceiling record is
widening a scope**, which is the deliberate, reviewable act ADR-0016 exists to govern. The
read policy grants `read` and nothing else, and no path in the harness, the MCP service, or
any surface writes these records.

**Read by workloads presenting an attested identity**, under a policy separate from the
database one. Not merged, for the reason the evidence read path was not merged: `harness-database`
exists so a run can write its own record, and merging would mean anything able to reach the
state store could read every ceiling in the estate.

**Never inferred from the credential-issuance policy, in either direction.** A definition
registered without a harness ceiling refuses. That substitution — reading a secrets grant as
a tool grant — is the single most dangerous shortcut available, and it is the one someone
would reach for on an afternoon when definitions were refusing and a fallback looked like
resilience.

## Consequences

**ADR-0015's description of the trust fabric is now incomplete**, which is why this record
exists rather than a comment in a module. It holds identities, registration, compiled
ceiling policies — and, as of this decision, the harness-domain jurisdiction too.

**Two records for one definition can disagree.** An agent can be granted a tool whose secrets
it cannot read, or secrets for a tool it cannot call. That is a consequence of keeping the
jurisdictions disjoint rather than a defect, and it is the cost of ADR-0044's rule. Nothing
currently reports the incoherence, and an operator will hit it. Recorded rather than solved:
a checker that cross-referenced them would be a rule duplicated across engines, which is the
thing ADR-0044 forbids.

**The engine appends policies nobody declared.** Terraform registers one ceiling policy;
Vault stores three, adding `default` and `default-ceiling` unless `no_default_ceiling_policy`
is set, which this repository has never set. Their contents are benign — self-inspection and
reading two well-known policies — and the finding is not that Vault granted something
dangerous. It is that the effective ceiling has never been the declared one and nothing had
looked. The fabric now reports both, split into configured and engine-appended. **Whether to
set `no_default_ceiling_policy` is deliberately not decided here**: it changes the security
posture of every registration and deserves its own record.

**Rich Authorization Requests remain the constitutional end-state and are not this.**
Principle IV describes authority manufacture as "attested workload identity → control-plane
Vault → RFC 8693 + RAR against ceiling policies". The implementation is a JWT auth-method
login against a named role, and RAR would let a *task* request a narrowed subset at exchange
time — the "task scope" term in Principle IV's intersection. The registry's
`optional_authorization_details` flag and the identity store's OIDC provider both exist and
are unused. This decision does not close that gap and does not pretend to; it is recorded in
`ROADMAP.md` as its own work.

**What this buys, stated plainly**: every authorization guarantee from 002 onward now rests
on a record an operator edits and reviews, rather than on a dictionary in a test fixture.
The guarantees themselves did not change. What changed is that they are now about something.
