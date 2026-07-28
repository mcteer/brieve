# Phase 0 Research: Production Identity Fabric

**Feature**: `specs/010-identity-fabric` | **Date**: 2026-07-28

Every finding below came from querying the running enclave rather than from reading code or
documentation. Three of them contradict something this repository currently believes, and
one contradicts the constitution. That ratio is the argument for doing this research against
a live system: the two most consequential findings are invisible from the source tree.

---

## Finding 1 — Registrations ARE readable. The feature is possible.

**Decision**: The fabric reads agent definitions from
`agent-registry/registration/display-name/<name>`.

**What was uncertain**: `registry.tf` sets `disable_read = true`, which reads like the
registry is write-only. If registrations could not be read back, this feature would need a
different source of truth entirely and the plan would be a different plan.

**What the enclave says**:

```
$ vault path-help agent-registry/
    ^register$
    ^registration/display-name/(?P<display_name>.+)$
    ^registration/display-name/?$
    ^registration/entity-id/(?P<entity_id>.+)$
    ^registration/id/(?P<id>.+)$
    ^registration/id/?$

$ vault list agent-registry/registration/display-name
demo-agent
```

`disable_read` is a **Terraform-provider** setting — it tells the provider not to read the
resource back into state, because `vault_generic_endpoint` cannot know whether an arbitrary
endpoint is safely readable. It says nothing about the Vault API. Read and list both work.

**Alternatives considered**: A separate registry projection maintained by the harness;
rejected as unnecessary once the read path was confirmed, and it would have created a second
source of truth for ceilings, which is the failure this feature exists to prevent.

---

## Finding 2 — Vault widens every ceiling, and nothing in this repository notices.

**Decision**: The fabric MUST compare the registration's *effective* `ceiling_policies`
against what was declared, and the enclave contract MUST assert the difference is understood
rather than incidental.

**What the enclave says**. Terraform registers exactly one policy:

```hcl
ceiling_policies = [each.value.ceiling_policy]     # ["agent-ceiling-demo"]
```

Vault stores three:

```json
"ceiling_policies": ["agent-ceiling-demo", "default", "default-ceiling"]
```

The `agent_registry` engine appends `default` and `default-ceiling` unless the registration
sets `no_default_ceiling_policy = true` — a parameter this repository has never set and, as
far as the git history shows, never knew about.

**What the added policies actually grant** — read, not ignore, because "Vault added
something" and "Vault widened authority meaningfully" are different claims:

```hcl
# default-ceiling
path "agent-registry/registration/entity_id/{{identity.entity.id}}" { capabilities = ["read"] }
path "policy/default"         { capabilities = ["read"] }
path "policy/default-ceiling" { capabilities = ["read"] }
```

Self-inspection and reading two well-known policies. **Benign in content, and that is
exactly why it is worth recording**: the finding is not "Vault granted something dangerous",
it is that *the effective ceiling is not the declared ceiling and no one had looked.* A
feature whose entire subject is "the ceiling must be what the registry holds" cannot leave
that unexamined — the next default the engine adds may not be benign, and there would still
be nothing watching.

**Note the path typo, which is Vault's own**: `default-ceiling` grants
`agent-registry/registration/entity_id/...` (underscore) while the engine serves
`registration/entity-id/...` (hyphen). The self-inspection grant does not match the route it
is for. Recorded rather than worked around — it is upstream's, and it means the
"inspect your own registration" affordance does not currently function.

**Alternatives considered**: Setting `no_default_ceiling_policy = true` to make declared and
effective identical. Rejected for *this* feature — it changes the security posture of every
registration and belongs in a decision of its own, not in a module edit. The plan records it
as a follow-up with the reason.

---

## Finding 3 — The registry schema is fixed. C1's answer needs a home the engine cannot provide.

**Decision**: The harness-domain ceiling lives in a **dedicated trust-fabric record** —
a KV v2 mount, written by the same Terraform that writes the registration, keyed by the same
display name — not inside the registration itself.

**What was assumed**: The clarification settled that the tool-authorization ceiling should be
"its own first-class field on the agent definition". That phrasing presumed a definition we
could add a field to.

