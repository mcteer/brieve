# Conformance contract: deferred disclosure

**Feature**: 036 | **Lane**: merge-blocking (`tests/conformance/adapter/`) | **Runs on**: every PR, no enclave needed

This contract carries **the owed gate row** — tool-call parity under deferred disclosure —
in ADR-0040's own wording: *an identical operation must produce identical governance
outcomes whether or not the tool was disclosed eagerly.* Under ADR-0047 these rows bind
the moment the feature exists; none may be stubbed, and a row asserting anything weaker
than its name does not discharge it.

**Who runs it**: CI's fast lane, automatically. No human-executed row in this contract.

## Rows

### D1 — Parity on the allow path (FR-002, SC-001)

Same definition, same registered tool, same arguments, run twice: eagerly disclosed, and
deferred-then-discovered. Assert the decision, reason code, executed flag, and tool
result are identical, and that the audit records **between `PRE_DECISION` and
`POST_DECISION` are indistinguishable** — field-for-field, with only correlation-scoped
values (timestamps, ids) excluded by name. The deferred trail additionally contains its
`DISCOVERY_OBSERVED` events, which are outside the compared span by design.

### D2 — Parity on the deny path (FR-002, SC-001)

Same shape as D1 with a policy that denies the tool. A tool reached through discovery is
denied for the same reason it would be eagerly. This is the row that catches a disclosure
layer quietly consulting its own view where authority should have been consulted.

### D3 — Deferral withholds schemas and only schemas (FR-001, SC-002)

In the deferred posture, before any discovery: every deferred tool contributes its name
and one-line description to what the model is sent, and **no parameter schema and no
nested types** — asserted per tool. The registry, ceiling, and policy inputs are
byte-identical between postures.

### D4 — The benefit is real (SC-002a)

For the shipped definitions, pre-task tool-schema material in the deferred posture is
**≤ 25% of the eager posture**, both sides measured by the same harness in the same
units, measured values printed in the failure message. A threshold revision requires a
contract edit carrying the measurement that motivated it — never a silent bump (R10).

### D5 — Discovery is recorded and cannot be refused (FR-006, FR-006a, FR-006c)

A search writes `DISCOVERY_OBSERVED` with its queries and matches — including a search
matching nothing. Assert no `PRE_DECISION` exists for the search itself, no path can
refuse it, and the event type differs from every tool-call event type, so "looked for"
cannot be read as "attempted".

### D6 — The search meta-tool never reaches the governed entry (R3)

Structural, two halves: (a) in the composed agent, a search resolves without
`invoke_tool` observing any call; (b) **the exemption is not a name match** — register a
genuine tool named `search_tools` in a *non-disclosure* agent and assert it routes to
`invoke_tool` like any tool. A disclosure agent with that registration refuses at build
(the framework reserves the name), which is a stated conflict, not a silent shadowing.

### D7 — The guard survives the feature (FR-003)

`build_governed_agent(model, capabilities=[ToolSearch()])` still raises
`unreachable_capability_wrapper`. The adapter's own disclosure composition is reachable
only through its named option — the regression row for R1's decision, and for R2's
measured double-wrap collision.

### D8 — Fallback posture is stated, never silent (FR-004, SC-006)

Deferral requested where the composition cannot support it → the run proceeds with
`disclosure_posture: eager_fallback` on its `RUN_START` record, distinguishable from both
`eager` and `deferred` through the governed read path. No configuration presents one
posture while running another.

## Amendment discipline

D4's threshold is the only number in this contract expected to move, and only with a
measurement. Every other row asserts an invariant; weakening one is a spec change, not a
test fix.
