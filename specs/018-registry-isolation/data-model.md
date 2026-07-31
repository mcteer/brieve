# Phase 1 — Data model: 018 registry isolation

This feature persists nothing. What follows is what the gate reads, what it attempts, and how
it decides — which is where its correctness lives, because three of the four outcomes look
alike from the outside.

---

## BoundingPath — the *bounding record* the spec names

One name for the concept, two spellings for two purposes: the prose says **bounding record**
because that is what it is; the type is `BoundingPath` because what the code holds is the
path the record lives at. They are the same thing and nothing distinguishes them.

A control-plane path holding a record that decides what a run or a person may do. Derived
from the **deployed** policy and then **cross-checked against what exists**, because a
derivation from read grants is blind to anything outside them.

**Two sources, and the second is not a special case.**

| Half | Source | Why |
| --- | --- | --- |
| **Derived** | the read grants on the policy a run carries | every readable path in that jurisdiction is a bound it must not write |
| **Named** | an explicit list, each entry with its reason | the grant of authority itself, and what decides which grants a run receives. **A run holds no read access to any of them**, so no derivation from its grants can reach them |

The named half exists because derivation is *structurally* blind, not because the derivation
is incomplete. A run's limits are stated twice — once as a record the platform consults, once
as the grant the control plane enforces — and rewriting the second moves the bound without
touching the first. Analysis passes 1 and 2 both built schemes anchored on what a run can
see; pass 3 found that the most direct route to widening authority is a thing a run cannot
see at all.

**Source of the derived half**: the read grants on the policy a run actually carries. Every path a run may read
in that jurisdiction is a bound it must not be able to write — that equivalence is what makes
derivation sound, and it is why the set needs no separate list to fall out of date.

**And a cross-check, because the equivalence runs one way.** Every readable path is a bound;
not every bound is readable. A record placed where a run cannot read still bounds that run,
because the platform consults it whether or not the run can — so the set is also compared
against what **exists** in the control plane, and anything present but underived fails.
Analysis found this hole; 017 found the identical one in its own coverage after four passes.

| Field | Meaning |
| --- | --- |
| `path` | Where the record lives. |
| `grant` | What the deployed policy permits on it. Expected: read, never write. |

**Known members at planning time** — six, and the count is the point:

| Path | Decides |
| --- | --- |
| `harness-ceilings/*` | what a definition may ever do |
| `role-bindings/*` | what a person may delegate |
| `policies/*` | what narrows a definition mid-run |
| `model-matrix/*` | which models are qualified |
| `definition-bindings/*` | which packs a definition reaches |
| `claim-mappings/*` | which claims grant which role — **added the day the spec was written** |

The spec named three. A literal list would have been stale before the feature landed, which
is the whole argument for deriving it.

**Out of scope, and the distinction is load-bearing**: paths a run writes as its *work* —
secrets in its own space, configuration, product state. Those are governed *by* bounds rather
than *being* bounds. A run may spend the budget; it may not edit the budget. A check that
drifted across this line would forbid the platform's purpose while looking stricter.

---

## AttemptOutcome

What happened when the gate tried to write a bounding path. **Four outcomes, three of which a
naive implementation collapses into one.**

```
          write refused          write succeeded
                │                       │
      ┌─────────┴─────────┐             │
   read 200            read 403         │
      │                    │            │
      ▼                    ▼            ▼
   REFUSED           UNATTRIBUTABLE   PERMITTED
   evidence          proves nothing   the claim is false
```

| Outcome | Meaning | Verdict |
| --- | --- | --- |
| **REFUSED** | Write denied, and the same authority can read the path. The denial is about the *capability*. | **Pass** — the only outcome that is evidence |
| **UNATTRIBUTABLE** | Write denied, read also denied. The path may not exist, may be misspelled, or may be invisible. | **Fail** — a row that accepted this would pass with a typo |
| **PERMITTED** | The write succeeded. A run changed a record bounding it. | **Fail, distinctly** — and the gate removes what it wrote |
| **UNREACHABLE** | The control plane did not answer. | **Fail** — never a skip |

**Why UNATTRIBUTABLE exists**, verified against the running control plane during planning: a
mount that does not exist returns `403 permission denied`, in exactly the same words as a real
bounding path. Vault will not distinguish *forbidden* from *absent*, and that is correct of
Vault — disclosing which would leak the shape of the tree to an unauthorized caller. It is
fatal to a row that treats 403 as proof.

So `harness-ceilingz` — one letter wrong — passes a naive row, forever, having asserted
nothing. The read is the only thing that tells them apart.

---

## Two authorities, two purposes, never mixed

| Act | Authority | May assert |
| --- | --- | --- |
| **Assert a refusal** | a run's own, all of it | that a run cannot write |
| **Enumerate what exists** | administrator | what the set must contain |

An enumeration that drifted into asserting a denial would assert that an *administrator* was
refused, which is the opposite of interesting. The separation is why the cross-check above is
legal at all.

---

## RunAuthority

The authority a run actually holds while executing. **All of it, as deployed** — three
policies at planning time.

Not an administrator's, not a synthesized token carrying one grant. The claim under test is
*a run cannot write its own bounds*; proving that a single policy lacks the grant leaves open
whether some combination supplies it.

*This reverses the spec's original FR-003, corrected during planning.* The concern behind it —
that a refusal might come from the wrong cause — is real and is met by the read
discriminator above, which tests the **path** rather than the **grants**, and tests it
directly.

---

## GateRowState

What the governing record can say about a named conformance row. Two states existed where
three were needed, which is how this row went four features without a home.

| State | Means | Recorded where |
| --- | --- | --- |
| **In force** | The feature exists; the row blocks. | The feature's contract |
| **Deferred by decision** | An ADR chose to postpone it. | That ADR, cited at the skip |
| **Not yet applicable** | No feature carries it yet. Nothing deferred it; there is no ADR to cite. | The contract, with the reason |

The third is the addition. Registry isolation occupied it from 004 onward, unnamed — 004's
contract described the situation exactly and refused to invent a citation:

> *"This is a wording gap in ADR-0047, not a gap in 004… the fix is a PATCH to ADR-0047
> distinguishing deferred by decision from not yet applicable, rather than inventing
> citations to satisfy the clause."*

This feature moves the row from the third state to the first, which is what keeps the
amendment concrete rather than theoretical.

---

## What this model deliberately does not represent

- **Whether the bounding records are correct.** A ceiling that grants too much, written by
  the reviewed configuration path, is invisible here. This asserts that a *run* cannot change
  it — not that it is right.
- **Writes through tools.** A run calling a pack's write tool is the product working. The
  tool's own credential does that writing, in a different jurisdiction (ADR-0044). Nothing
  here touches it.
- **Whether the read grant should exist.** The gate depends on it to attribute refusals. If
  it were removed, every row would fail — correctly, but reporting *"could not attribute"*
  rather than *"isolation broke"*, and the two must not read alike.
