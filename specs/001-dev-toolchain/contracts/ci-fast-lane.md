# Contract: CI fast lane

**Feature**: `specs/001-dev-toolchain`
**Audience**: Maintainers, contributors, GitHub Actions
**Workflow path (planned)**: `.github/workflows/ci.yml`

## Trigger

- `pull_request` against `main` (required)
- Optional: `push` to `main`

## Jobs / steps (logical)

| Step | Required | Notes |
| --- | --- | --- |
| Checkout | yes | Full history if DCO needs it |
| Install toolchain | yes | `uv` + `uv sync --frozen` (or equivalent) |
| Inner-loop check | yes | Equivalent to `make check` |
| Secret scan | yes | e.g. gitleaks; no privileged tokens required |
| DCO verification | yes | All commits in the PR carry `Signed-off-by` |
| License compliance | yes | Fail on disallowed licenses per CONTRIBUTING |
| Spec-artifact lint | conditional | When the PR touches `specs/**` |

## Invariants

1. Runs on fork PRs without repository secrets.
2. Does not call live model providers or product estates.
3. Does not enable GitHub branch protection by itself (maintainer settings).
4. Class-gated suites (conformance, evals, a11y) are **out of scope** for this workflow in 001.

## Related docs

- [docs/development/testing.md](../../../docs/development/testing.md) — CI tiers (Fast)
- [../spec.md](../spec.md) — FR-006, SC-002, SC-005
