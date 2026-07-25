# Quickstart validation: Developer Toolchain Scaffold

**Feature**: `specs/001-dev-toolchain`  
**Purpose**: Prove the contributor contract end-to-end after `feat/001-dev-toolchain` lands.  
**Not**: an implementation guide with full file contents (see `tasks.md`).

## Prerequisites

- Linux, macOS, or Windows WSL2
- `git`, `make`, and `uv` available on `PATH`
- Python 3.12+ available to `uv`

## Scenario A — Fresh clone green path (US1 / SC-001)

```bash
git clone <repo-url> brieve && cd brieve
uv sync
make check
```

**Expect**: `uv sync` completes without undocumented steps; `make check` exits `0`.

## Scenario B — Layout reservations (US2 / SC-004)

```bash
test -d src/core && test -d src/adapters && test -d src/surfaces
test -d tests/harness
test -d packs && test -d hooks && test -d providers && test -d portal
# portal must NOT have a Node toolchain yet
test ! -f portal/package.json
```

**Expect**: all directories present; harness README states semver/public-API reservation; extension READMEs state reserved purpose.

## Scenario C — Stub contracts (US3 / SC-003)

```bash
make conformance; echo exit:$?
make test-full; echo exit:$?
make dev-up; echo exit:$?
```

**Expect**: each command is defined; each exits non-zero with a clear stub message on stderr; none claim suite success.

## Scenario D — Pre-commit (US4)

```bash
pre-commit install
# introduce a deliberate formatting issue in a tracked Python file, then:
git add -A && git commit -s -m "test: pre-commit"
```

**Expect**: hooks run; commit is blocked or auto-fixed per hook policy before an unclean commit lands.

## Scenario E — Fast lane (SC-002)

Open a pull request against `main` (even a docs-only no-op on a fork).

**Expect**: CI workflow runs install + `make check` + secret scan + DCO + license steps; if the PR touches `specs/`, spec-artifact lint runs.

## Related contracts

- [contracts/make-targets.md](./contracts/make-targets.md)
- [contracts/ci-fast-lane.md](./contracts/ci-fast-lane.md)
