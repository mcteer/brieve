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
export VAULT_ADDR=https://127.0.0.1:8200
export VAULT_CACERT="$PWD/.enclave/ca.pem"   # the enclave serves TLS from its own CA
export VAULT_TOKEN=...                       # VAULT_ROOT_TOKEN from .env
uv run --extra adapters --extra surfaces --extra portal \
  python tests/evals_live/policy_impact_probe.py
```

**`VAULT_CACERT` is not optional and urllib will not find it for you.** The control plane
serves TLS from a CA in no system trust store, and urllib does not read `VAULT_CACERT` on its
own — that is a Vault CLI convention. Without it every request fails verification and the
error surfaces as `URLError`, which reads as "Vault is down" rather than "the certificate was
never loaded". The client handles this once the variable is set; setting it is the caller's.

Expected: two scratch policies written and destroyed inside one tool call; per-path
`current` / `proposed` / `granted` / `revoked` from Vault's own `sys/capabilities`; zero
`scratch-agent-*` policies surviving — which the probe checks itself rather than leaving to a
follow-up command.

Observed 2026-08-07:

```
  secret/data/payments/*        granted ['create', 'update']   revoked []
  secret/metadata/payments/*    granted ['list']               revoked []
zero scratch policies survived; the measurement left nothing behind
```

**This probe earned its keep on its first run.** Vault answers `["deny"]` for a path a token
cannot reach, and the first version of the arithmetic reported `granted: ["list"], revoked:
["deny"]` for the metadata path — "revokes deny" being the absence of capabilities spelled as
a fact, which makes a reviewer count one grant twice. No hermetic row caught it, because the
scripted Vault never returned Vault's actual marker.

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
