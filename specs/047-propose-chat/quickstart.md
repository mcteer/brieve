# Quickstart: Propose chat (047)

## Hermetic

```bash
uv sync
make check
# once rows exist:
uv run pytest tests/conformance/propose/ -q
```

## Dev stack walkthrough

```bash
deploy/local/stack.sh up   # or make dev-up + portal-up
# Ensure demo repo is in the owned-repositories allowlist for the operator role
open https://127.0.0.1:8082/propose
# Paste https://github.com/mcteer/brieve-demo and a Terraform task
# Observe phase strip: Research → … → Propose
# Success shows PR URL
```

## Failure drills

1. Paste a repo not in the allowlist → refuse; no PR.
2. `HARNESS_TERRAFORM_PLAN_FAIL=1` (hermetic) or a tree that makes `terraform plan` exit 1
   → Write failed with a plan reason; no PR. Live E2 is the named-runner enclave row.
3. `HARNESS_JUDGE_DENY=1` → Judge failed; no PR.

## Live / enclave

Named runner (Dan): E1–E3 in `contracts/conformance-propose-chat.md` against the enclave
and the owned demo repository. Record outcomes on the implementation PR.

**E3 walkthrough**: start Build on an owned demo repo; without a full page reload that
clears the run, the phase strip must show at least one mid-run transition (for example
Research → Plan, or Write → Judge) before the PR URL or a phase failure.
