# Contract: Substrate requirements

**Feature**: `specs/006-deployment-module-tree`
**Status**: Planned
**Depends on**: ADR-0025 (Kubernetes as accommodation), ADR-0048

## Purpose

State what any substrate must supply. This feature implements the container and instance shapes; it
does **not** implement Kubernetes. Writing the requirements down is what makes a future Kubernetes
substrate a conformance question rather than an argument.

## What a substrate MUST supply

1. **An attested workload identity the trust store accepts** — verifiable by the trust store with
   no shared secret, and bindable to a specific workload so a role cannot be assumed by anything
   that happens to run there. Without the binding the attestation is decorative.
2. **A scheduler that runs the agent harness in a containment boundary.** The container is
   containment; the harness inside is enforcement. Both are required and they are different
   mechanisms (ADR-0048).
3. **Persistent state that outlives an individual workload.** A checkpoint store that dies with the
   process is not durability.
4. **A place to run the trust store that the substrate does not schedule** (FR-004). Two
   independent reasons, per ADR-0048: containment, and the circularity that makes cold start
   impossible when the scheduler is itself a client of the store.
5. **The three endpoints** in [module-interface.md](./module-interface.md).

## What a substrate MUST NOT do

- Configure trust of any kind.
- Require changes to `trust-fabric` to accommodate it. Needing one is the signal that the
  attestation model differs in a way this contract has not yet described — a finding, not a patch.

## Conformance, not analogy

ADR-0025 permits Kubernetes as an accommodation and requires it to demonstrate **the same
conformance assertions**, not an equivalent-sounding story. Concretely: the durability rows must
run as a scheduled workload under that substrate's attested identity, and the configuration digest
must match.

The anti-fragmentation rule holds with one sharpened edge: "substrate delta" now includes the
attestation mechanism, which is a more consequential difference than a scheduling one.

## Out of scope here

Implementing a Kubernetes substrate. Multi-region and disaster-recovery topology. A CI lane running
the enclave — recorded as a known gap in 005's conformance contract and unchanged by this feature.

## Related

- [module-interface.md](./module-interface.md)
- [bring-up-contract.md](./bring-up-contract.md)
