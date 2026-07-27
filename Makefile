# SPDX-License-Identifier: Apache-2.0

.PHONY: check conformance conformance-hermetic test-full dev-up dev-down dev-status enclave-verify enclave-digest-diff enclave-boundaries

# Every recipe names the adapters and surfaces extras so the gates cannot run in an
# environment that silently lacks the primary adapter or the northbound surface
# (specs/004-primary-adapter/research.md; specs/008-northbound-api T003).
UV_RUN := uv run --extra adapters --extra surfaces

# Inner-loop: lint, typecheck, unit tests
# Hermetic inner loop. Enclave-dependent tests are excluded by marker rather than by
# skipping inside them: a test that skips itself reports the same green as one that ran.
check:
	$(UV_RUN) ruff check src tests
	$(UV_RUN) ruff format --check src tests
	$(UV_RUN) mypy
	$(UV_RUN) pytest -m "not enclave"

# Adapter/provider conformance — merge-blocking (constitution Quality Gates).
# Rows in force are recorded per feature; see
# specs/004-primary-adapter/contracts/conformance-adapter.md (ADR-0047).
# Every row, including the seven durability rows (SC-009). Requires `make dev-up`:
# the durability lane runs against the real Vault and Postgres, and fails loudly rather
# than skipping when they are absent.
# The durability rows run as a SCHEDULED WORKLOAD holding their own attested identity —
# not on the host with a token. That is what makes them exercise the attestation chain
# rather than sit beside it. The honest cost is that failure output arrives through
# allocation logs; enclave-conformance streams them and surfaces the exit status.
conformance:
	$(UV_RUN) pytest tests/conformance --ignore=tests/conformance/durability -q
	@bash infra/bin/enclave-conformance
	$(UV_RUN) pytest -m enclave -q

# The subset that needs no enclave, for the fork-safe CI fast lane, which has no Vault
# Enterprise license and cannot stand one up. This is a real coverage gap and is
# recorded as one in specs/005-durable-execution/contracts/conformance-durability.md —
# the durability rows are merge-blocking for a human running them, not for CI.
# Two exclusions, and both are load-bearing for different reasons.
#
# The path ignore stays because the durability rows are parameterized memory/postgres and
# are NOT marker-excluded — their memory half is genuinely hermetic, so a marker would
# either drop coverage or force the postgres half into this lane.
#
# The marker is new, for tests/conformance/api, which holds hermetic AND enclave rows in
# one directory. Ignoring that path would drop the hermetic ones; collecting the enclave
# ones fails the lane, since they fail loudly rather than skipping when the enclave is
# absent. Neither exclusion alone is sufficient (specs/008-northbound-api T057a).
conformance-hermetic:
	$(UV_RUN) pytest tests/conformance --ignore=tests/conformance/durability -m "not enclave" -q

test-full:
	@echo "make test-full: stub — PR-tier suites not implemented yet" >&2
	@exit 2

# Local enclave, in ADR-0048's order: Terraform -> Vault -> Nomad -> harness.
# Idempotent — re-running when parts are already up is fine. Never re-initialises a
# Vault that already has a raft store; that would discard the trust configuration and
# invalidate the credentials in .env.
dev-up:
	@bash infra/bin/enclave-up

# Stops the stack. Destroys nothing — the named volumes hold the raft store and run state.
dev-down:
	@bash infra/bin/enclave-down

# SC-001: the tree produces identical configuration on every substrate. Runs against no
# infrastructure — a check needing both environments to exist is a check nobody runs.
enclave-digest-diff:
	@bash infra/bin/enclave-digest-diff

# The module boundary, both directions (contracts/module-interface.md) plus FR-004.
enclave-boundaries:
	@bash infra/bin/enclave-boundaries

# The full contract, asserted. dev-status is the quick glance; this is the guarantee.
enclave-verify:
	@bash infra/bin/enclave-verify

dev-status:
	@printf 'Nomad    ' ; curl -sf -o /dev/null --max-time 2 http://127.0.0.1:4646/v1/status/leader && echo up || echo down
	@printf 'Vault    ' ; \
		A=$$(grep '^VAULT_ADDR=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
		A=$${A:-http://127.0.0.1:8200} ; \
		C=$$(grep '^VAULT_CACERT=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
		S=$$(VAULT_ADDR=$$A VAULT_CACERT=$$C vault status 2>/dev/null | awk '/^Sealed/{print $$2}') ; \
		if [ "$$S" = "false" ]; then echo "up (unsealed)" ; elif [ "$$S" = "true" ]; then echo "up (SEALED — run make dev-up)" ; else echo down ; fi
	@printf 'Postgres ' ; nc -z 127.0.0.1 5432 2>/dev/null && echo up || echo down
