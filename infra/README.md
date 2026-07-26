# The enclave

One parameterized tree. Applied to a workstation and to customer infrastructure, with the
**substrate as the only permitted delta** (ADR-0025, Principle VII).

```bash
make dev-up        # brings it up, in ADR-0048's order, and verifies its own contract
make dev-status    # a glance
make enclave-verify # the full contract, asserted
make dev-down      # stops; destroys nothing
```

## Layout

```text
infra/
├── modules/
│   ├── trust-fabric/          # substrate-INDEPENDENT — this is the product
│   ├── configuration-digest/  # provider-free, so SC-001 is checkable offline
│   ├── substrate-docker/      # containers on a workstation
│   └── substrate-vm/          # hosts at an operator's site
├── environments/{dev,production}/
├── jobs/                      # postgres, harness-probe, conformance
└── bin/                       # enclave-up, -down, -verify, -conformance, -digest-diff, -boundaries
```

`trust-fabric` takes exactly **three** substrate-derived inputs: where workload identities are
verified, where the state store listens, and (via the provider) where it writes. A fourth is the
signal the boundary has moved — possibly correct, but a deliberate change to
[the module-interface contract](../specs/006-deployment-module-tree/contracts/module-interface.md),
not a variable added while solving something else.

## Two axes, and only two

| Axis | Controls | Example |
| --- | --- | --- |
| **Substrate** | *Where* things run | Containers on a laptop vs hosts at a customer |
| **Profile** | *Posture* | Whether the bootstrap credential is revoked; which seal |

Profile is **not** substrate. A workstation could run the production profile; that it usually does
not is convenience. Keeping them apart is what lets "the substrate is the only delta" stay true
while dev and production still differ in hardening.

```bash
make enclave-digest-diff   # SC-001: substrate changes nothing. Runs against no infrastructure.
make enclave-boundaries    # the boundary, both directions, plus FR-004
```

## Production posture

| Item | Status |
| --- | --- |
| Transport security | **Implemented** — PKI-issued, self-signed bootstrap. `enable_tls`; always on in production |
| Bootstrap credential | **Implemented** for the production profile. Development keeps the root token deliberately — revoking it there breaks the re-apply loop, and an enclave nobody re-applies costs more safety than the token does on a workstation |
| Unseal shape | **Seam only** — `seal_config` passes an auto-unseal configuration through untouched. Development default is 1-of-1 shamir. Shipping one KMS variant would privilege a cloud and still leave every other operator writing their own |
| High availability | **Deferred.** Named trigger: the first deployment target that requires it, or the first time single-node behaviour is suspected of hiding a fencing defect |

**The HA deferral has a consequence that must not be lost.** 005's conformance caveat persists:
fencing and parking are proven against single-node behaviour, and multi-node partition is not
exercised. A tree that claimed HA and had never survived a node loss would be worse than one that
says it is single-node.

## The failure catalogue

Six conditions already diagnosed once. The third column is why they cost time — each presents with
a message pointing somewhere other than its cause.

| Condition | Presents as | Points at |
| --- | --- | --- |
| Container driver disallows volume mounts | Task fails to start | The jobspec, which is correct — the fix is in the *agent* config |
| Fresh named volume is root-owned; the trust store runs as uid 100 | Crash loop on permission denied | Storage, not ownership |
| `IPC_LOCK` written in short form | Every apply replaces the container and **reseals the store** | A race, which it is not |
| Raft data moved to a differently-named node | Unseals, then permanently standby, every call answering "sealed" | The seal, not `node_id` |
| Terraform applied against a **sealed** store | Resources vanish from state; the next apply fails on conflict, and has crashed the provider | The configuration, not the seal |
| State-store volume destroyed while the trust store holds the rotated credential | Every credential fails authentication | The credential path, not `rotate-root`'s coupling |
| Terraform state deleted or orphaned while its resources still run | Next apply fails on a name conflict | The new configuration, not the abandoned state |
| Scheduler binds `0.0.0.0` and advertises a LAN address that later goes stale | Job registers, reports `running`, **no allocation is ever placed** — anything waiting on it waits forever | The job, or nothing at all. The HTTP API keeps answering and a leader is still elected |

Each is now prevented or detected by the tree — see `bin/enclave-up` and `modules/substrate-docker`.

### Resetting

`rotate-root` couples the trust store and the state store **in both directions**. Destroy the state
store's volume and it reverts to its bootstrap password while the trust store holds the rotated one;
disable the trust store's database mount and the reverse. Either way nothing authenticates. Reset
them together:

```bash
nomad job stop -purge postgres && docker volume rm brieve-dev-pgdata
make dev-up
cd infra/environments/dev && terraform apply -replace=module.trust_fabric.vault_generic_endpoint.rotate_root
```

## What an alternative substrate must supply

Kubernetes remains an accommodation under ADR-0025. This tree does not implement it; what it must
supply is written down so that adding one is a conformance question rather than an argument — see
[substrate-requirements](../specs/006-deployment-module-tree/contracts/substrate-requirements.md).

Briefly: an attested workload identity the trust store accepts and that binds to a specific
workload; a scheduler running the harness in a containment boundary; persistent state outliving a
workload; somewhere to run the trust store that the substrate does **not** schedule; and the same
three endpoints. It must demonstrate **the same conformance assertions**, not an analogous story —
"substrate delta" now includes the attestation mechanism, which is a more consequential difference
than a scheduling one.

## What this does not guarantee

- **No HA.** Single trust-store node, single scheduler server.
- **No production seal in development.** 1-of-1 shamir with the key in `.env`.
- **No bootstrap-credential revocation in development.** Deliberate; see above.
- **CI does not run the enclave.** The fast lane is fork-safe and cannot hold the licence. The
  durability rows are merge-blocking for a human running them locally — recorded in 005's
  conformance contract.
