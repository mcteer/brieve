# Research: Deferred disclosure and code mode

**Feature**: 036 | **Date**: 2026-08-05

Everything here was **measured against this repository's pinned dependencies**, not read
from documentation. Each finding names its probe so it can be re-run when a pin moves.
Probes lived in the session scratchpad; the load-bearing ones become conformance rows or
component tests during implementation, which is where they belong permanently.

## R1 — The disclosure mechanism ships in the pinned framework, and the governed agent refuses it

**Decision**: compose disclosure in the adapter, deliberately; do not weaken the guard.

**Measured** (`pydantic-ai-slim==2.18.0`):

- `pydantic_ai.toolsets` exports `DeferredLoadingToolset`; `_tool_search` provides
  `ToolSearchToolset` and `keywords_search_fn` (a local strategy that needs no
  model-native support); `pydantic_ai.capabilities.ToolSearch` is the capability form.
- `build_governed_agent(model, capabilities=[ToolSearch()])` raises `GovernedToolError`
  with `reason_code=unreachable_capability_wrapper`. The guard is correct:
  `GovernedToolset` is terminal — `call_tool` routes to `invoke_tool` and never delegates
  inward — so a co-resident capability's wrapper toolset would be silently unreachable,
  the ADR-0047 failure mode.

**Rationale**: the refusal is the platform working. The composition must be *owned by the
adapter* — a named, audited arrangement the adapter constructs — never a caller-supplied
capability the guard has to trust.

**Alternatives considered**: deleting the guard (re-opens the silent-pass hole for every
future capability); exempting `ToolSearch` by class name (a name is not a property — a
fork or rename walks straight past it).

## R2 — Manually constructing the search wrapper double-wraps; the framework supplies its own

**Decision**: the adapter *marks* tools deferred and lets the framework's machinery
provide the search layer; it never constructs `ToolSearchToolset` itself. The exact
wiring (framework auto-wrap vs. explicit capability with governance-aware ordering) is
selected by the first implementation task, with this collision as its regression test.

**Measured, instrumented**: composing `ToolSearchToolset(GovernedToolset(DeferredLoadingToolset(tools)))`
and running an agent raises `UserError: Tool name 'search_tools' is reserved for tool
search`. A spy on `get_tools` showed **two wrapper instances** — the manually constructed
one, and a second the framework created around it whose inner view already contained the
first one's `search_tools`. The framework's own source states the doctrine: *"Capability
wrapper toolsets (including ToolSearch and CodeMode) are applied here via
get_wrapper_toolset, around the prepare_tools wrap."*

**Also measured**: deferral marks alone, with no search layer in the chain
(`DeferredLoadingToolset(GovernedToolset(tools))`, plain agent, scripted model) are a
**silent no-op** — every tool was disclosed in full, no `search_tools` appeared, no error.
This corrects an earlier same-day probe that attributed the no-op to model-profile
support; the missing piece was the search layer, not the profile. Both states matter:
the first is the collision to avoid, the second is the unstated-posture hazard FR-004
exists for.

**Rationale**: fighting a framework's composition doctrine from outside it produces
exactly the two failure modes measured. The adapter's job is to place governance
correctly *within* that doctrine while keeping `GovernedToolset` terminal for execution.

## R3 — The search meta-tool must be exempted structurally, not by name

**Decision**: a search never reaches `invoke_tool`. The exemption is positional — the
search layer sits outside the terminal wrapper and handles its own meta-tool, so a search
*cannot* arrive at the governed entry — never a string match on `search_tools`.

**Measured**: a scripted model emitting `ToolCallPart(tool_name="search_tools")` against
today's governed agent produces `GovernedToolError: tool is not registered` — the call
reached `invoke_tool` and was refused as an ordinary unregistered tool.

**Rationale**: a name-based exemption is a bypass anyone can trigger by registering a
tool called `search_tools`. `ToolSearchToolset.call_tool` already handles its meta-tool
without delegating inward, which is the structural shape FR-006/FR-006a require: recorded
(the adapter wraps the search function to emit the observation) and never refused (it is
not a decision point, so it never enters the pipeline that makes decisions).

## R4 — Discovery recording is an audit-schema addition with named precedent

**Decision**: two additive `AuditEventType` members — `DISCOVERY_OBSERVED` (queries, what
matched, including nothing) and `PROGRAM_SUBMITTED` (the model-written program, verbatim,
for US3). ADR-0061 amends ADR-0040 in the same change (FR-006b), by status-line pointer,
Decision section untouched — the ADR-0060 mechanism.

