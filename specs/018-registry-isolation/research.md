# Phase 0 — Research: 018 registry isolation

Probed against the running control plane, not inferred. One finding settles the design, one
contradicts a requirement in the spec, and one shrinks the feature.

---

## R1 — `403 permission denied` does not mean what a naive row would take it to mean

**Decision**: A refusal counts only when the same authority can **read** the path. Read 200
plus write 403 is evidence; write 403 alone is not.

**Finding**: A token carrying `harness-authority-read` was pointed at four real bounding
paths and two fabrications. Every one answered identically:

| Path | Write |
| --- | --- |
| `harness-authority/data/harness-ceilings/planner-agent` | `403 permission denied` |
| `agent-registry/registration/display-name/probe-x` | `403 permission denied` |
| `harness-authority/data/role-bindings/operator` | `403 permission denied` |
| **`no-such-mount/data/x`** — a mount that does not exist | **`403 permission denied`** |

So a row with a typo in its path — `harness-ceilingz` — passes, having proven nothing.
**The read distinguishes them:**

| Path | Read |
| --- | --- |
| `harness-authority/data/harness-ceilings/planner-agent` | `200` |
| `harness-authority/data/role-bindings/operator` | `200` |
| `no-such-mount/data/x` | `403` |
| `harness-authority/data/harness-ceilingz/typo` (typo) | `403` |

**Rationale**: This is FR-005's "refused for an unrelated reason" arriving immediately and
concretely. Vault deliberately does not distinguish *forbidden* from *absent* — disclosing
which would leak the shape of the tree to an unauthorized caller. That is correct of Vault
and fatal to a row that reads 403 as proof.

**Alternatives considered**:
- *Trusting 403 alone.* Rejected — demonstrated above to pass against a nonexistent mount.
- *Checking the path against configuration.* Rejected — that re-reads Terraform, which is
  the argument this feature exists to replace with evidence.

---

## R2 — FR-004 is wrong, and the spec should be corrected

**Decision**: Use the authority **a run actually holds**, not a synthesized token carrying
only the bound under test.

**Finding**: The `agent-run` role issues tokens carrying three policies:

```
['agent-pack-secrets', 'harness-database', 'harness-authority-read']
```

FR-004 says the authority "MUST carry **only** the bound under test, so a refusal cannot be
caused by the absence of an unrelated grant." Applied here that is backwards. The
constitution's claim is *a run cannot write its own bounds* — about the authority a run
holds, all of it. Stripping it to one policy proves something narrower: that one policy does
not grant write, which leaves open whether some combination does.

**The concern behind FR-004 was real and is met differently.** It was written against a
refusal that came from the wrong cause; R1's read-200 check addresses exactly that, and
addresses it better, because it discriminates on the *path* rather than on the *grants*.

**This is a correction to the spec, not a planning decision**, and it is recorded here rather
than applied silently. FR-004 should be rewritten to require the run's real authority.

**Alternatives considered**:
- *Both — a single-policy token and the full run authority.* Rejected as redundant once R1
  lands: two assertions where the second subsumes the first.
- *A root token.* Rejected, obviously — it would be refused by nothing and prove nothing.

---

## R3 — The refusal already holds, on every path the spec names

**Decision**: Build the rows. Expect them green on the first run.

**Finding**: All four probed writes were refused by the live control plane under a real run's
authority, including one path the spec did not name — `claim-mappings`, added by the
identity work earlier today, which is a bounding record by the spec's own definition (it
decides which claims grant which role, so it decides what a person may delegate).

**Rationale**: The spec's assumption said this feature is "expected to observe a refusal that
already occurs — and if it does not, that is a far more serious finding than a missing test."
It occurs. What is missing is only the observation, which is R4's whole point.

**Alternatives considered**: None. This is a measurement, not a choice.

---

## R4 — Four bounding record kinds, not three, and the fourth arrived today

**Decision**: Enumerate bounding paths from the deployed policy rather than from a list in
the test suite.

**Finding**: The spec names three kinds. `harness-authority-read` grants read on **five**
path patterns: `harness-ceilings`, `role-bindings`, `policies`, `model-matrix`, and
`definition-bindings` — plus `claim-mappings`, added earlier today. Each decides something
about what a run or a person may do, and a run must be refused write on all of them.

A hand-maintained list in the suite would already be two entries stale on the day it is
written. 017 paid for exactly this: its coverage mechanism was fail-open until analysis found
that a process nobody enrolled was invisible, and the fix was to enumerate from the
deployment and fail on anything unplaced.

**Rationale**: The policy is the authoritative statement of what a run may read, and every
readable bounding path is one it must not write. Deriving the set from it means a path added
to the policy is covered without anyone remembering.

**Alternatives considered**:
- *A literal list in the test module.* Rejected — stale on arrival, and it is the failure
  mode 017's FR-005a exists to prevent.
- *Enumerating from Terraform source.* Rejected — reading configuration is what this feature
  replaces. Read the **deployed** policy.

---

## R5 — The amendment and the gate ship together

**Decision**: One change, one pull request.

**Finding**: The spec's checklist flagged the choice. ADR-0047's amendment names two states
for a row not in force, and its worked example is this row moving to in-force. Landing the
amendment alone leaves the row still unowned and the example hypothetical; landing the gate
alone leaves the next row in the same ambiguity 004 documented and declined to paper over.

**Rationale**: FR-021 already requires the row to move to in-force *with* the amendment —
"an amendment that only described states without placing the row that prompted it would leave
the situation it exists to end."

**Alternatives considered**: Two pull requests. Rejected on FR-021, which settles it.

---

## Residual unknowns

**None blocking.** One thing deliberately left to implementation: whether the read-200 check
belongs in every row or in a shared helper. That is a code-organisation choice, and stating
it here would be a plan pretending to be an implementation.
