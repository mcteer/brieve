# Specification Quality Checklist: MCP Surface

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-27
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs)
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details)
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification

## Notes

- This feature **claims** the four-transport parity row rather than deferring it. 008
  refused it for a good reason — parity is a property between transports and there was one.
  Refusing it again with two would stop being rigour.
- **ADR-0049 is Proposed and this feature resolves it.** That was deliberate: the decision
  was left open until something built it. FR-021 and SC-013 make leaving it Proposed a
  failure rather than a deferral.
- The size is flagged in Assumptions with a suggested phasing rather than split
  unilaterally. `ROADMAP.md` already records health checks and the sweeper as MCP's scope,
  so the bundling is a prior decision, not a new one.
- Clarify (2026-07-27) tightened three things that would each have produced a row passing
  without proving anything: what "equivalent audit events" means (same types, order,
  subject, decision fields — transport as a field, not a structural difference), the
  granularity of a dependency (a named product, because per-workspace health would mean
  enumerating a customer's estate), and single ownership of reachability (the checker
  records, everything else reads).
- It also settled that MCP authenticates **as the calling user**, never as itself. A
  service account would collapse every caller into one subject and destroy
  non-repudiation — invisibly, because everything would still appear to work.
- Analyze (2026-07-27) caught a claim this spec made without checking its source. The
  constitutional parity row reads "surface parity across **all four** transports", and this
  feature has two — so claiming it would have been the passing stub ADR-0047 forbids, in the
  feature whose spec makes a point of refusing stubs. The clarification session had recorded
  "refusing a second time would be avoidance" as settled reasoning, which is how a decision
  gets made without being verified. The row is now **amended to bind incrementally** instead,
  which is better than either claiming or deferring.
- It also found the amendment was incomplete — **Principle VIII** describes parking too, so
  amending only the gate row would have left a principle describing an impossible state — and
  that the sweeper had no dispatch route: 008's parameterized job carries neither `run_id`
  nor `step_index`, so it could decide to resume with nothing to resume with. Same shape as
  008 shipping `NomadDispatcher` with no job to dispatch to.
- ADR-0026 now records being partially superseded (Principle X), and every SC carries a task
  reference rather than only the FRs.
- Analyze pass 2 (2026-07-27) found the fix for the sweeper's dispatch route had stopped one
  layer short: the jobspec now *requires* `run_id` and `step_index`, and `RunDispatcher.dispatch()`
  accepts neither, so the sweeper could not pass what the job demanded. **Third instance of
  "a mechanism specified without the thing it acts through" across two features, and the
  first where fixing one produced the next.** The mechanical check that would have caught
  all three: when a task says "wire A to B", verify A's interface accepts what B requires.
- It also found `ROADMAP.md` still saying "Claimed by 009" after spec, plan, contracts, and
  checklist had all been corrected — **fourth occurrence of restatement drift**, and in the
  file the next feature's planner reads. `ROADMAP.md` belongs in every sweep for that reason.
- And it found T015 telling someone to change Principle VIII's "parks" to "stops" without
  saying why. That "parks" has a different trigger — no eval-qualified model cell — where
  `SUSPENDED` looks like the right answer and would restore human-waiting through the
  model-fallback path, since qualifying a cell is eval-gated human work.
- Analyze pass 3 (2026-07-27) applied the check recorded in pass 2 — *when a task says
  "wire A to B", verify A's interface accepts what B requires* — and immediately found three
  more instances, one of which made a core mechanism unbuildable: the dependency gate is
  registered through `builtin_governance_hooks()`, which takes no arguments, and reads a
  `GovernedRun` that has no health field. There was no path from the hook to the health it
  must consult.
- The other two: extending `RunDispatcher.dispatch()` with required parameters would have
  stopped 008's `POST /runs` compiling, and the MCP service had no Vault JWT role at all —
  the same failure 008 hit at T030, not carried forward.
- **The cause is now recorded in plan.md as a table rather than fixed case by case.** 009 is
  the first feature to consume seams that 002, 005, and 008 each built for one caller, so
  each accepts exactly what its original caller passed. Four extensions are enumerated, and
  the rule that prevents two of the three findings on its own is: **optional-by-default
  wherever a prior caller exists.**
- Analyze pass 4 (2026-07-27) found **no criticals** — the first pass on this feature that
  did not. What it did find: the fix for the previous critical landed in the wrong phase.
  The `GovernedRun` health field is blocking for anything that constructs a run, and it sat
  inside US3's phase, unlabelled, while the plan's own parallel example has someone working
  US1 at the same time. Moved to Foundational.
- It also found the **seam table itself incomplete** — `verify_stream_integrity`'s connection
  factory was a fifth instance of the class the table exists to record. An enumeration that
  reads as exhaustive and is not is worse than none, so the plan now says to add rows rather
  than absorb consumptions into tasks.
- And two smaller ones: the health checker's subject set was never stated (it is the
  registry's distinct products, not a config list, or a newly registered product goes
  unmonitored while the mechanism reports healthy), and the parity amendment is better framed
  as a **correction toward ADR-0033** — which says "any transport", never "all four" — than
  as a policy change. Principle X applies directly, which is a much easier argument.
- Analyze pass 5 (2026-07-27) probed a category the first four never entered: state
  consistency rather than seam wiring. Suspension had **two sources of truth** — 005's
  checkpoint `run_state` and the new `suspended_runs` table — with no rule for which wins.
  The failure modes are silent and asymmetric: absent from the table, a suspended run is
  invisible to the sweeper forever and presents exactly like the hang ADR-0049 exists to
  prevent; stale in the table, the sweeper resumes a finished run. Resolved as the
  `audit_stream_heads` shape: the checkpoint is authoritative, the table is an index written
  in the same transaction, and the sweeper re-reads before resuming.
- It also found the **sixth seam instance, worse than the previous five**: the health
  checker's subject set named "the tool registry" as though one readable instance existed.
  `ToolRegistry` is per-process and in-memory — 002 built it for one caller in one process —
  so no instance existed that the persistent service could read. The MCP service's registry
  is now declared the registry of record, with the ADR-0008 boundary stated: the platform's
  own registry gaining a persistent home, not a registry product; it ships no API for third
  parties, and growing one would be the violation.
- And `is_terminal()` — the method that gives run states their meaning — is now named in
  T013 and asserted in T015a, because wrong in one direction the sweeper can resume nothing,
  and wrong in the other a stopped run resumes past its bound.
