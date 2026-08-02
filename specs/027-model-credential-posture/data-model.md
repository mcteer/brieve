# Data model: 027 — how the platform holds a model credential

**Phase 1.** One secret, one reference shape, one disposition, two document changes. Nothing new
is persisted by the platform except the operator-written secret itself.

---

## The credential record

`model-credentials/<vendor>` (KV v2), e.g. `model-credentials/anthropic`.

| Field | Rule |
| --- | --- |
| `api_key` | The vendor credential. **The only place it exists at rest.** |
| `rotated_at` | Operator-maintained timestamp; carried into the reference so rotation is visible in the trail without the value being |

- **Operator-written; the platform only reads.** Production posture puts the write path behind a
  Control Group, the way the first named exception is governed. Dev writes it directly.
- **Rotation is an in-place overwrite** — KV v2 versioning makes the version number the rotation
  counter, for free.
- **Revocation is deletion (or rotation to a dud).** Nothing running restarts; the next task's
  fetch refuses.

## The reader (`core.authority.model_credential`)

`BrokeredModelCredential.fetch(vendor)` → the key **for this task**, or raise.

- Reads under **the caller's own attested identity** — the surface as `mcp-surface`, the
  allocation as the run role. No shared reader identity.
- **Never caches.** Two tasks are two fetches; the material's lifetime is the task's, which is
  the entire posture.
- Absent record, unreadable fabric → `ResolutionRefused` with the vocabulary below. **No fallback
  to environment variables** — the env path is the eval lane's, exempt and stated there.

## The reference (what the trail carries)

`model_authority` = `vault:model-credentials/<vendor>@v<version>` — a **location and a rotation
generation, never a value**.

| Property | Why |
| --- | --- |
| Names the store path | An investigator can go from the record to the governance of what permitted the call |
| Carries the KV version | "Which rotation generation authorised this call" is answerable — the difference between before-the-leak and after-the-rotation |
| Never the key, never a hash of the key | A hash of a low-entropy-format secret is an oracle; the platform's rule is references only, and a reference is what this is |

## The `ASK_ANSWERED` record — sealed core, one additive field

| Field | Value |
| --- | --- |
| existing fields | unchanged |
| `model_authority` **(new)** | The reference above when a credential was obtained; empty on every refusal that precedes the fetch |

**Fourth additive touch in four features; the review gates the PR this time** (Dan McTeer). The
just-closed review examined this record's accumulation pattern and held it: ask facts land here
because an ask has no run. `MODEL_GATE` is deliberately **not** touched — no run has ever bound a
real model, so a run-side field would be written by nothing and verified by nothing (plan,
Complexity Tracking).

## Refusal vocabulary (disposition values, joining 026's)

| Value | Meaning | Who acts |
| --- | --- | --- |
| `unbound` / `unqualified_cell` / `matrix_unreadable` | 026's — unchanged, checked **first** | operator / operator / outage owner |
| `credential_unavailable` **(new)** | The cell is qualified; the credential could not be obtained (absent, revoked, or the store refused) | Whoever governs the credential |
| `provider_unavailable` | Credential in hand; the vendor did not answer | The vendor, or the network |

**The order is the design**: cell → credential → vendor. Three failures, three people, and the
trail distinguishes all three (SC-006).

## The two documents

| Document | Change |
| --- | --- |
| `docs/adr/0058-model-credential-brokering.md` | **New.** The decision: broker on the first exception's pattern; ADR-0044's federate-or-broker rule routes models here; gateway and do-nothing rejected with reasons |
| `.specify/memory/constitution.md` | **v1.3.0 → v1.4.0 (MINOR — adds/expands).** *"exactly one named exception"* → *"exactly two"*; *"static API keys are prohibited without exception"* → *"…prohibited as workload credentials; the named exceptions are held only in the trust store and delivered per task."* Ships **with** the capability, never after it |

## State transitions

The credential: written → read per task → rotated (version increments) → deleted (fetch refuses).
The material a workload holds: fetched → used for one task → gone with the process. Nothing else
has a lifecycle, and nothing the platform writes persists the key.
