# Quickstart: Vault policy authoring

How to see it working, cheapest first. Row IDs refer to
[contracts/conformance-policy-authoring.md](contracts/conformance-policy-authoring.md).

## Prerequisites

- Hermetic: nothing beyond the repo.
- Live legs: `make dev-up` (the enclave Vault is the impact instrument — there is no
  fixture mode, by design); the trust-fabric apply that ships the `scratch-check` token
  role, the `scratch_policy_check` grant, and the published protected set.
- End to end: 041's authoring prerequisites (GitHub App key in the trust store) and a
  policy-repository subject.

## 1 — Hermetic proof (every PR)

```sh
make check                 # V6/V7 scans, request/hook refusals, ImpactResult composition
make conformance-hermetic  # V1–V14, V18: the safety case, the reader, the instrument's refusals
```

Failures worth causing on purpose: give a request `target_policy = "agent_ceiling"` (V1);
call `vault_policy_impact` with a `scratch_name` argument (V11); unregister the 042 hook and
watch V3 fail — the safety case losing is the demonstration.

## 2 — The instrument, one call, raw output (live; named runner: Dan)

```sh
make dev-up
# PL1 — a single impact check with the capability answers printed
```

Expected: two scratch policies written and destroyed inside one tool call; per-path
`current` / `proposed` / `granted` / `revoked` from Vault's own `sys/capabilities`; zero
`scratch-agent-*` policies surviving (`vault policy list | grep scratch-agent-` is empty).

## 3 — The product-level back-stop (live)

V16: with the platform hook disabled, a scratch write naming `agent_ceiling` still refuses —
from Vault's ACL, not from the platform. The safety case does not rest on the platform being
correct.

## 4 — End to end (live; named runner: Dan)

PL2: a policy-repository subject → request naming a non-protected policy → read →
author → impact → real pull request. Read only the PR and answer SC-001's three questions:
what changed (the diff), what it now permits (the impact section), on what basis (the
citations). Confirm no secret value and no trust-fabric body anywhere in it (V18).

## 5 — What did not change

- 041's rows: pass unedited, asserted as a diff from the merge-base (SC-008).
- `core/authoring`: still product-blind — the gate that caught 041 runs unedited.
- `vault_read`'s boundary: inherited by construction; no new tool takes a secret path.
- The estate: nothing a run does here changes a live policy; what a person merges is still
  the only thing that changes the estate.
