# Implementation Plan: Deferred disclosure and code mode

**Branch**: `036-deferred-disclosure-code-mode` | **Date**: 2026-08-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/036-deferred-disclosure-code-mode/spec.md`

## Summary

Two efficiency mechanisms land without moving a single tool call off the governed path.
**Disclosure**: the adapter composes the framework's deferred-loading and tool-search
machinery *outside* the terminal governance wrapper — a view layer over what the model
knows, never a path around what it may do — and each search is recorded as an observation
(never a decision), which amends ADR-0040 in the same change. **Code mode**: a
platform-owned sandbox seam whose only exit routes every call request — registered tool,
`open`, `eval`, or a name invented on the spot — through `invoke_tool`, with the
`pydantic-monty` runtime plugged in beneath the seam as replaceable, pinned, identified
content. The parity assertions bind to the platform's boundary, not to the runtime's
behaviour, and a deliberately introduced bypass must turn the suite red (SC-004).

## Technical Context

**Language/Version**: Python 3.12 (matches repository)

**Primary Dependencies**: `pydantic-ai-slim==2.18.0` (already pinned; carries
`DeferredLoadingToolset`, `ToolSearchToolset`, the `ToolSearch` capability, and the
`keywords` local search strategy). **New**: `pydantic-monty==0.0.19` — as an **optional
extra** (`sandbox`), never in the base install, and pinned exact per FR-014b. The PyPI
name `monty` is an unrelated materials-science package; the dependency line names
`pydantic-monty` and `research.md` records the provenance.

**Storage**: none new. Discovery and program records land in the existing audit trail;
suspended sandbox state goes through the existing `DurabilityProvider`.

**Testing**: pytest — component suites against the adapter fixtures, conformance rows in
`tests/conformance/adapter/` (the owed parity row lives here), unit gates for the
structural assertions.

**Target Platform**: unchanged (macOS dev, Linux CI/Nomad).

**Project Type**: single project; changes confined to `src/adapters/pydantic_ai/`,
`src/core/sandbox/` (new), `src/core/audit/schema.py` (additive), `src/core/tools/`
(untouched — `invoke_tool` is the fixed point everything else composes around).

**Performance Goals**: SC-002a — deferred pre-task schema material ≤ **25%** of eager for
the shipped definitions, asserted by the conformance row with the measured numbers in its
failure message. The threshold is calibrated against the real pack corpus during
implementation; if the corpus cannot meet it, the row fails and the threshold gets an
evidence-based revision in the contract — never a silent bump.

**Constraints**: `invoke_tool` remains the sole execution entry (Principle II/III), and
because `run_program` is itself a tool, that entry is **re-entered** on the same run —
which composes for bounds and lease but leaves nested non-repeatable brackets as a named
design task (research R11), not an assumption; `_reject_unreachable_wrappers` stays in
force for caller-supplied capabilities; the audit schema change is additive to an
unversioned enum and carries Principle V review; no framework import enters `core/`
(Principle I) — `core/sandbox/` defines the seam as a protocol and the runtime binding
lives in `adapters/`.

**Scale/Scope**: two composition changes in the adapter, one new core seam module, one
audit event type pair, one ADR, **~17 conformance rows + 3 unit gates** (8 disclosure, 9
code-mode, 3 structural — see `contracts/`), no API/MCP/portal surface change.

## Constitution Check

| Principle | Verdict | Notes |
| --- | --- | --- |
| I — Build Glue Only | **Pass** | Both mechanisms are adopted framework/runtime machinery with thin platform glue. `core/` gains a *protocol*, not a runtime import; the `pydantic-monty` binding sits in `adapters/`, the one place framework-shaped dependencies belong (ADR-0019). |
| II — Total Interception; One Governed Tool Layer | **Pass** | The design's fixed point: `invoke_tool` stays the sole execution entry. Disclosure is a view layer outside the terminal wrapper; every sandbox call request — including undeclared names — routes to `invoke_tool` and refuses `tool is not registered` on the same path a structured call would. |
| III — Fail-Closed, In-Process Enforcement | **Pass** | The constitution's own sentence *is* this feature's gate: "Code mode ships in the governed path only with verified per-call hook parity." The verification is the merge-blocking rows in this plan. Note: "capability loading is itself a hooked, audited, ceiling-checked event" already sets the posture FR-006 extends to discovery. |
| IV — Zero Standing Credentials; Authority Per Task | **Pass** | No credential surface changes. Sandbox snapshots enter the existing credential-free-checkpoint discipline (FR-011), asserted by a seeded-credential row. |
| V — Sealed Core, Versioned Seams | **Pass, with review** | Two sealed-core touches: the adapter's composition changes, and an additive `AuditEventType` pair (precedent: `TOOL_CHOSEN`, 021's read-back event — both carried the approved spec + security-maintainer review this one will). Review is Dan's, at the planning PR. |
| VI — Lean by Default | **Pass** | `pydantic-monty` is a library behind an optional extra, not an operated component — no named-trigger ADR required. Absent the extra, code mode refuses with a stated reason (FR-013/SC-007) rather than the base install growing a Rust runtime. |
| VII — Anti-Fragmentation | **Pass** | No substrate-specific behaviour; the same composition ships everywhere. |
| VIII — Eval-Gated Promotion; Pinned vs Fresh | **Pass** | No new promotable artifact class: the model-written program is model *output* under the run's existing ceiling and bounds, not adopted content. The runtime itself is pinned, identified content (FR-014b). Existing must-deny suites keep their jurisdiction; nothing here changes what a definition may do (FR-016). |
| IX — Evidence Over Claims | **Pass** | The feature *adds* evidence: discovery observations (what the model went looking for) and the program as the recorded cause of its calls (US3). Both flow through the existing hash-chained trail and governed read path. |
| X — The Decision Record Governs | **Pass, with obligation** | FR-006b: recording discovery contradicts ADR-0040's "no registry, hook, or audit change", so **ADR-0061 amending ADR-0040 lands in this same change** — status-line pointer on 0040, Decision section untouched, exactly the ADR-0060 mechanism. |

**Gate result**: **PASS — proceed to Phase 0.** Two named obligations travel with the
feature: the Principle V review at the planning PR, and ADR-0061 in the implementation
change.

## Project Structure

### Documentation (this feature)

```text
specs/036-deferred-disclosure-code-mode/
├── plan.md              # This file
├── research.md          # Phase 0 — measured findings and the decisions they forced
├── data-model.md        # Phase 1 — records, postures, and the sandbox seam's shapes
├── quickstart.md        # Phase 1 — how to prove it works end to end
├── contracts/
│   ├── conformance-disclosure.md   # the owed parity row + posture + discovery rows
│   └── conformance-code-mode.md    # per-call parity, break fixture, checkpoint rows
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/
├── adapters/pydantic_ai/
│   ├── agent.py           # build_governed_agent grows a disclosure option; the
│   │                      #   caller-facing guard is UNCHANGED
│   ├── disclosure.py      # NEW — adapter-owned composition: search outside the
│   │                      #   terminal wrapper, discovery recording, posture detection
│   ├── tools.py           # GovernedToolset — untouched; it is the fixed point
│   └── sandbox_runtime.py # NEW — the pydantic-monty binding, beneath the core seam
├── core/
│   ├── audit/schema.py    # additive: DISCOVERY_OBSERVED, PROGRAM_SUBMITTED
│   ├── sandbox/           # NEW — the platform-owned seam
│   │   ├── __init__.py
│   │   ├── seam.py        # SandboxRuntime protocol + the governed execution loop:
│   │   │                  #   every call request → invoke_tool, no second path
│   │   └── state.py       # suspended-state handling under the checkpoint discipline
│   └── tools/invoke.py    # UNTOUCHED
docs/adr/
└── 0061-*.md              # NEW — discovery is recorded, never refused (amends 0040)
tests/
├── component/             # disclosure composition, code-mode loop, posture, evidence
├── conformance/adapter/   # the parity rows (both contracts), incl. the break fixture
└── unit/                  # structural gates: guard intact, no runtime import in core/
```

**Structure Decision**: single project, additive. The load-bearing choice is what does
*not* change: `invoke.py` and `tools.py` are the fixed points, and both new capabilities
are composition around them. `core/sandbox/seam.py` holds the governed loop so the parity
property lives in platform-owned code (FR-014c); `adapters/pydantic_ai/sandbox_runtime.py`
holds the only `pydantic_monty` import in the tree, asserted by a unit gate.

## Constitution re-check (post-design)

Re-evaluated after Phase 1. No verdict changed; two were strengthened by design decisions:

- **II** — R8 exposes code mode as a *registered tool* (`run_program`), so the registry is
  the opt-in switch and no new invocation class exists. A definition whose ceiling lacks
  the tool has no code mode, which is FR-016 holding by construction.
- **IX** — the data model's one-sentence parity property ("between `PRE_DECISION` and
  `POST_DECISION`, nothing in any record reveals which invocation path issued the call")
  became rows D1/D2/C2, which is the property stated as a test rather than an intention.

One risk moved *into* the record rather than being resolved: R9 notes the credential scan
must not parse the runtime's serialization format, and C6 asserts against the seam's own
ledger instead. That is a design constraint the implementer inherits, not an open question.

## Complexity Tracking

No Constitution Check violations to justify. The one addition that *looks* like
complexity — a whole new `core/sandbox/` package for what could be a function in the
adapter — is the direct consequence of FR-014a/c: the parity assertions must hold against
a boundary the platform owns, and a boundary owned by the adapter's runtime binding would
move with the runtime.
