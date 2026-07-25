# SPDX-License-Identifier: Apache-2.0

.PHONY: check conformance test-full dev-up

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

dev-up:
	@echo "make dev-up: stub — local stack not implemented yet; will not mutate remote environments" >&2
	@exit 2
