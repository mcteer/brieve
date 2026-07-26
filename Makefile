# SPDX-License-Identifier: Apache-2.0

.PHONY: check conformance test-full dev-up dev-down dev-status

# Every recipe names the adapters extra so the gates cannot run in an environment
# that silently lacks the primary adapter (specs/004-primary-adapter/research.md).
UV_RUN := uv run --extra adapters

# Inner-loop: lint, typecheck, unit tests
check:
	$(UV_RUN) ruff check src tests
	$(UV_RUN) ruff format --check src tests
	$(UV_RUN) mypy
	$(UV_RUN) pytest

# Adapter/provider conformance — merge-blocking (constitution Quality Gates).
# Rows in force are recorded per feature; see
# specs/004-primary-adapter/contracts/conformance-adapter.md (ADR-0047).
conformance:
	$(UV_RUN) pytest tests/conformance -q

test-full:
	@echo "make test-full: stub — PR-tier suites not implemented yet" >&2
	@exit 2

# Local enclave, in ADR-0048's order: Terraform -> Vault -> Nomad -> harness.
# Idempotent — re-running when parts are already up is fine. Never re-initialises a
# Vault that already has a raft store; that would discard the trust configuration and
# invalidate the credentials in .env.
dev-up:
	@bash infra/dev-enclave/dev-up.sh

# Stops the stack. Destroys nothing — the named volumes hold the raft store and run state.
dev-down:
	@bash infra/dev-enclave/dev-down.sh

dev-status:
	@printf 'Nomad    ' ; curl -sf -o /dev/null --max-time 2 http://127.0.0.1:4646/v1/status/leader && echo up || echo down
	@printf 'Vault    ' ; S=$$(VAULT_ADDR=http://127.0.0.1:8200 vault status 2>/dev/null | awk '/^Sealed/{print $$2}') ; \
		if [ "$$S" = "false" ]; then echo "up (unsealed)" ; elif [ "$$S" = "true" ]; then echo "up (SEALED — run make dev-up)" ; else echo down ; fi
	@printf 'Postgres ' ; nc -z 127.0.0.1 5432 2>/dev/null && echo up || echo down
