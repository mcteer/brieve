# Phase 1 Data Model: Production Identity Fabric

**Feature**: `specs/010-identity-fabric` | **Date**: 2026-07-28

Four records and one in-memory value. Two of the records already exist and this feature only
reads them; two are new. Nothing here is stored by the harness — every persistent record
lives in the control-plane trust fabric, which is the point.

---

## Agent registration *(exists; read-only to this feature)*

Held by Vault's `agent_registry` engine at
`agent-registry/registration/display-name/<display_name>`. **The schema is the engine's and
cannot be extended** (research Finding 3).

| Field | Type | Notes |
| --- | --- | --- |
| `display_name` | string | The key this feature resolves by. Matches `agent_definition_id` |
| `id` | string | Registry-assigned |
| `entity_id` | string | Vault identity entity |
| `owner` | string | Human owner (ADR-0015) |
| `description` | string | |
| `ceiling_policies` | list[string] | **Credential-issuance** jurisdiction. Not the harness ceiling |
| `no_default_ceiling_policy` | bool | Unset today, so Vault appends `default` and `default-ceiling` |
| `optional_authorization_details` | bool | RAR flag; unused until Finding 5's gap closes |

**Validation on read**:

- Absent registration → refuse (`unknown_agent_definition`). Never a default ceiling (FR-003).
- `ceiling_policies` as stored will contain more than was declared. The reader records both
  and does not treat the difference as corruption (research Finding 2).

---

## Harness ceiling record *(new)*

The tool-authorization jurisdiction, in the core's own vocabulary. A KV v2 record beside the
registration, written by the same Terraform, read by the fabric.

| Field | Type | Notes |
| --- | --- | --- |
| `agent_definition_id` | string | Must equal the registration's `display_name` |
| `tool_names` | list[string] | Maps to `AuthorityScope.tool_names` |
| `product_actions` | list[string] | Maps to `AuthorityScope.product_actions` |
| `schema_version` | int | So a reader can refuse a record it does not understand rather than partially parsing it |

**Validation**:

- Missing record for a registered definition → **refuse** (FR-005). Never inferred from
  `ceiling_policies`, in either direction — that substitution is how a secrets grant would
  quietly become a tool grant.
- Any entry naming a tool or action the platform does not know → refuse, naming the entry
  (FR-005a). Silently dropping it narrows a ceiling with no trace.
- Unknown `schema_version` → refuse. A record written by a newer platform must not be
  half-understood by an older one.

**Relationship**: exactly one per registration. The two are separate records on purpose
(ADR-0044 disjoint jurisdictions), which means they can disagree about what an agent is for —
recorded in the spec as a known coherence gap rather than solved here.

---

## Role binding record *(new)*

Turns a claim-derived role into a harness-domain scope. Same store, same governance, same
reader as the ceiling record — it is the same jurisdiction.

| Field | Type | Notes |
| --- | --- | --- |
| `role` | string | As produced by `resolve_roles` from IdP claims |
| `tool_names` | list[string] | |
| `product_actions` | list[string] | |
| `schema_version` | int | As above |

**Validation**:

- A subject resolving to **no** role → refuse (`no_role_for_subject`).
- A role with **no** binding record → refuse (`unbound_role`). Distinct from the above and
  from an empty binding, because the three are different situations: nobody knows who you
  are, nobody has said what your role means, and your role means nothing. Only the third is
  a legitimate empty scope (FR-007).
- Multiple roles → the union of their bindings, then intersected downstream. Union is the
  only choice that makes adding a role additive; intersection would make a second role able
  to *remove* access, which nobody would predict.

---

## Product entitlement query *(new; not stored)*

Not a record — a question asked of a product through a seam this feature defines and the
faked products implement (spec C2).

| Field | Type | Notes |
| --- | --- | --- |
| `subject_user_id` | string | The **user**, never the agent — this is the mirroring check |
| `product` | string | As the registry names it |
| → `actions` | frozenset[str] | What that user may do in that product |
| → *or* refusal | `FabricFault` | Unanswerable is not empty and not full (FR-011) |

---

## Resolved authority *(in-memory, exists)*

`AuthorityScope` — `tool_names` and `product_actions`, frozen, with `intersect` and
`issubset`. Unchanged by this feature; only its provenance changes.

The intersection Principle IV requires, with each term's new source:

```
effective = user scope  ∩  agent ceiling  ∩  task scope  ∩  policy
              │               │                │             │
   role binding records   ceiling record    the request   policy record
       (new)                 (new)          (unchanged)     (new)
```

Three of four terms move from a test fixture to the trust fabric. The fourth was always the
caller's.

---

## Reason codes

FR-012 requires that refusals distinguish three situations. Enumerated here because a
reason code invented at the call site is one nothing can assert on.

| Code | Means | Direction |
| --- | --- | --- |
| `unknown_subject` | Who is asking cannot be established | Who |
| `no_role_for_subject` | Authenticated, but claims map to no role | Who |
| `unbound_role` | Role exists, no binding record | What, unknown |
| `unknown_agent_definition` | No registration | What, unknown |
| `missing_ceiling_record` | Registered, no harness ceiling | What, unknown |
| `unknown_ceiling_entry` | Ceiling names a tool or action the platform does not know | What, unknown |
| `unsupported_schema_version` | Record written by a newer platform | What, unknown |
| `fabric_unreachable` | The trust fabric did not answer | What, unknown |
| `fabric_timeout` | It answered too slowly (FR-018) | What, unknown |
| `entitlement_unavailable` | The product could not be asked | What, unknown |
| `outside_scope` | Resolution succeeded; the action is not permitted | What, permitted |

**Only the last is a policy answer.** Everything above it is the platform declining to guess,
and the two must never be conflated in the record — an investigator reading "denied" needs
to know whether the system decided or failed.
