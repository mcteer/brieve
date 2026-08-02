# ADR-0058: A model vendor credential is brokered from the trust store, per task

- **Status**: Accepted
- **Date**: 2026-08-02
- **Relates to**: [ADR-0044](0044-authz-doctrine-and-credential-translation.md), [ADR-0022](0022-qualified-model-matrix.md), [ADR-0039](0039-per-role-model-bindings.md), [ADR-0026](0026-delegation-grants-and-per-step-tokens.md)
- **Requirements**: R2, R4

## Context

Three consecutive features built an answering capability that no person could use.

024 built it: a governed path that answers questions from a pinned corpus and cites what it rests
on. 025 extended it to the estate — the same question, routed to the asker's own records, read
through the governed evidence path. 026 governed it: an ask now resolves a cell in the Qualified
Model Matrix before any provider is contacted, so an unqualified model is unreachable rather than
merely unused. Each feature was complete, gated, and demonstrated.

And every ask through the served surface refused before reaching a model. `served.py` wired an ask
authority from the Vault fabric and deliberately wired no provider; 026's own served check proved
its work by watching a refusal *move* — from `unbound` to `provider_unavailable` — rather than by
getting an answer. The same gap existed on the run path and was less visible: `build_chooser`
returns a real `ModelChooser` for any non-fixture identifier, but the dev matrix has only ever held
`fixture:fixture/scripted@1:plan` cells, so no run has ever bound a real model and no allocation
has ever needed a credential. The machinery on both paths was proven — `make evals-live` calls a
real vendor through the product answering path and passes — so what was missing was not capability
but **posture**.

Nobody decided because the decision collided with Principle IV, which read:

> The enclave holds no standing credentials to anything it manages — with exactly one named
> exception: the rotated, Control-Group-governed management token behind the TFE broker (ADR-0044).

A vendor API key sitting in a served surface or a dispatched allocation would be a second standing
credential, and the principle named exactly one. That is a constitutional question, not a
configuration one. Three features recorded the deferral rather than resolving it, which is the
correct behaviour for a feature and the wrong outcome for a platform: the deferral was becoming
permanent by accumulation.

**ADR-0044 already contains the rule that decides this**, and that is the finding that made the
decision tractable rather than novel. Credential translation *federates* where the product
validates external identity and *brokers* only where it cannot. A model vendor authenticates with a
static key and validates no workload identity whatsoever — there is no OIDC audience to present, no
JWT to exchange. Models therefore land in the broker branch by the existing rule. The constitution
had not been written with a vendor in mind; the doctrine had.

**One measurement reshaped the design.** `BrokeredMaterialSource` in
`core/authority/entitlements.py` is a Protocol with no production implementation — its own docstring
says the mechanism "is its own feature." The TFE broker is a decision, not machinery. So this is not
a second use of an established pattern; it is **the first working broker**, and whatever shape it
takes becomes the precedent the TFE path inherits.

**A second measurement corrected what could be promised.** Vault mints *derived, lesser* credentials
for products that expose a credential API — database roles, PKI certificates. A model vendor has no
such API. There is nothing to derive from, so "short-lived material derived from the credential"
cannot mean lesser material: the material a workload uses **is** the key. Any design premised on
scope reduction was unavailable at any price.

## Decision

**The platform holds exactly one vendor credential per vendor, in the trust store, and no workload
ever persists it.**

- **Stored** at `model-credentials/<vendor>` (KV v2), operator-written, Control-Group-governed in
  production posture, rotated in place. The platform reads; it never writes.
- **Obtained at task start**, under the reading workload's **own attested identity** — the surface
  as `mcp-surface`, an allocation as the run role. There is no shared reader identity and no
  ambient environment variable.
- **Held in process for exactly one task**, then gone with it. On the answering path a task is one
  ask; on the run path an allocation *is* one task, so process lifetime and task lifetime coincide.
  Nothing caches: two tasks are two reads.
- **Never written anywhere** — not a checkpoint, a log, the audit trail, or model context.
- **Revoked by deleting or rotating the record.** The next task's fetch refuses; nothing restarts.
  A task already in flight completes on the authority it holds, exactly like every other per-task
  grant this platform manufactures.