**What the enclave says**: `agent_registry` is a **built-in Vault Enterprise engine**
(`type=agent_registry`, mounted by default — there is no `vault_mount` for it in our
Terraform), and `register` accepts a closed parameter set:

```
ceiling_policies (slice) | description | display_name | entity_id | id | owner
no_default_ceiling_policy (bool) | optional_authorization_details (bool)
```

There is no extension point. `optional_authorization_details` is not storage for
authorization details — it flags whether JWTs may *omit* them (Finding 5).

**Why a separate record is the right answer and not a consolation prize.** C1's substance was
that credential-issuance and tool-authorization are disjoint jurisdictions, which ADR-0044
requires. A jurisdiction with its own record, its own policy, and its own reader is a
*better* expression of that than a second field on one object would have been. The
"first-class" property that mattered is that the ceiling is authored directly in the core's
vocabulary and read directly — not that it shares a struct with the registration.

The tension to state plainly: `registry.tf` opens with "a first-class registry, **not a
convention implemented over kv**." Storing the harness ceiling in KV is adjacent to the
thing that comment disdains. The difference is that the comment was about implementing *the
agent registry* over KV when a real registry engine exists — and there is no engine for the
harness-domain ceiling, because it is our concept, not Vault's.

**Alternatives considered**:

- *Encode the ceiling in a Vault policy* (the spec's original translate approach). Rejected
  at clarify: it produces paths that address nothing, enforced by nothing, parsed only by us.
- *RAR `authorization_details`* — see Finding 5. It is the constitutional end-state and a far
  larger build; deferred with a named trigger rather than attempted here.

---

## Finding 4 — The reference ceiling grants access to a mount that does not exist.

**Decision**: The enclave gains at least one agent definition whose ceiling resolves to
something real, because a conformance row asserting "the ceiling is enforced" against a
no-op ceiling asserts nothing.

**What the enclave says**:

```
$ vault policy read agent-ceiling-demo
path "secret/data/demo/*" { capabilities = ["read"] }

$ vault secrets list        # agent-registry/ cubbyhole/ database/ identity/ pki/ sys/
secret/ mounted: False
```

`demo-agent`'s ceiling grants read on a path under a mount that is not mounted. Correct for
what it was — a registration flow proof, which is all 006 claimed — and inadequate as the
fixture for a feature about ceilings actually bounding things. Every assertion against it
would pass whether enforcement worked or not.

---

## Finding 5 — The constitution describes a manufacture path the code does not implement.

**Decision**: Record it as a named gap. **Do not** close it in this feature, and do not let
this feature's language imply it is closed.

**Constitution, Principle IV**, describing how authority is manufactured:

> attested workload identity → control-plane Vault → **RFC 8693 + RAR** against ceiling
> policies

**What the code does** (`src/core/durability/credentials.py`):

```python
login = self._post(f"auth/{self._auth_path}/login", {"role": self._role, "jwt": ...})
token = login["auth"]["client_token"]
```

A JWT auth-method login against a named role. Not an RFC 8693 token exchange, and no RFC
9396 `authorization_details` anywhere. The ceiling is applied by the role's `token_policies`,
which is a real enforcement mechanism — but it is not the one the governing document
describes, and the difference is not cosmetic: RAR would let a *task* request a narrowed
subset at exchange time, which is precisely the "task scope" term in Principle IV's
`user ∩ agent ceiling ∩ task scope ∩ policy`.

The pieces are present and unused: the registry exposes `optional_authorization_details`, and
the identity store has an OIDC provider (`default`) with `/authorize`, `/token`, and
`/userinfo` endpoints and no clients registered.

**Why this feature does not close it**: it is a second large feature — an OIDC client, an
exchange flow, RAR request construction and validation, and a migration for every existing
credential path — and bundling it here would mean neither lands well. **Why it must be
recorded now**: this feature is the one that reads ceilings, so it is the last honest moment
to notice that the constitution's manufacture path and the implementation's have diverged.
An undocumented divergence between a governing document and the code is the failure
Principle X names.

**Alternatives considered**: Amending the constitution to describe what the code does.
Rejected — the constitution is describing the *right* design; the code is behind it. Weaken
the document to match and the target is lost.

---

## Finding 6 — The "fake only" methods have a production caller, and it writes a placeholder.

**Decision**: The broker branch of entitlement mirroring **refuses** (`broker_not_implemented`)
until ADR-0044's credential translation ships. The two methods leave the protocol as FR-013
requires, and nothing inherits them.

**What was assumed**: That `issue_brokered_material` / `get_brokered_material` were declared
for tests and called only by tests — which is what "(fake only)" in their docstrings says.

**What the source says** (`src/core/hooks/mirroring.py`, production code on the invoke path):

```python
if mode == "broker":
    # Entitlement membership already checked before any shared-grain wield.
    material = fabric.get_brokered_material(authority.credential_id)
    if material is None:
        fabric.issue_brokered_material(
            authority.credential_id,
            "HARNESS_FIXTURE_BROKERED_GRAIN_MARKER_NOT_A_REAL_SECRET",
        )
```

Production code performing a **simulated** brokered exchange, storing a hard-coded fixture
string. The method is not test-only; the *branch* is a stub, and it is a stub that returns
`allow`.

**Why this matters more than the protocol change it complicates.** Principle IV names the
brokered path explicitly — "the rotated, Control-Group-governed management token behind the
TFE broker" is the one permitted standing credential in the entire platform. The mechanism
that credential exists for does not exist. What exists is a branch that looks like it works:
it checks entitlements first (correctly), then "brokers" by writing a placeholder, then
allows the call.

The entitlement check in front of it is real and does its job, so the compensating control
is present. But a reader of `mirroring.py` would reasonably conclude that brokering is
implemented, and it is not.

**Why refusing is the right resolution rather than preserving the simulation.** Keeping it
behind the fake would mean production and test behaviour differ on the exact path where they
must not — a call that is allowed under test and refused in production, or worse, allowed in
both for different reasons. Refusing with a named reason code makes the gap visible at the
moment someone configures a brokered product, which is the moment they need to know.

**Consequence for this feature's scope**: US5 grows a decision it did not have. Removing two
methods from a protocol is trivial; deciding what the branch that called them now does is not.
Recorded so the task list reflects the second thing rather than only the first.

**Alternatives considered**: Implementing federation/brokering here — that is ADR-0044's
feature and explicitly out of scope. Leaving the simulation in place with a comment — a
comment does not stop the branch returning `allow`.

---

## Consolidated decisions

| # | Decision | Rationale |
| --- | --- | --- |
| D1 | Read definitions from `agent-registry/registration/display-name/<name>` | Confirmed readable; single source of truth |
| D2 | Assert declared vs. effective `ceiling_policies` | The engine appends policies nobody knew about |
| D3 | Harness ceiling in a dedicated KV v2 record, Terraform-written | Engine schema is closed; disjoint jurisdiction deserves its own record |
| D4 | Give the enclave a ceiling that resolves to something real | A no-op fixture cannot demonstrate enforcement |
| D5 | Record the RFC 8693 + RAR divergence; do not close it | Too large to bundle; too important to leave unrecorded |
| D6 | Fabric authenticates by workload identity, new narrow read policy | The `harness` role carries only `harness-database` today |
| D7 | Policy read per step, no cache; suspend on mid-run outage | Spec C3 |
| D8 | Entitlement seam real, products faked | Spec C2 |
| D9 | Broker branch refuses `broker_not_implemented` | Its "exchange" writes a placeholder and returns allow (Finding 6) |

## Remaining unknowns

None blocking. Two carried forward deliberately:

- **Where role-to-scope bindings live.** User scope derives from claims through roles
  (FR-006); the roles exist, the bindings do not. The plan places them beside the ceiling
  record for the same reason — same jurisdiction, same governance, same reader.
- **Whether `no_default_ceiling_policy` should be set.** Finding 2's follow-up. Deliberately
  not decided here.
