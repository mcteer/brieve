# Data model: 031 — a real model drives a governed run

## The visibility change (one set, one place)

| Role | Gains | Keeps hidden |
| --- | --- | --- |
| `operator` | `AUTHORITY_DENIED`, `AUTHORITY_REFUSED` | `AUTHORITY_ISSUED`, `AUTHORITY_EXPIRED`, grants/changes, reads |

No estate case's expected set changes → no `asker_role` changes → ADR-0059 span untouched (dated
prose note only). The focus row asserting the old premise is updated as the deliberate step.

## The plan subject (live lane)

| Property | Value |
| --- | --- |
| Suites | `must_deny`, `must_decline` only — the tool-choice pair |
| Roles scored | `ask` (as today) **and** `plan` |
| Verdicts | Same majority-of-three, same thresholds |
| Cell earned | `{pack}:anthropic/claude-opus@5:plan`, `qualified_by = "live"` — recorded post-run in the matrix comment; **never seeded** in variables.tf |

## The demonstration (seed → run → restore → prove)

| Step | Record | Posture |
| --- | --- | --- |
| Capture | matrix + demo binding originals, read from Vault | held in the script |
| Seed | matrix += live plan cell; `planner-agent` binding → that cell | Vault API, out of band, never state |
| Run 1 | vault-agent-ish clean task, ≤5 steps | real model chooses; trail shows TOOL_CHOSEN + credential ref |
| Run 2 | planner-agent, task worded toward `apply` | ≥1 refusal recorded by existing enforcement |
| Restore | rewrite both records from captured originals, in a trap | interruption-safe |
| Prove | re-read and compare to captured; then the choice conformance lane against fixtures | the script's own check is the enclave-state proof (the merge gate reads variables.tf, which never changed — stated honestly) |

## What deliberately does not change

Sealed core (no payload growth); the merge gate's assertion; the seeded variables.tf matrix; the
credential posture; the chooser's interception.
