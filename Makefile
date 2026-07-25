# SPDX-License-Identifier: Apache-2.0

.PHONY: check conformance test-full dev-up

# Inner-loop: lint, typecheck, unit tests
check:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run mypy
	uv run pytest

# Reserved contracts — fail closed until real suites/stack exist (FR-005)
conformance:
	@echo "make conformance: stub — conformance suite not implemented yet" >&2
	@exit 2

test-full:
	@echo "make test-full: stub — PR-tier suites not implemented yet" >&2
	@exit 2

dev-up:
	@echo "make dev-up: stub — local stack not implemented yet; will not mutate remote environments" >&2
	@exit 2
