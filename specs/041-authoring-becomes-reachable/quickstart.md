# Quickstart: Authoring becomes reachable

How to see this feature working, from hermetic rows to a real pull request. Row IDs refer to
[contracts/conformance-authoring-reachable.md](contracts/conformance-authoring-reachable.md);
entities to [data-model.md](data-model.md).

## Prerequisites

- The local enclave up: `make dev-up` (Terraform → Vault → Nomad → harness). On Apple Silicon
  confirm the Nomad node advertises real CPU (`infra/nomad/client.hcl` sets
  `cpu_total_compute`; 040's repair — a 24 MHz node cannot place these allocations).
- **Operator-seeded, once** (not provisioned by this feature):
  - A GitHub App installed on a maintainer-owned target repository, its private key seeded at
    `harness-authority/data/authoring/vcs-app` (ADR-0062).
  - The target repository named in the request's `owned_repositories`.
- `git` and `gh` present in the proposer task image (R8 — the lane fails `tooling_missing`
  rather than skipping if absent).
- A qualified `write` cell bound (see step 2); model credential seeded (re-seed after any
  `terraform apply` — it clobbers the KV generation).

## 1 — Hermetic proof (every PR, no estate)

```sh
make check                    # unit rows incl. ledger sweep (A5) and product-mapping guard (A17)
make conformance-hermetic     # A-rows: reachability, refusal layers, acquisition, publish seams
```

Expected: A1–A21 green; A4's rigged construction demonstrably fails when enabled; 038's rows
pass with an empty diff over their files (A20).

## 2 — Qualify and bind the `write` cell (once per estate)

```sh
make eval-authoring           # mechanical scorer over evals/authoring/corpus.toml (ADR-0063)
```

Then add the dated `write` cells (both packs × Sonnet 5) to `model_matrix_cells` in the trust
fabric and apply. Expected: `resolve_write_cell` returns the cell; before binding, a dispatched
authoring run stops `unqualified_cell` (A18) — run it once unbound to see the refusal, which is
SC-011's other half.

## 3 — The real thing (enclave lane; named runner: Dan)

Dispatch an authoring run against the target repository (request names `target_repository`,
task, pack). Watch:

```sh
nomad job status authoring-tier          # analyzer (prestart) exits, proposer runs
```

Expected outcomes, in order:

1. **Acquisition**: a shallow checkout appears in the dispatcher's per-run directory;
   `NOMAD_META_subject_path` points at it (A10). A bogus repository name refuses
   `subject_unreachable` with no workspace created (A11).
2. **Analyzer**: `TOOL_CHOSEN` records name `read_subject`/`author_file` with model-supplied
   arguments; the workspace holds authored files; the checkpoint lands; **no attested identity
   in this task** — E3's credential read fails structurally.
3. **Proposer**: continues (no resume attempt consumed — E4), containment passes, and a real
   PR opens on the target repository.
4. **Verify E1**: the PR's file digests match the artifact's; its description carries the
   model rationale plus correlation ID, consulted paths, digests (and truncation note only if
   the read was partial); the trail walks prompt → hooks → publish → `PROPOSAL_OPENED` under
   one correlation ID.
5. **Verify E2**: re-dispatch the same request; `gh pr list --head <branch>` still shows one
   PR, and the second result carries `reused=true`.

## 4 — The failure modes worth seeing once

- Kill the proposer mid-publish → revival resolves via the observer, no second PR (A14).
- Block `github.com` from the proposer → the run suspends against product `github`; restore
  and watch the sweeper revive it (SC-012).
- Ask for a run whose ceiling omits `author_file` → refused for the ceiling, not the
  vocabulary (A2's middle layer).

## Cleanup

Row-opened PRs land on `branch_for(...)` branches of the dedicated target repository and are
never merged; close them or let E2's reuse keep the count at one.
