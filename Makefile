# SPDX-License-Identifier: Apache-2.0

# `evals` is .PHONY twice over: it is a recipe, and a DIRECTORY named evals/ exists at
# the repository root — without the declaration, make reports the seed set 'up to date'
# and the gate never runs, which is a skip wearing a build system's clothes.
.PHONY: check mcp-surface-up conformance conformance-hermetic eval-authoring test-full dev-up dev-down dev-status enclave-verify enclave-digest-diff enclave-boundaries a11y portal-up evals evals-live evals-smoke evals-relevance-qualify

# Every recipe names the adapters and surfaces extras so the gates cannot run in an
# environment that silently lacks the primary adapter or the northbound surface
# (specs/004-primary-adapter/research.md; specs/008-northbound-api T003).
UV_RUN := uv run --extra adapters --extra surfaces --extra portal

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
# Step 1 runs only what a host process legitimately can. The durability rows and the
# enclave-marked API rows both hold their OWN workload identity, so running them here
# would fail for the right reason and the wrong purpose — a host process has no attested
# identity and should not be able to reach the state store. They run in the allocation.
mcp-surface-up:
	@bash infra/bin/mcp-surface-up

conformance:
	# `not live_model` is 020's, and it is FR-011 at the lane rather than in a row: the
	# merge gate never calls a vendor. 020's fidelity row (FR-011a) is deliberately outside
	# it, behind a named runner, because a stand-in nobody checks is what this feature
	# exists to end — and it fails loudly rather than skipping, which would fail this lane
	# on every machine without a provider credential.
	$(UV_RUN) pytest tests/conformance --ignore=tests/conformance/durability -m "not enclave and not live_model" -q
	@bash infra/bin/enclave-conformance
	$(UV_RUN) pytest -m enclave -q
	# The rows that must run HERE rather than in the allocation: they drive the
	# scheduler, or hold an admin token the allocation deliberately lacks.
	#
	# Named by DIRECTORY, and 010 had to add its own — a marker alone does not run a row
	# that no lane collects. `tests/conformance/identity` was invisible to this line while
	# passing everywhere it was asked to run, which is the same shape as the rows the
	# in-allocation lane could not see.
	#
	# 014 adds `tests/conformance/durability`, and the trap there is subtler than the
	# missing directory 010 paid for. That directory IS named by a lane — the
	# in-allocation one — but it runs with `-m "not host_enclave"`, so a row that drives
	# the scheduler is DESELECTED there, and no other lane could see it either: the first
	# line of this recipe ignores the path, and `pytest -m enclave` above reads
	# `testpaths`, which is tests/unit and tests/component. Ten dispatched-resume rows
	# would have passed when run by hand and been invisible to this gate — the defect 014
	# exists to fix, rebuilt inside the gate that was meant to prove it fixed. "Already
	# named by a lane" is not the same question as "named by a lane that will run it".
	#
	# The enclave's coordinates come from .env because `uv run` does not read it, and
	# 011's divergence rows read the trail as an OPERATOR — a host process holds no
	# attested identity, so the alternative is a row that cannot run where it belongs.
	# Passed on the command line rather than exported: it stays scoped to this one lane.
	@A=$$(grep '^VAULT_ADDR=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
	C=$$(grep '^VAULT_CACERT=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
	T=$$(grep '^VAULT_ROOT_TOKEN=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
	VAULT_ADDR=$$A VAULT_CACERT=$$C VAULT_TOKEN=$$T \
	  $(UV_RUN) pytest tests/conformance/api tests/conformance/identity tests/conformance/packs tests/conformance/durability tests/conformance/evidence tests/conformance/authority tests/conformance/endorsed -m host_enclave -q
	#
	# 018 adds `tests/conformance/authority`, and it very nearly repeated 010's mistake in
	# the feature built to end exactly this class of gap. Its rows passed by hand and its
	# conformance contract SAID this line already enumerated them. No lane collected the
	# directory: the first recipe line runs `-m "not enclave"` and these rows are marked
	# enclave, and nothing else names the path. Twelve rows asserting that a run cannot
	# widen its own authority, green on demand and invisible to the gate.
	#
	# Found by reading this comment block, which is the third time it has paid for itself.
	#
	# 045 adds `tests/conformance/endorsed`, wired at birth for 010's reason, and it is
	# the FIRST directory to need BOTH lanes. Its store rows hold a workload identity and
	# run in the allocation; its transport row runs a real `git clone` and the allocation's
	# image has no git, which the authoring tier already refused to fix with a runtime
	# `apt-get`. So the split is by what each environment can do — and naming the directory
	# on only one line would have left the transport, the feature's single outbound
	# operation, exercised by nothing while everything downstream of it was green.
	#
	# 012's containment lane. Named here in the same change that created the directory —
	# 010 lost a whole feature's rows to a directory no lane enumerated, and the fix is to
	# wire it at birth rather than to remember later.
	#
	# 024's answering lane is deliberately NOT on the host_enclave line above, and an
	# earlier draft of this change put it there. Its rows carry no `host_enclave` marker,
	# so that line deselected all five while reading as though it ran them — an inert
	# entry is worse than no entry, because it answers "is this directory wired?" with a
	# yes. They are swept by the FIRST line of this recipe, which runs every directory
	# under tests/conformance that is not enclave-marked, and that is the whole coverage
	# story for them. The trap this file documents three times is about directories that
	# line CANNOT see; this is not one.
	$(UV_RUN) pytest tests/conformance/portal -q
	#
	# 013's pack lane. Its HERMETIC rows need no wiring — the first line of this recipe
	# collects `tests/conformance` wholesale — so only the host_enclave line above needed
	# the directory added, and it was added in the change that created it. Recorded here
	# because "already collected" is exactly the assumption 010 made and paid for: the
	# distinction is that line 34 names a tree and the host line names directories.
	#
	# 017's deployment lane, and it is deliberately NOT a pytest line. Those all run before
	# the API and the portal are stood up, so rows there would assert against surfaces that
	# do not exist yet and fail on every invocation — FR-006 makes an absent process a
	# failure, never a skip. The runner below stands them up first and enumerates the
	# directory itself, which is what "named by a lane that WILL RUN IT" actually requires;
	# 010 lost a feature's rows to a directory no lane named, and 014 nearly repeated it
	# with a directory a lane named and deselected.
	#
	# LAST, so the conformance batch job above has completed and released its reservation
	# before two more services are submitted. Ordering is a property of this position rather
	# than of a workflow file nobody runs locally — registering these surfaces at bring-up
	# once left that batch job unplaceable and the merge-blocking durability rows never ran.
	@bash infra/bin/deployment-conformance
	#
	# 019's served-surface lane. NOT the host_enclave pytest line above: these rows drive a
	# running process, and a directory named there would be collected with nothing serving —
	# which is why `tests/conformance/deployment` is absent from it too.
	@bash infra/bin/mcp-surface-conformance
	#
	# 020's choice lane. Its own runner rather than another directory on the host_enclave
	# pytest line above, because its preconditions fail SILENTLY: a dispatched choice row
	# against an enclave with no `model-matrix` record refuses every run for
	# `unqualified_cell`, which is indistinguishable from FR-006 working correctly. The
	# script checks the record exists and says so in one sentence.
	#
	# The hermetic half of `tests/conformance/choice` needs no wiring — the first line of
	# this recipe collects the tree — which is what makes `make conformance-hermetic` pass
	# with no provider and no enclave (FR-011, SC-006).
	@bash infra/bin/choice-conformance
	#
	# 021's reports lane. Its own runner because `tests/conformance/reports` holds BOTH
	# hermetic and dispatched rows: naming the path on the host_enclave line above would
	# collect the hermetic ones twice, and a marker mismatch would deselect exactly the
	# dispatched ones — which is the failure 010, 014 and 018 each paid for.
	@bash infra/bin/reports-conformance

# The accessibility gate (012, FR-020a). Its own target because it is its own DISCIPLINE:
# every other gate here asserts something about a process, and this one asserts something
# about a rendered interface, which needs a browser no other lane has.
#
# `playwright install` is idempotent and quick once the browser is cached. It is in the
# recipe rather than in a setup document because a gate that depends on someone having read
# something is a gate that does not run.
#
# The ruleset is VENDORED and pinned (tests/a11y/vendor). What this gate cannot assert is
# recorded in specs/012-conversational-portal/contracts/conformance-portal.md with a named
# human runner — a green run here is not a conformance claim.
# The surfaces a person uses, separate from `dev-up` on purpose — see infra/bin/portal-up.
portal-up:
	@bash infra/bin/portal-up

# Clears what a FAILED deployment lane left standing. Named by that lane's own failure
# message, so it has to exist — a message pointing at a missing command is the one output
# someone reads when the gate is already red. Stops only MARKED surfaces; a portal you
# brought up yourself is untouched.
deployment-down:
	@bash infra/bin/deployment-down

a11y:
	uv run --extra surfaces --extra portal --extra a11y playwright install chromium
	uv run --extra adapters --extra surfaces --extra portal --extra a11y pytest tests/a11y -q

# The eval gates (013, Principle VIII). `evals` scores FIXTURES and blocks — it is part
# of what a merge must pass, and it is hermetic so it never fails for reasons unrelated to
# the change under review. `evals-live` scores a REAL model: it needs a paid credential
# (EVAL_PROVIDER_API_KEY) and is non-deterministic, so it is never in a blocking lane and
# has a named runner (plan.md: Dan, before merge, per-cell outcome recorded in
# specs/013-capability-packs/contracts/conformance-packs.md).
evals:
	$(UV_RUN) pytest tests/component/test_eval_gates.py tests/component/test_judge_chain.py -q

# The credential comes from .env's ANTHROPIC_API_KEY, passed on the command line as the
# name the lane reads — scoped to this one invocation, never exported, on the same pattern
# as the conformance recipe's Vault coordinates. The directory is NAMED because it sits
# outside `testpaths` (like tests/a11y): a bare `pytest -m live_model` collects nothing,
# which is a gate that cannot run reporting an empty pass.
# TWO CALLS BEFORE ONE HUNDRED AND EIGHTY. Building the live lane took six full runs and
# four of them existed only to surface a HARNESS defect — a truncating token budget, a
# rejected temperature, a subject that did not know its own scope, a judge starved of
# context. Every one was visible in a single call with the response printed. Run this
# first; `evals-live` is for qualifying cells, not for finding out whether the harness
# works. See tests/evals_live/smoke.py for the full accounting.
evals-smoke:
	@K=$$(grep '^ANTHROPIC_API_KEY=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
	[ -n "$$K" ] || { echo "no ANTHROPIC_API_KEY in .env" >&2; exit 1; } ; \
	EVAL_PROVIDER_API_KEY=$$K uv run --extra adapters --extra surfaces --extra portal --extra evals \
	  python tests/evals_live/smoke.py

# Qualifying a RELEVANCE judge against the human-labelled seed set (043). Separate from
# `evals-live` on purpose: that lane qualifies answering cells and takes ~28 minutes, and
# this one asks a different question of a different role. THE LANE BINDS NOTHING — it prints
# two numbers and exits; promoting the cell stays a human act (ADR-0052).
# Run the rigged candidate too, and expect it to be REFUSED:
#   make evals-relevance-qualify ARGS=--rubber-stamp
evals-relevance-qualify:
	@K=$$(grep '^ANTHROPIC_API_KEY=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
	[ -n "$$K" ] || { echo "no ANTHROPIC_API_KEY in .env" >&2; exit 1; } ; \
	EVAL_PROVIDER_API_KEY=$$K uv run --extra adapters --extra surfaces --extra portal --extra evals \
	  python tests/evals_live/relevance_qualify.py $(ARGS)

evals-live: evals-smoke
	@K=$$(grep '^ANTHROPIC_API_KEY=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
	[ -n "$$K" ] || { echo "no ANTHROPIC_API_KEY in .env; the live lane cannot run" >&2; exit 1; } ; \
	EVAL_PROVIDER_API_KEY=$$K uv run --extra adapters --extra surfaces --extra portal --extra evals \
	  pytest tests/evals_live -m live_model -q


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
#
# The `live_model` exclusion is 020's, and it is FR-011 stated at the lane rather than in a
# row: a gate that cannot run without a vendor is a gate that stops running. The fidelity row
# that keeps 020's double honest (FR-011a) costs a real provider call and fails loudly rather
# than skipping when the credential is absent — which is right for a row with a named runner
# and wrong for a blocking lane, where it would turn every fork PR red for having no API key.
conformance-hermetic:
	$(UV_RUN) pytest tests/conformance --ignore=tests/conformance/durability -m "not enclave and not live_model" -q

# The `write` role's correctness gate (038, FR-018). TWO NUMBERS, never one — product tooling
# and reference comparison catch different failures, and collapsing them hides which occurred.
#
# RUNS IN THE ENCLAVE LANE, which already installs the binary (`install_hashicorp terraform` in
# .github/workflows/enclave.yml). Research R10 framed this as new tooling and never measured
# that precedent; what is actually new is the pinned provider set, which comes from a lock file
# and a CI cache rather than from vendored binaries — provider binaries run to hundreds of
# megabytes per platform and this repository should not carry them.
#
# IF THE TOOLING CANNOT RUN, THIS FAILS. `score_corpus` raises `UnrunnableSuite` rather than
# degrading to a formatter-only check while still reporting "validated" — 012 shipped the
# skip-reads-as-green shape twice, and this is the costume it would wear here.
eval-authoring:
	$(UV_RUN) pytest tests/conformance/authoring -q -k qualification
	@command -v terraform >/dev/null || { \
	  echo "eval-authoring: terraform is not on PATH. This gate FAILS rather than skipping:" ; \
	  echo "  a lane that skips reads as green, and 'validated' would then mean 'not checked'." ; \
	  exit 1 ; \
	}
	@echo "eval-authoring: product tooling present; corpus gate ran"

# The LIVE `write` qualification (041, T019; ADR-0063). Two gates, two numbers, never one.
#
# 038 built every piece of the scoring and nothing produced artefacts to score — `properties_of`
# is caller-supplied and its only implementations were literal maps inside rows. This lane is
# what points the machinery at a model.
#
# IT BINDS NOTHING. Promotion is a separate, human decision: this prints the evidence, and a
# maintainer decides whether a cell is earned. A lane that promoted what it measured would be
# grading its own homework.
evals-authoring-live:
	@K=$$(grep '^ANTHROPIC_API_KEY=' .env 2>/dev/null | cut -d= -f2- | tr -d '"') ; \
	[ -n "$$K" ] || { echo "no ANTHROPIC_API_KEY in .env" >&2; exit 1; } ; \
	command -v terraform >/dev/null || { \
	  echo "evals-authoring-live: terraform is not on PATH. Gate one is the product's OWN" >&2 ; \
	  echo "  tooling; without it this FAILS rather than degrading to a syntax check." >&2 ; \
	  exit 1 ; \
	} ; \
	EVAL_PROVIDER_API_KEY=$$K uv run --extra adapters --extra surfaces --extra evals \
	  python tests/evals_live/authoring.py

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
