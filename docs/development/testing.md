# Testing Guide

How to test a governed agent runtime. This guide is prescriptive because the usual
instincts — mock everything, assert on output text, retry until green — produce tests
that pass while the guarantees underneath them rot.

**Contents**

- [Two lanes: tests and evals](#two-lanes-tests-and-evals)
- [Test taxonomy](#test-taxonomy)
- [The test harness](#the-test-harness)
- [Governance assertions](#governance-assertions)
- [Testing hooks](#testing-hooks)
- [Testing tools](#testing-tools)
- [Durability and fault injection](#durability-and-fault-injection)
- [Multi-tenant isolation](#multi-tenant-isolation)
- [Adversarial testing](#adversarial-testing)
- [Conformance suites](#conformance-suites)
- [Writing evals](#writing-evals)
- [Coverage policy](#coverage-policy)
- [CI tiers](#ci-tiers)
- [Anti-patterns](#anti-patterns)

## Two lanes: tests and evals

The single most important rule in this repository:

> **Tests are deterministic. Evals are statistical. They never mix.**

A test that calls a live model is not a test — it is a slow, flaky eval wearing a
test's clothes, and it will be quarantined. Tests run with stub models, fixed clocks,
seeded randomness, and fake backing services; the same input produces the same result
on every machine, forever. Their job is to prove that *mechanisms* behave: that a hook
denies, that a token is exchanged, that a correlation ID propagates, that a resume
re-authenticates.

Evals exercise *judgment* — whether the agent plans sensibly, writes correct HCL,
cites accurately, declines what it should. Model behavior varies between runs, so
evals are scored across repetitions against thresholds, not asserted once. They gate
promotion of packs, prompts, models, and policies; they never gate a core unit test
run, and they never appear in the fast CI lane.

If you are unsure which you are writing, ask: *would a different-but-reasonable model
response make this fail?* If yes, it is an eval.

## Test taxonomy

| Lane | Scope | Models | Speed | Runs |
| --- | --- | --- | --- | --- |
| **Unit** | One module, no I/O | none | ms | every push |
| **Component** | One subsystem with fakes (hook pipeline, registry, token exchange) | stub | ms–s | every push |
| **Contract** | A seam's interface, both directions | stub | s | every push |
| **Conformance** | A provider or adapter implementation against the shared suite | stub | s–min | every PR touching it — merge-blocking, in the fast lane (`make conformance`) |
| **Integration** | Real backing services (Postgres, dev-mode identity fabric, local MCP servers) | stub | min | every PR |
| **Scenario** | Multi-step runs end to end, including approvals and resumption | scripted | min | every PR |
| **Fault injection** | Kill, expire, partition, duplicate, drain | scripted | min | every PR |
| **Adversarial** | Injection, exfiltration, scope escape, confused deputy | scripted | min | every PR |
| **Performance** | Latency and context budgets | stub/real | min | nightly |
| **Eval** | Agent judgment quality | real | min–hr | promotion gates, nightly |

"Scripted" means a `FunctionModel`-style stub that returns a fixed sequence of tool
calls and messages — deterministic agent behavior without a model provider.

## The test harness

`tests/harness/` provides the fakes. Use them; do not hand-roll mocks for these.

```python
from tests.harness import (
    fake_identity_fabric,   # registration, ceilings, token exchange, Control Groups
    fake_product_api,       # Terraform/Vault/VCS endpoints with recorded semantics
    fake_registry,          # tool registry with lifecycle states
    stub_model,             # deterministic model: fixed responses
    scripted_agent,         # deterministic tool-call sequences
    frozen_clock,           # deterministic time; advance() for TTL and expiry
    fault,                  # kill, partition, expire, delay, duplicate
    capture_audit,          # in-memory audit sink with chain verification
    capture_spans,          # OTel span recorder
)
```

Design rules for the harness itself, since contributors extend it:

- **Fakes enforce the real invariants.** `fake_identity_fabric` refuses to mint a
  credential for an unregistered instance and refuses scopes above the ceiling —
  because a fake that is more permissive than production makes tests that pass against
  code that would fail in the field. When you find a real invariant the fake doesn't
  enforce, add it to the fake in the same PR.
- **No network, ever, in the unit/component/contract lanes.** A test that reaches the
  internet fails in air-gapped CI, which is the environment several of our operators
  actually run.
- **The harness is a shipped surface.** Operators write their own hooks, packs, and
  providers and need these fakes to test them, so `harness.testing` is public API under
  the semver seam promise (constitution, Principle V). Breaking it is a MAJOR change.

## Governance assertions

Security-relevant assertions must be one line, or contributors will skip them. Use the
provided helpers rather than inspecting internals:

```python
assert_denied_closed(result, reason="risk_class")   # denied, and denied by failing closed
assert_allowed(result)
assert_audit_chain(audit)                            # append-only, hash-chain intact, no gaps
assert_correlated(audit, spans, run_id)              # one ID joins prompt → hook → tool → run
assert_scope_narrowed(token, at_most=user_scope)     # never amplified beyond the user
assert_no_secret_values(audit, spans, model_context) # references only, everywhere
assert_hook_order(spans)                             # governance capability ran first
assert_no_side_effect(fake_product_api)              # nothing mutated on the denial path
```

Every enforcement test should assert *four* things, not one: the decision, the audit
record, the absence of side effects, and the absence of leaked secret values. A test
that only checks the return value proves less than it appears to.

## Testing hooks

A hook is enforcement code. Four cases, all required:

```python
def test_allows_within_scope(...)      # the happy path
def test_denies_out_of_scope(...)      # the intended denial
def test_denies_on_internal_error(...) # THE IMPORTANT ONE — fail closed
def test_runs_in_governance_order(...) # ordering relative to co-resident capabilities
```

The error case is where reviews fail most often. Inject an exception into whatever the
hook depends on (policy engine unreachable, registry snapshot corrupt, clock skew) and
assert the call is **denied and audited**, not allowed-through and logged:

```python
def test_denies_on_internal_error(hook, fault):
    with fault.raise_in("policy_engine.evaluate", RuntimeError):
        result = hook.pre_tool_use(call)
    assert_denied_closed(result, reason="internal_error")
    assert_no_side_effect(fake_product_api)
```

Also test the post-hook independently — redaction and audit must happen even when the
tool call itself failed, and especially when it returned something sensitive.

## Testing tools

Every registered tool, MCP or native, needs:

- **Schema tests** — arguments validate strictly; malformed input is rejected before
  any I/O.
- **Risk-class tests** — the declared class drives the expected gates (destructive
  requires a plan artifact and human approval; secret-touching triggers quarantine
  behavior).
- **Registration tests** — an unregistered, review-overdue, or drifted tool is refused
  by the pre-hook. Do not skip this because "the registry handles it": the enforcement
  point is what you are testing.
- **Idempotency tests** — invoke twice with the same side-effect key; assert one
  effect. If a tool cannot be safely retried, its test should demonstrate the rejection
  of the duplicate rather than pretend the case doesn't arise.
- **Secret-handling tests** — assert secret values never appear in results handed to
  model context, audit, or spans. References only.

For MCP-backed tools, test against a local stub server rather than the vendor's — you
are testing your client, hooks, and mapping, not their implementation. Record-and-
replay fixtures against the real server belong in the integration lane, refreshed
deliberately.

## Durability and fault injection

The seven scenarios below are constitutional (constitution, Quality Gates). Every
durability provider and both adapters run all of them; a change that touches
execution, checkpointing, or token lifetime runs them too.

```python
@pytest.mark.durability
def test_resume_after_token_expiry(runner, frozen_clock, fault):
    run = runner.start(long_task)
    run.advance_to(step=3)
    frozen_clock.advance(hours=2)          # token TTL passes
    fault.kill(run)
    resumed = runner.resume(run.id)
    assert resumed.reauthenticated is True # re-auth …
    assert resumed.replayed_token is False # … never replay
    assert_correlated(audit, spans, run.id)
```

The full set: kill mid-run and resume; kill during an external wait (must **re-observe**
the outcome, never re-execute); resume after token expiry (re-auth, never replay);
partition plus double-resume (fencing rejects the zombie); grant expiry mid-outage
(parks, never resumes); duplicate side-effect rejection; in-flight drain across
upgrade.

Two rules: **never `sleep()`** — advance the frozen clock; and **assert on observable
state**, not on internal step counters, or the test breaks every time the execution
model is refactored.

## Multi-tenant isolation

The highest-severity bug this system can have is one tenant seeing another's estate.
Isolation gets its own test class, not incidental coverage:

- Every read path: a Tenant A identity querying a Tenant B resource is denied, and the
  denial does not disclose existence.
- Every write path: cross-tenant mutation is impossible even with a valid Tenant A
  token and a correct Tenant B resource identifier.
- Audit and evidence: Tenant A's governed read path returns Tenant A records only, and
  the evidence-access record is itself written.
- Caches and precedent: a cache or in-flight-index hit never crosses a tenant boundary
  (constitution, Principle IV — reuse carries no authority).

Parameterize these across surfaces (MCP, API, CLI, portal), since **surface parity** is
itself a conformance requirement: the same operation must produce the same verdict on
every transport.

## Adversarial testing

Written from the attacker's position, not the user's:

- **Prompt injection** via analyzed repository content, retrieved guidance, and tool
  results — assert the injected instruction does not change tool selection, scope, or
  policy outcomes.
- **Exfiltration** — an agent instructed to leak analyzed code or secret values into a
  PR body, a commit message, a log line, or a tool argument, and blocked at each.
- **Scope escape** — attempts to exceed the requesting user's entitlements, including
  via delegation chains and inter-agent handoff; assert scopes only narrow.
- **Confused deputy** — brokered products where a shared-grain credential could exceed
  the user: assert the entitlement-mirroring pre-check refuses before the credential is
  wielded.
- **Capability smuggling** — loading a capability or tool outside the ceiling; assert
  the load itself is hooked, audited, and denied.

These belong in the PR lane, not nightly. They are cheap, and they are what a security
reviewer will look for first in a hook or pack PR.

## Conformance suites

```bash
uv sync --extra adapters   # required: the suite exercises the primary adapter
make conformance
```

Conformance is where an adapter or provider proves it did not weaken the guarantees it
sits on top of. It is **merge-blocking in the fast lane** — a locally-run result pasted
into a pull request is a pre-flight, never the gate.

**Which rows are in force is per-feature, not global.** Each gate row binds from the
moment its underlying feature exists, and before then is absent or a single explicit skip
naming the ADR that defers it — never a passing stub, because a silent green is
indistinguishable from a real pass at review time
([ADR-0047](../adr/0047-conformance-gate-rows-attach-as-features-land.md)). The in-force
set for a feature is recorded in its conformance contract; a feature that lands without
adding its rows is a gate regression.

The primary adapter's slice (`tests/conformance/adapter/`) is deliberately three rows:

| Row | What it proves |
| --- | --- |
| **Governance order** | The governance capability admits a call before any co-resident capability observes it. Governance declares `position='outermost'`, so this holds regardless of how a caller orders the list |
| **Fail closed** | An injected fault anywhere in the capability chain denies with zero tool-body executions. No branch converts an enforcement error into an allow |
| **Governed entry** | Execution reaches `invoke_tool`, never a framework tool body. The fixture's framework bodies raise if called, so a bypass fails loudly |

Deferred rows — four-transport surface parity, deferred-disclosure parity, the full
ADR-0024 durability matrix, second-adapter cases — attach when those features land. See
`specs/004-primary-adapter/contracts/conformance-adapter.md` for the per-row ADR citations.

**The break test passes.** `test_governance_order_break.py` is self-verifying: it builds
the inverted arrangement and asserts the shared ordering assertion *raises*. A gate nobody
has watched fail is a gate nobody knows works — this is how that is checked without
leaving a red test in the suite.

## Writing evals

Evals live with their pack (`packs/<name>/evals/`) and run through `pydantic-evals`
behind the Eval Provider interface.

**Case format**: an eval case is an input, a context fixture, and an expectation about
*behavior*, not wording. Assert that a plan gate was requested, that a specific tool
was chosen, that a citation to the right source appeared, that a decline occurred —
never that the model said a particular sentence.

**Required suites per pack**:

- **Golden tasks** — representative work, scored for correctness (does the generated
  HCL plan cleanly; does the integration compile and wire correctly).
- **Must-deny** — safety cases the agent must refuse.
- **Must-decline** — out-of-scope requests it must decline with a pointer elsewhere
  (spend actuals, chargeback, audit-grade cost reporting).
- **Citation accuracy** — guidance answers cite real, retrieved sources, and decline
  rather than confabulate when guidance is missing.
- **Role suites** where bindings differ — ask, plan, write, and judge each qualify
  separately; a model green for writing is not thereby qualified to judge.

**Variance handling**: run N repetitions (default 5), score against a threshold, and
report the distribution. A suite that passes at 3/5 has told you something important —
record it rather than re-running until green. Judges used in scoring are pinned,
qualified artifacts; changing the judge is a gate change and requires its own
promotion.

**Corpus hygiene**: eval data is synthetic or scrubbed. Never commit real customer
data, real infrastructure identifiers, or production audit records. Cases derived from
real incidents are reviewed before contribution.

## Coverage policy

There is no global percentage target — chasing one produces tests of trivial getters
while the deny paths go uncovered. Instead:

- **Branch coverage is required on enforcement paths**: hooks, policy evaluation,
  identity and token exchange, redaction, audit writes, and every `except` in those
  paths. A new branch in enforcement code without a covering test is a review blocker.
- **Every bug fix ships a regression test** that fails without the fix.
- **Uncovered code in a PR gets a sentence** in the description explaining why.

Coverage reports are advisory in CI; the enforcement-path check is required.

## CI tiers

| Tier | Trigger | Contents | Budget |
| --- | --- | --- | --- |
| **Fast** | every push | lint, types, unit, component, contract, **adapter and provider conformance**, secret scan, DCO check, license compliance | < 5 min |
| **Full** | every PR | fast + integration, scenario, fault injection, adversarial, remaining conformance and evals by class, license check, a11y | < 30 min |
| **Nightly** | schedule | full + performance, the wider eval matrix, long-horizon durability, dependency audit | unbounded |
| **Release** | tag | nightly + upgrade/migration from previous released versions, air-gapped bundle verification | unbounded |

Reproduce locally before pushing again: `make check` for the fast tier, `make
conformance` for the suites, `make test-full` for the PR tier. CI is not a debugger.

## Anti-patterns

- **Asserting on model wording.** Assert on structure and behavior — tool selected,
  gate requested, citation present, decline issued.
- **Live models in tests.** Stub or script them; a live call belongs in an eval.
- **Retry loops around flakiness.** Quarantine with a linked issue or fix it. Flaky
  tests are failures.
- **`sleep()` for timing.** Advance the frozen clock.
- **Mocking the thing under test.** Mocking your own hook pipeline to test your hook
  proves nothing; use the fakes at the system boundary.
- **Happy-path-only enforcement tests.** The denial and error cases are the point.
- **Fakes that are more permissive than production.** Every fake enforces the real
  invariants, or it is generating false confidence.
- **Snapshot tests over generated content.** They lock in incidental phrasing and
  break on every prompt change; assert properties instead.
- **Skipping the audit assertion.** If it is not audited, it did not happen — the
  product's central claim is exactly this, and tests are how it stays true.
- **Assertions that cannot fail.** Asserting against an object constructed inside
  the test to satisfy the assertion (a zero-count dummy, a fixture that trivially
  matches) proves nothing and reads as coverage. Assert against the artifact the
  scenario actually produced.

## The durability lane is not hermetic

Every suite before `specs/005-durable-execution` ran with no operated service. The
durability lane does not, and the difference is deliberate: Vault and Postgres are
components this project deploys, so faking them would mean the durability guarantees
ship unproven against what they actually run on.

```bash
make dev-up        # Terraform -> Vault -> Nomad -> Postgres
make conformance   # includes the seven durability rows
```

**It fails loudly when the enclave is absent**, rather than skipping. A skipped
guarantee reads exactly like a passing one in a test summary, which is worse than a red
lane.

What survives of the old determinism rule is narrower and still absolute: no live model
provider, no live managed-product API, and disruption simulated in-process rather than
by terminating real infrastructure. `tests/unit/test_no_live_dependencies.py` encodes
the distinction — one list banned everywhere, one permitted only in the modules that
talk to our own enclave.

One scenario crosses a genuine process boundary
(`tests/component/test_resume_cross_process.py`). Restarting a test process is not
terminating infrastructure; an entirely in-process suite would prove the code reloads
its own state, not that the state survived anything.
