# Contract: identity conformance lane

**Feature**: `specs/010-identity-fabric`
**Status**: Planned
**Depends on**: Constitution Quality Gates (v1.2.0); ADR-0015; ADR-0044; ADR-0047; ADR-0049

## The row this feature finally makes meaningful

Not a new constitutional row — an existing family of them. Every row asserting that authority
cannot exceed a ceiling has passed since 002 against a dictionary in `FakeIdentityFabric`.
They were not wrong; they were narrower than they read. After this feature they assert the
same properties against what an operator configures.

**That is the honest framing, and it is worth stating precisely.** This feature does not add
much new *behaviour*. It changes what a large number of existing assertions are about, which
is a different and harder thing to demonstrate — and it is why the rows below concentrate on
provenance rather than on outcomes.

## Rows

| Row | Asserts | Spec | Enclave |
| --- | --- | --- | --- |
| Ceiling comes from the registry | Two definitions with different ceilings produce different manufactured authority; neither exceeds its record | FR-001, FR-004, SC-002 | **yes** |
| Unknown definition refuses | An unregistered id never resolves to a default, empty-then-widened, or open ceiling | FR-003, SC-005 | **yes** |
| Jurisdictions never substitute | A registration with a credential policy and no harness ceiling refuses; neither is inferred from the other | FR-005, SC-003 | **yes** |
| Unknown ceiling entry refuses | A ceiling naming an unknown tool refuses and names it, rather than dropping it | FR-005a, SC-003 | no |
| Declared vs. effective policies | The engine's appended `default` / `default-ceiling` are observed and accounted for, not discovered later | research F2 | **yes** |
| User scope comes from claims | Two users whose claims map to different roles get different authority for the same request | FR-006, SC-004 | **yes** |
| Three "no scope" cases stay distinct | No role, unbound role, and empty binding produce three different reason codes | FR-007, SC-005 | no |
| Policy is read per step | A mid-run narrowing bounds the next step; zero steps served from cache | FR-008, FR-009, SC-006 | **yes** |
| Mid-run outage suspends | Losing the fabric mid-run suspends naming it, holds no container, and resumes on recovery with no operator action | FR-008a, SC-006a | **yes** |
| Recovery order terminates | Fabric → checker login → credentials → health recorded → sweep. Asserted as an order, because it is the only one that terminates | FR-008b | **yes** |
| Health cannot be faked healthy | Nothing that failed to reach the fabric may mark it healthy; unknown already refuses | FR-008c | no |
| Entitlement mirroring bites | A user narrower than the credential cannot exceed themselves; zero side effects | FR-010, SC-007 | no |
| Unanswerable entitlement refuses | Unknown is neither empty nor full | FR-011, SC-007 | no |
| The fabric is unreachable from a tool | With an agent's own credential, ceiling paths are denied **by Vault**, not by our code | FR-016 | **yes** |
| Protocol declares no test-only method | And no module under `src/` imports from `tests/` | FR-013, FR-015, SC-008, SC-009 | no |
| No static credential | The same assertion the durability and evidence paths already carry | FR-002, SC-010 | **yes** |

## Break fixtures worth naming

A break fixture is only useful if the thing it breaks would otherwise pass. Three here are
worth building because the failure they model is the failure that *looks fine*:

- **A fabric that returns an empty scope on error.** Every "denied" row still passes — denial
  is what an empty scope produces. What fails is the reason code. This is the single most
  likely regression in the feature, because returning `AuthorityScope()` on an exception is
  the shortest path and reads as fail-closed.
- **A ceiling reader that falls back to `ceiling_policies`.** Plausible as a "be resilient"
  change, and it converts a secrets grant into a tool grant.
- **A resolver that caches policy for a few seconds.** An obvious optimisation, and it makes
  a mid-run narrowing take up to that long to bite. The row that catches it is the one
  asserting zero cached steps, not the one asserting the narrowing eventually applies.

## The fixture problem, recorded because it invalidates the obvious approach

`demo-agent`'s ceiling grants `secret/data/demo/*` and `secret/` is not mounted (research
Finding 4). **Rows written against it would pass whether enforcement worked or not.** The
enclave gains a definition whose ceiling resolves to something real before any enclave row is
written; a task that writes rows first would produce green that means nothing.

## Who runs these

| Where the change comes from | What covers these rows |
| --- | --- |
| Same-repo branch or pull request | The enclave lane (`.github/workflows/enclave.yml`). A required check |
| Fork pull request | **The agent harness in the IDE**, per `AGENTS.md` |
| The lane could not run | **The agent harness.** A lane that did not run is not a lane that passed |

Recorded here because the constitution requires a blocking row with no automated runner to
name who runs it *in this contract*. 009 narrowed that to forks; this feature inherits the
narrowed version and adds nothing to it.

## What this lane still cannot prove

Stated so nobody reads the green as broader than it is:

- **Authority manufacture does not match the constitution.** Principle IV describes RFC 8693
  + RAR; the implementation is a JWT role login (research Finding 5). These rows assert the
  ceiling is *read* correctly and *enforced*, not that it is manufactured the described way.
- **The two jurisdictions can disagree.** An agent may hold a tool whose secrets it cannot
  read, or the reverse. Legal, a consequence of keeping them disjoint, and nothing reports it.
- **One IdP.** Claim-to-role mapping is exercised against the enclave's identity source, not
  against the variety of real ones.
