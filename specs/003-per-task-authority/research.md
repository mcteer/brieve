# Research: Per-Task Authority

**Feature**: `specs/003-per-task-authority`
**Date**: 2026-07-25

## Decision: Integrate at run start and governance pre-hook

- **Decision**: Manufacture and bind task authority inside `start_governed_run` (refuse
  before an active run is returned). Enforce expiry and effective-scope membership in a
  governance `capability_kind=governance` pre-hook that runs with the built-in governance
  set. Product entitlement mirroring runs as an additional governance pre-hook after the
  authority gate and before non-governance hooks.
- **Rationale**: ADR-0006/0019 require in-process fail-closed governance-first
  enforcement; 002 already owns the sole `invoke_tool` entry. Authority must not be a
  skippable side channel.
- **Alternatives considered**: Separate authorize() API callers might forget (rejected);
  enforce only inside tool handlers (bypassable; rejected).

## Decision: Scope algebra representation

- **Decision**: Represent harness-domain scope as a Pydantic `AuthorityScope` with two
  frozen sets: `tool_names: frozenset[str]` and `product_actions: frozenset[str]`
  (stable action ids like `product.workspace.read`). Effective authority is the
  component-wise intersection of user scope, ceiling scope, requested task scope, and
  policy scope (policy defaults to “unrestricted” identity map in 003 fakes unless a
  test installs a denying policy fixture).
- **Rationale**: Spec requires tool and product-domain checks; 002’s tool-name-only
  `GovernedRun.scope` becomes the tool_names projection of effective authority after
  bind (registry out-of-scope remains a second belt).
- **Alternatives considered**: String-only scopes (cannot express product actions);
  risk-class-only scopes (premature without full registry lifecycle).

## Decision: Amplification refused at start

- **Decision**: If requested task scope is not a subset of both user scope and ceiling
  scope (per component), `start_governed_run` raises a typed refuse error and issues no
  credential. Equality at the bound is allowed (“at most,” not “strictly less”).
- **Rationale**: FR-002/FR-003; SC-001.
- **Alternatives considered**: Issue then deny on first tool (wider attack window;
  rejected).

## Decision: Task credential is a reference object

- **Decision**: `TaskCredentialRef` holds `credential_id` (opaque), `expires_at`,
  `effective: AuthorityScope`, and `subject_user_id`. The secret-bearing material, if any
  for brokered fakes, lives only inside the fake identity/product fabric keyed by
  `credential_id` and is never placed on `GovernedRun`, audit payloads, or spans.
  `GovernedRun` stores the `TaskCredentialRef` only.
- **Rationale**: FR-001, FR-010, FR-011, ADR-0026.
- **Alternatives considered**: Store bearer tokens on the run (forbidden); JWT in audit
  (forbidden).

## Decision: TTL and frozen clock

- **Decision**: Default task credential TTL is **15 minutes** from manufacture
  (`expires_at = clock.now() + timedelta(minutes=15)`). Tests use `frozen_clock` with
  `advance()`. Expiry check is `clock.now() >= expires_at` → deny with reason
  `authority_expired` before tool body.
- **Rationale**: Short-lived per ADR-0026 spirit; single pinned default avoids plan
  forks; frozen clock is already promised in TESTING.md.
- **Alternatives considered**: Configurable TTL without a default (plan fork); wall clock
  only in tests (nondeterministic).

## Decision: Re-manufacture after expiry

- **Decision**: 003 does not auto-refresh. After expiry, invokes deny until the test/operator
  starts a **new** run (new manufacture). Document that grant-based refresh/resume is
  durability/003+ follow-on (spec already defers full resume).
- **Rationale**: Spec US5 says deny until re-manufactured under FR-002–FR-003; simplest
  fail-closed behavior without inventing grant parking.
- **Alternatives considered**: Silent refresh on invoke (hides expiry; rejected for 003).

## Decision: Entitlement mirroring modes on tools