- **Recorded by reference**: `model_authority` on `ASK_ANSWERED` carries
  `vault:model-credentials/<vendor>@v<version>` — a location and a rotation generation, never a
  value and never a hash of one. A hash of a low-entropy-format secret is an oracle.

**What makes this safe is lifetime, not scope.** That distinction is the honest form of the promise
and it is stated here because the tempting phrasing — "short-lived derived material" — describes
something the vendor makes impossible.

**The order of checks is part of the decision**, because it decides who gets called during an
incident: the matrix cell is resolved first, then the credential is obtained, then the vendor is
contacted. `unqualified_cell` sends someone to the matrix, `credential_unavailable` to whoever
governs the credential, `provider_unavailable` to the vendor or the network. Collapsing any two of
these would send somebody to the wrong system.

**The blocking lanes need no vendor credential and must keep needing none.** A fixture cell fetches
nothing, because there is no vendor to hold authority for. The eval lane keeps its environment path
under a named human, and that exemption is written at the lane rather than inferred.

**Both paths use one reader.** `BrokeredModelCredential` serves the answering surface and the run
entrypoint. The *providers* differ by path and always have — that is not the fragmentation
Principle VII forbids. Two ways to obtain authority to call a vendor would be.

## Consequences

**This amends the constitution, in the same change.** Principle IV goes to two named exceptions,
and its `static API keys are prohibited without exception` sentence becomes `prohibited as workload
credentials; the named exceptions above are held only in the trust store and delivered per task`.
Both sentences move together — amending one and leaving the other would reproduce, in miniature,
exactly the contradiction this decision exists to end. Shipping the capability first and the
amendment later would leave the platform contradicting its own constitution in the interval, which
is worse than either state alone.

**What it makes easy.** A person can get an answer from the deployed platform, for the first time.
Revocation becomes an operator action with immediate effect and no deployment. The audit trail
answers *how a model call was permitted* beside *which cell allowed it*, and the rotation generation
makes before-the-leak and after-the-rotation distinguishable from the record alone.

**What it costs.** The platform now holds a credential that, if read, is usable by anyone — there is
no scope reduction to fall back on. Blast radius is bounded only by rotation and by the store's own
governance, which is precisely why the write path is Control-Group-governed in production posture
and why the reference carries a generation. This is a real reduction in the strength of Principle IV
and the record says so plainly rather than describing it as a refinement.

**What it forecloses.** A model gateway the enclave federates to was rejected: it moves the
credential outside the boundary and makes the vendor someone else's dependency, but it is an
operated component that still holds the key — moved rather than removed — and Principle VI wants a
named trigger before adding one. Response-wrapping ceremony per task was rejected for a sharper
reason: it adds an issuer role and a second hop and changes **nothing** about what the workload ends
up holding. Keeping models out of deployed workloads entirely — the status quo, live model use only
with a named human present — was rejected because it is the state that made a governed answering
capability unusable for three features while every gate stayed green.

**Obligations this creates.** A sealed-core review for `model_authority` (Principle V). A
security-maintainer review of the constitution amendment. A conformance row asserting no jobspec
passes a vendor key as a workload environment variable, and rows asserting the credential appears in
no trail payload, no response body, and no checkpoint. A readability row proving both workload roles
can read the path against the live fabric. And the demonstration that closes it: a real answer from
the deployed platform, a rotation, and a deletion that refuses the next ask without a restart.

## Notes

The reader is `core/authority/model_credential.py`; the posture rows are
`tests/conformance/answering/test_model_credential_posture.py`. The one that matters most is the
no-environment-fallback row: it sets `EVAL_PROVIDER_API_KEY` and asserts a production ask **still**
refuses. Every other row in the file passes whether or not that fallback exists — a path that fell
back would work on an operator's laptop and fail only in the enclave, which is the most expensive
place to find out.

`MODEL_GATE` is deliberately not given a `model_authority` field. No run has ever bound a real
model, so a run-side field would today be written by nothing and verified by nothing. It goes there
when a run first needs it.
