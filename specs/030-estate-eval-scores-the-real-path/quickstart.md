# Quickstart: 030 — the estate eval scores the real path

Validation in the order that finds problems cheapest. Shapes in
[data-model.md](./data-model.md); rows in [contracts/conformance.md](./contracts/conformance.md).

## 1. The hermetic gates (run constantly)

```sh
make evals    # the blocking eval gate, over the now-tagged cases
make check    # includes the new visibility rows
```

Expected: an estate case without a role refuses to load; an operator case expecting an authority
reference refuses at scorer construction; a recording provider under an operator case receives no
authority records; the tagged suites pass with the same verdicts as before.

## 2. The decision record

```sh
git diff main -- docs/adr/0059-*.md packs/*/evals/estate_state.toml
```

Expected: every estate case tagged with the role that could ask it (vault 001/002/003/005 →
compliance-analyst, 004 → operator; terraform likewise per its expected sets), and ADR-0059
stating what a cell's estate evidence asserts — the matrix schema untouched, qualification
requiring every declared role's subset to pass.

## 3. The live re-run (US3) — named runner: Dan McTeer

```sh
make evals-smoke   # ~5 calls first, as always
make evals-live    # ~25 min, vendor cost
```

**Before running**: nothing about the deployed binding changes. **After**: the outcome decides the
two live cells —

- **Pass** → cells confirmed on corrected evidence; note the date in the matrix variables.
- **Fail for a role subset** → the affected cells are **withdrawn** in
  `infra/environments/dev/variables.tf` and applied. Withdrawal unbinds the deployed ask until an
  operator rebinds — the surface will refuse `unqualified_cell`, which is the mechanism working
  and is stated here so it is not discovered by a person mid-question.

## 4. What this closes and what stays open

Closes: the suite scoring records no grantable role could receive, and the unstated gap that let
it. Stays open, recorded: operator visibility of authority records (029's owed decision), and the
un-scored path pieces named in the suite headers.