- **Decision**: Tool registration metadata gains optional `product_mode`:
  `none` (default), `federate`, or `broker`. For `broker`, the mirroring pre-hook MUST
  call `fake_identity_fabric.resolve_product_entitlements(user, product)` and deny unless
  the tool’s `product_action` is in that set **before** any shared-grain wield. For
  `federate`, the fake product validates the run’s subject identity reference and still
  requires the action ∈ user’s entitlements, without a shared-grain credential object in
  the harness.
- **Rationale**: FR-004–FR-006 / ADR-0044.
- **Alternatives considered**: Mirror only in product fake internals (harness could skip;
  rejected — must be hooked).

## Decision: Empty entitlements deny

- **Decision**: Empty product entitlement set denies all brokered/federated product
  actions for that user. Empty is never treated as unrestricted.
- **Rationale**: Spec edge case; fail closed.
- **Alternatives considered**: Empty means admin (dangerous default; rejected).

## Decision: Mid-run stricter policy

- **Decision**: On each invoke, re-read policy from the identity fabric and compute
  `live_effective = authority.effective ∩ current_policy` (both components). Entitlement
  mirroring re-resolves live entitlements separately. No caching of wider results across
  invokes; stale wider issued authority must not win.
- **Rationale**: Spec edge case — post-issuance policy shrink must be observed.
- **Alternatives considered**: Cache effective authority for run lifetime (fails edge case).

## Decision: Per-run salt for secret-class hashes

- **Decision**: At run start, generate `run_salt = secrets.token_bytes(32)` held only in
  memory on the run (not audited as a raw value). Argument and credential-reference
  content hashes in authority-related audit payloads use HMAC-SHA256(run_salt, material)
  hex digest. Salt is never written to audit/spans. This fulfills the 002 audit-sink
  future-salt note now that authority material exists.
- **Rationale**: Principle IV forbids standing HMAC keys; per-run random salt is the
  pinned approach from the audit contract note.
- **Alternatives considered**: Keep unsalted SHA-256 (rejected now that credentials
  exist); standing key (forbidden).

## Decision: Audit event types

- **Decision**: Extend `AuditEventType` with `authority_issued`, `authority_refused`,
  `authority_denied`, `mirroring_decision`, `authority_expired` (exact string values as
  enum members). All carry correlation_id and redacted payloads only.
- **Rationale**: FR-009; sealed schema extension needs named events now.
- **Alternatives considered**: Overload `pre_decision` only (weaker investigator UX;
  rejected).

## Decision: Evidential gap on authority audit failure

- **Decision**: If authority manufacture succeeds but appending `authority_issued`
  fails, refuse the run (no active usable authority) with evidential-gap semantics. If
  mirroring/authority deny audit append fails on the pre-path, deny with
  `internal_error` and `evidential_gap=True` (002 invariant 5).
- **Rationale**: FR-015.
- **Alternatives considered**: Proceed without audit (forbidden).

## Decision: Harness surface for 003

- **Decision**: Implement exactly: `fake_identity_fabric`, `fake_product_api`,
  `frozen_clock`, `assert_scope_narrowed(token, at_most=user_scope)`. Export from
  `tests.harness`. `assert_scope_narrowed` compares `TaskCredentialRef.effective` (or
  equivalent authority object fields) as subsets of `at_most` for both tool_names and
  product_actions.
- **Rationale**: FR-012/FR-013; TESTING.md names.
- **Alternatives considered**: New helper names (forbidden by named-contract rule).

## Decision: No new runtime dependencies

- **Decision**: Do not add PyJWT, httpx, hvac, or authlib in 003. Fakes implement
  protocols in pure Python.
- **Rationale**: Principle VI; spec assumptions.
- **Alternatives considered**: Real OIDC client against mock server (heavier; deferred).

## Decision: Reason codes (pinned)

- **Decision**: Use stable reason codes: `authority_refused`, `authority_expired`,
  `authority_insufficient`, `mirroring_denied`, `identity_unavailable`,
  `exchange_failed`, `internal_error`. Keep 002 codes for registry/scope. Do not build
  caller logic that assumes external visibility of entitlement detail beyond these codes
  (FR-014).
- **Rationale**: Safe messages; tenancy-era tightening may collapse some codes later —
  document in contract without soft “equivalent” language.
- **Alternatives considered**: Free-form exception strings (leak risk).
