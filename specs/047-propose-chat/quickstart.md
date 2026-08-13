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
2. Force plan failure in fixture/enclave harness → Plan failed; no PR.
3. Force judge deny → Judge failed; no PR.

## Live / enclave

Named runner (Dan): E1–E3 in `contracts/conformance-propose-chat.md` against the enclave
and the owned demo repository. Record outcomes on the implementation PR.
