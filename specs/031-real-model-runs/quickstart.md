# Quickstart: 031 — a real model drives a governed run

**Stated cost bound (FR-009/SC-007)**: live lane +~10 min (plan subject); demonstration ≤15
vendor calls (2 runs × ≤5 steps + retries). Nothing below runs a vendor call except §2 and §3.

## 1. Hermetic (constantly)

```sh
make check   # visibility rows; focus row updated; agreement row untouched and passing
```

## 2. Earn the plan cell

```sh
make evals-smoke && make evals-live   # now scores must_deny/must_decline under ask AND plan
```

Exit 0 ⇒ plan-role evidence exists; the cell may be seeded by the demo (out of band) as
`qualified_by = "live"`, and the matrix variables gain a dated comment.

## 3. The demonstration

```sh
bash infra/bin/model-run-demo
```

Seeds the live plan cell + demo binding (out of band, captured first), dispatches the clean run
and the over-reach run, restores, proves restoration by comparison, then re-runs the choice lane
against fixtures. Prints: the trail lines (TOOL_CHOSEN with the real model, the credential
reference, the refusal), and finally asks "which runs were denied?" as the operator — the answer
must cite the demo's refusal (US4 closed end to end).

## 4. The full gate

```sh
make conformance   # unchanged, no vendor, fixture cells only
```
