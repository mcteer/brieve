# Contract: the identity fabric protocol

**Feature**: `specs/010-identity-fabric`
**Status**: Planned
**Seals**: `src/core/authority/fabric.py` — sealed core (Principle V)

## The change

The protocol loses two methods and gains nothing.

```python
# Removed (FR-013)
def issue_brokered_material(self, credential_id: str, marker: str) -> None: ...
def get_brokered_material(self, credential_id: str) -> str | None: ...
```

Their own docstrings say "(fake only)" and "never for audit/spans". A production
implementation would be obliged to implement two methods that exist for tests, and the
honest implementation is a pair that raise — a protocol admitting it does not describe its
own production case.

**Where they go**: onto the fake, which is the only thing that ever needed them. The fake
already has both; it simply stops claiming they are part of the contract.

## What remains

| Method | Source after this feature |
| --- | --- |
| `resolve_user_scope(subject_user_id)` | Role binding records in the trust fabric |
| `resolve_ceiling(agent_definition_id)` | Harness ceiling record in the trust fabric |
| `resolve_policy(agent_definition_id)` | Policy record in the trust fabric, read per step |
| `resolve_product_entitlements(user, product)` | The product, through a seam this feature defines |

## Why this is a narrowing and not a breaking change

Every implementation and every caller is in this repository. `FakeIdentityFabric` keeps both
methods as ordinary methods; nothing in `src/` calls them, and if anything did, that would be
production code reaching into a test affordance — which is the defect, not the constraint.

**The check that makes this stick**: a row asserting the protocol declares no method whose
docstring or name marks it test-only, and that no module under `src/` imports from `tests/`
(FR-015, SC-008). Without it, the next test-only convenience arrives the same way this one
did — as the shortest path at the time.

## Failure contract

Every method raises `FabricFault(reason_code=...)` rather than returning a default. The
reason codes are enumerated in [data-model.md](../data-model.md); the property that matters
is that **no failure path returns an empty scope**. An empty scope is a legitimate answer
meaning "this principal may do nothing", and it must stay distinguishable from "the platform
could not find out" — which is FR-007, and the difference between a person with no
permissions and a system that does not know who is asking.