**Measured**: `core/audit/schema.py` is an unversioned `StrEnum` whose last two additions
(`TOOL_CHOSEN`, 021's read-back event) each carry a docstring recording that additive
sealed-core changes went through Principle V review rather than being waved through.
`TURN_RECORDED`'s docstring already argues the verbatim-content question this feature
re-encounters for programs: the record is the only copy once views are deleted, and
divergence from `redact_arguments` is argued in an ADR rather than assumed.

**Rationale**: precedent is exact. Follow it, including the review.

## R5 — The sandbox seam: demonstrated end to end, and the boundary is the host's

**Decision**: `core/sandbox/seam.py` owns the governed loop; the runtime implements a
protocol beneath it. Every `FunctionSnapshot` — registered tool or not — routes to
`invoke_tool`; the loop resumes with the governed result or converts a refusal into the
in-sandbox failure.

**Measured** (`pydantic-monty==0.0.19`, clean venv):

- Lifecycle: `Monty()` is a worker pool and a context manager; `pool.checkout()` yields a
  context-managed `MontySession`; `feed_start(code, external_lookup={...})` returns
  snapshots; `FunctionSnapshot` carries `function_name`, `args`, `kwargs`, `call_id`,
  `is_os_function`; resume takes `{"return_value": ...}` (or `exception` /`exc_type`);
  `MontySession.dump()`/`load_snapshot` serialize the suspended worker.
- A two-call program paused at both calls; the host saw both; the governed result of the
  first flowed into the second as a keyword argument.
- **The table is a lookup, not a whitelist**: `open('/etc/passwd')`, `eval('1+1')`,
  `__import__('socket')`, and an entirely undeclared `exfiltrate('secret')` all arrived
  as ordinary `FunctionSnapshot`s. `import os` yields a stub whose attributes do not
  exist, so nothing reaches the OS on its own — but every attempt becomes a request the
  host is offered, shape-identical to a tool call.

**Rationale**: the last finding decides the architecture and appears in no ADR. The
security boundary is the host's snapshot handler — our code — so FR-014a/c (platform owns
the seam; parity binds to it, not to runtime behaviour) is the measured conclusion, not a
caution. It also collapses FR-008 into the existing path: an invented name is refused by
`invoke_tool` as `tool is not registered`, recorded like any denial, with no special-case
code to get wrong.

## R6 — There is no framework code mode to adopt

**Decision**: build the seam here; adopt nothing.

**Measured**: `CodeModeToolset` is absent from pinned 2.18.0. In the latest release
(2.24.0, wheel inspected) it appears **only inside a comment** in `tool_manager.py` — no
module, no class. ADR-0054's watch signal "CodeModeToolset ships in stable Pydantic AI"
is unmet.

## R7 — Package identity: the obvious name is the wrong project

**Decision**: depend on `pydantic-monty==0.0.19`, exact pin, optional extra `sandbox`,
provenance recorded here.

**Measured**: PyPI `monty` is the materials-science package from the pymatgen ecosystem
(version 2026.7.16, "Monty is the missing complement to Python"). The sandbox is
`pydantic-monty` — Python bindings for github.com/pydantic/monty, MIT, 26 releases,
0.0.19 current (ADR-0054 recorded 0.0.17 on 2026-07-29; two releases in a week is the
instability its `0.0.x` version claims). Import name: `pydantic_monty` (ships with
`pydantic-monty-runtime`).

**Rationale**: `uv add monty` installs an unrelated project without error. ADR-0004's
identified-content discipline applies to runtime dependencies exactly as to documents.

## R8 — How a program enters the run: a governed tool call

**Decision**: code mode is exposed as a registered **native tool** (working name
`run_program`) whose handler is the sandbox seam. The program arrives as the tool call's
argument, so submission itself passes the full pipeline — hooks decide whether *this
definition* may use code mode at all, the bracket wraps the non-repeatable execution, and
`PROGRAM_SUBMITTED` records the cause. Inner calls each round-trip `invoke_tool` under
the same run: a program issuing N calls produces **N+1** governed decisions.

**Rationale**: registering it as a tool means no new invocation class and no new
enforcement point — Principle II's registry *is* the opt-in switch (a definition whose
ceiling lacks `run_program` has no code mode, FR-016 holding by construction), and
FR-013/SC-007 falls out naturally: without the `sandbox` extra the handler refuses with a
stated reason code rather than the capability half-existing.

**Alternatives considered**: a second entry beside `invoke_tool` (a parallel governed
path is the fragmentation Principle II forbids); a capability wrapper à la the framework's
future `CodeModeToolset` (builds on a comment, R6).

## R9 — Suspended sandbox state is a checkpoint

**Decision**: `MontySession.dump()` bytes flow through the existing `DurabilityProvider`
via the adapter's `save_state`, whose `_reject_credentials` discipline extends to the
serialized worker. The conformance row seeds a credential-shaped value into sandbox
state and asserts `CredentialInCheckpointError` — asserted, not assumed from the sandbox
holding no ambient credentials (FR-011, ADR-0026).

**Open at implementation** (named here so it is not discovered): snapshot bytes are
opaque; the credential scan may need the seam to keep a parallel, scannable record of
what entered the sandbox (inputs and resume values) rather than parsing the runtime's
serialization format, which would couple the discipline to a `0.0.x` format.

## R10 — SC-002a's threshold

**Decision**: the row asserts deferred pre-task schema material ≤ **25%** of eager for
the shipped definitions, both sides measured by the same harness in the same units, the
measured numbers printed in the failure message. Calibrated against the real pack corpus
by the implementing task; if the corpus cannot meet 25%, the row fails and the threshold
is revised *in the contract, with the measurement* — never bumped silently.

**Rationale**: a ratio self-calibrates as packs grow where an absolute budget goes stale;
25% is a starting claim strong enough to mean something and weak enough that a catalog
line per tool plausibly meets it. The number is falsifiable by construction, which is the
property that matters.
