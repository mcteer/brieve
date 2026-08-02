# Research: 027 — how the platform holds a model credential

**Phase 0.** Measured against merged `main` on 2026-08-02. The first finding reframes the whole
feature; the second corrects a requirement the spec wrote against an imagined precedent.

---

## F1 — The "TFE broker precedent" is a decision, not machinery. 027 is the first implementation.

**Measured**: `src/core/authority/entitlements.py` defines `BrokeredMaterialSource` as a Protocol
with **no production implementation** — its docstring says the module exists so that a deployment
configuring brokering with no source gets a refusal naming exactly that, and that ADR-0044's
credential translation "is its own feature." The one named exception in Principle IV describes how
a credential *would* be governed; nothing today holds, rotates, or delivers one.

**Consequence**: 027 cannot reuse a broker. It **establishes the brokered pattern's first working
shape**, which the TFE path will later inherit — the dependency points the other way from what the
spec assumed. That raises the design bar: whatever is built here becomes the precedent.

---

## F2 — A static vendor key is not derivable, and the spec's FR-001a overpromises

**The physics**: Vault can mint *derived, lesser* credentials for products with credential APIs
(database roles, PKI). A model vendor's API key has no such API — there is nothing to derive.
"Short-lived material derived from the credential" therefore cannot mean lesser material; the
material a workload uses **is** the key.

**What the precedent actually promises** (ADR-0044, entitlements.py): brokered material is the
**shared-grain credential, delivered per task**, compensated by governance — not derived material.

**Decision**: FR-001a's *"neither can read what it was derived from"* gets a **surgical spec
amendment at implement**, to the honest, precedent-consistent form:

> No workload ever **persists** the credential. It is obtained at task start under the workload's
> own attested identity, held in process memory for the task, and evaporates with it. It never
> enters a checkpoint, a log, the trail, or model context.

Revocation then works through the store, not the workload: rotate or remove the credential and
the **next task's fetch fails** — no restart, no redeploy (FR-006 satisfied for new tasks; a task
already in flight completes on the authority it was issued, exactly like every other per-task
grant this platform manufactures).

---

## F3 — Storage and delivery: a KV record behind the same trust store, read per task

**Measured**: both workload roles already authenticate to Vault with attested identity —
`mcp-surface` (served.py) and the run role (entrypoint) — and the platform's discipline for
checkpoints already forbids credentials (*"checkpoints hold state, never credentials; resume
re-authenticates, never replays"*).

**Decision**:

- **Store**: a KV v2 secret at `model-credentials/<vendor>` (e.g. `model-credentials/anthropic`),
  operator-written, **Control-Group-governed in production posture**, rotated in place.
- **Deliver**: the workload reads it **at task start** — per ask on the surface, per allocation on
  the run path (an allocation *is* one task, so process lifetime = task lifetime and the material
  evaporates with the allocation).
- **Revoke**: delete or rotate the KV entry. Next fetch refuses `credential_unavailable`.
- **Never cached** across tasks, never written anywhere. The existing no-secret-leak rows extend.

**Rejected**: response-wrapping ceremony per task (adds an issuer role without changing what the
workload ends up holding), and a model-gateway proxy (an operated component that still holds the
key — moves it without removing it, Principle VI wants a named trigger).

---

## F4 — Integration: two call sites, one reader, and the eval lane untouched

**Measured**:

- **Ask path**: `served.py` wires `ask_authority` and no provider. `client_and_model` in
  `adapters/anthropic_scorer.py` reads `EVAL_PROVIDER_API_KEY` from the environment — eval-lane
  shaped.
- **Run path**: `ModelChooser._build` → `build_governed_agent(to_model_string(model), ...)`;
  pydantic-ai resolves the vendor key from its environment at agent construction.

**Decision**: one reader, `BrokeredModelCredential` (in `core/authority/`, beside the ask
binding — it is authority-domain), injected like every collaborator:

- `client_and_model` gains an optional `api_key` parameter; **the eval lane keeps the env path**
  (FR-013's exemption, written at the lane).
- `served.py` builds the ask provider **per ask**, fetching through the reader.
- The entrypoint fetches **before `build_chooser`** for a non-fixture model and supplies the key
  explicitly — never via ambient env that would outlive scrutiny.

---

## F5 — The trail: a reference on the records that already carry the model decision

**Decision**: `model_authority` — a **reference** (`vault:model-credentials/anthropic@<version>`),
never a value — added to `ASK_ANSWERED`'s payload and to `MODEL_GATE`'s. FR-007's "how the call
was permitted" then sits beside "which cell allowed it" on the records an investigator already
reads, and FR-009's three failures are disposition values: `credential_unavailable` (the fetch
refused) distinct from `unqualified_cell` (026) distinct from `provider_unavailable` (vendor
unreachable).

**This is the fourth additive touch to `ASK_ANSWERED` in four features.** Principle V review:
**Dan McTeer, and this time actually before merge** — the review that just closed found the one
non-additive change among seven; the new discipline is that the review gates the PR or the
contract says "after merge" from the start. This plan commits to *before*.

---

## F6 — The constitution: a MINOR amendment, with the sentence rewritten rather than read around

**Measured**: constitution v1.3.0; versioning rules say MINOR "adds/expands"; amendments require a
Sync Impact Report citing motivating ADRs; next ADR number is **0058**.

**Decision**: **ADR-0058 — model credential brokering** (the motivating record), and a
constitution amendment to v1.4.0:

- *"with exactly one named exception"* → *"with exactly two named exceptions"*, the second being
  the model vendor credential, same governance clause (rotated, Control-Group-governed).
- *"static API keys are prohibited without exception"* → *"static API keys are prohibited as
  workload credentials; the named exceptions above are held only in the trust store and delivered
  per task."* The sentence is **amended in the open** (FR-002), not reinterpreted — the current
  wording and any vendor key cannot coexist honestly.

---

## F7 — What must not change

- **The blocking lanes**: no vendor credential, unchanged (FR-011). The broker is dev/prod
  posture; tests inject readers.
- **026's binding**: untouched and consumed. The order per ask becomes: governance (cell) →
  credential → provider — three refusals, three people.
- **The eval lane**: exempt, and the exemption written in `tests/evals_live/` itself (FR-013a).
- **Checkpoint discipline**: already forbids credentials; the new rows assert it for model
  material specifically.

## Open for tasks, not for plan

- Whether the dev enclave seeds a placeholder credential (making dev-up's ask progression reach
  `provider_unavailable`… now `credential_unavailable` vs a real answer) or leaves the path empty.
- Whether `MODEL_GATE`'s addition lands in this feature or waits for the first real-model run to
  need it (the ask path is the one with a user today).
