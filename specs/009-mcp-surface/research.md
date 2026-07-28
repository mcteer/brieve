# Phase 0 Research: MCP Surface

**Feature**: `specs/009-mcp-surface` | **Date**: 2026-07-27

Ten decisions. The first is checked rather than assumed, because 008 learned that the hard
way — its premise gate caught a wrong licence claim in this document's predecessor.

---

## D1 — The MCP protocol: the official SDK, and it already clears the gate

**Decision**: `mcp` 1.28.1 (MIT). **Verified against `scripts/check-licenses.sh` before
planning around it**, not deferred to a task: `mcp`, `sse-starlette`, `python-multipart`,
`jsonschema`, `referencing`, `rpds-py`, `python-dotenv`, `httpx-sse`, and
`pydantic-settings` are MIT, BSD-3-Clause, or Apache-2.0, all already on the allowlist. The
gate passes with no allowlist change.

**Rationale**: Principle I is explicit — adopt what upstream ships, and ADR-0033 says to
migrate onto official servers as they mature. Implementing the protocol here would be
building the one thing that is unambiguously commodity, and it would drift from the spec the
IDEs on the other end follow.

**Alternatives considered**:

- **Hand-rolled JSON-RPC over stdio/SSE.** No new dependency, and wrong. The protocol is
  not the interesting part of this feature; the authorization core behind it is. Every hour
  spent on framing is an hour not spent on parity.
- **Wrapping the SDK behind our own abstraction "in case it changes".** A layer whose only
  purpose is to make a future migration easier, written before knowing what the migration
  would be. The seam that matters is `RunDispatcher`-shaped and already exists at the core.

---

## D2 — A persistent `service` job, and the honest cost of it

**Decision**: `infra/jobs/mcp.nomad.hcl` as a Nomad **`service`** job. The first persistent
component in this platform.

**Rationale**: ADR-0049 needs somewhere for the health checker and sweeper to live, and
everything else is deliberately ephemeral — the ADR makes a run's container ending part of
the guarantee. Something has to outlast a run for a suspended run to be resumed *by* it.

**The cost, stated rather than implied**: a persistent service holds an attested identity
for as long as it runs, which is the least ephemeral thing in this platform. That is
mitigated — a TTL on the identity with re-issue, and no product credential held at all,
since the service starts runs and reads health rather than acting on products — but it is
not eliminated. If a reviewer pushes back on Principle IV, this is the place.

**Alternatives considered**:

- **A periodic `batch` job.** Would avoid the persistent component entirely, and it is
  sufficient for *recovery detection*. It is not sufficient for the refusal path: a run
  about to call a product needs the answer now, not at the next tick. Splitting them — a
  periodic sweeper and an on-demand checker — would mean two components where the checker
  still has to be persistent.
- **Health checks inside each run.** Every run independently rediscovering the same outage,
  which is the thing ADR-0049 rejects by name: "one signal, raised once, instead of every
  affected run independently rediscovering the same outage."

---

## D3 — Health state in Postgres, never in memory

**Decision**: dependency health records live in the database, with the time of the last
check.

**Rationale**: a restart must not silently mean "everything is reachable again". In-memory
health starts empty, and empty resolves to unknown, and unknown is unhealthy (FR-006) — so
in-memory would actually fail *closed*, which sounds fine until the service restarts during
an incident and every run suspends at once. Persisted health degrades honestly: the record
says when it was last checked, and a stale record is treated as unknown rather than as
either extreme.

**Alternatives considered**:

- **In-memory with a warm-up period.** Introduces a window whose behaviour depends on
  timing, which is the class of bug this platform keeps finding the expensive way.
- **Health derived on demand from the product itself.** That is the refusal calling the
  dependency it exists to avoid calling.

---

## D4 — The refusal is a hook, not a pre-flight

**Decision**: the dependency gate runs **inside** the governed hook pipeline, as a
pre-execution hook, alongside governance, authority, and mirroring.

**Rationale**: Principle II. A check placed before the pipeline is a second refusal path,
and a second refusal path is a second authorization path wearing a practical-sounding name.
It also gets the audit and ordering guarantees for free rather than needing them
reimplemented.

**The risk worth naming**: a pre-flight check is *obviously* cheaper — skip the pipeline
entirely for a call that will be refused anyway — and it would work. That is why the
conformance row has to assert **placement**, not just behaviour. Otherwise the first person
optimising a hot path moves it and nothing notices.

**Alternatives considered**:

- **A pre-flight guard in the surface.** Cheapest, and it would leave a run started through
  the CLI ignoring a dependency the platform knows is down.
- **Inside the tool adapter.** Correct per-tool and wrong per-platform: every new adapter
  would have to remember.

---

## D5 — Two denial classes, and only one is model-visible

**Decision**: an availability denial and a policy denial are distinct in the audit trail
**and** distinct in what the model is told. Only the availability class is surfaced to the
agent as an invitation to adapt.

**Rationale**: this is ADR-0049 being more specific than the spec was, and it is the
subtlest thing in the feature. A tool call refused for **scope** must not teach an agent to
find another route — that is the governance boundary holding, and an agent that treats it
as an obstacle to route around inverts Principles II and III. A call refused because a
dependency is **down** invites a legitimate alternative: write the Terraform, hand it back,
say the workspace was unreachable.

So the difference is not cosmetic and not only for auditors. Getting it backwards — making
scope denials model-visible as adaptable — would actively train the wrong behaviour.

**Alternatives considered**:

- **One denial class with a reason code.** Simpler, and it puts the decision about how to
  react in the model's hands, which is exactly where it must not be.
- **Neither visible.** Loses US4 entirely: the agent cannot do the part it still can if it
  is not told why it was refused.

---

## D6 — What replaces `PARKED`, and the amendment it forces

**Decision**: `PARKED` is removed and split into the two things it was conflating:

- **Grant expiry → `STOPPED`**, with the reason recorded. The same disposition as any other
  execution bound, per ADR-0049.
- **Unreachable dependency → `SUSPENDED`**, naming that dependency. Resumable by the
  sweeper, never by a person.

**Rationale**: `PARKED` meant "stopped for a human to resolve", and ADR-0049 removes the
category. Keeping the name for the dependency case would carry the human-in-the-loop
connotation into the state that most needs it gone.

**The consequence the spec did not anticipate**: the constitution's Quality Gates name
**"grant-expiry parking"** as one of seven merge-blocking durability rows
(`.specify/memory/constitution.md`, line 199). That row must become grant-expiry *stop*,
which changes what a constitutionally-named gate asserts. This feature therefore carries a
**constitution amendment with a Sync Impact Report citing ADR-0049** — a MINOR revision,
since a gate row is redefined but no principle is removed or redefined, so no ADR-0016
quorum is required.

Found by grepping for `PARKED` and hitting `tests/conformance/durability/rows.py`. Worth
recording how, because "removing a state" reads like a refactor right up until it turns out
the constitution names it.

**Alternatives considered**:

- **Keep `PARKED` as a deprecated alias.** Leaves a state in the sealed core that nothing
  can enter, and leaves the constitution naming a row for behaviour that no longer exists.
- **Rename `PARKED` to `SUSPENDED` and keep one state.** Collapses grant expiry and
  dependency unavailability back together, which is precisely the conflation ADR-0049
  separates.

---

## D7 — The CI lane: `pull_request`, head-repo condition, and `make conformance`

**Decision**: a second workflow triggered on `pull_request`, whose enclave job runs only
when `github.event.pull_request.head.repo.full_name == github.repository`. It runs **`make
conformance`** — the same command a human runs.

**Rationale, on the trigger**: the lane needs a Vault Enterprise licence, which is a secret.
GitHub does not expose secrets to fork-triggered `pull_request` workflows, and the mechanism
that would — `pull_request_target` — runs base-branch workflows with secrets available while
the fork controls the code being tested. Using it here would hand a licence and a live
enclave to arbitrary pull requests: a credential-disclosure problem traded for a coverage
gap, which is a bad trade in the direction that matters.

**Rationale, on the command**: Principle VII. If the lane runs a bespoke sequence, there are
two ways to run the gate, they drift, and the one nobody runs locally is the one that rots.
The lane should be thin enough that its content is uninteresting — install the toolchain,
write the licence, `make dev-up`, `make conformance`.

**What this depends on that I cannot provide**: the licence in repository secrets. The lane
is unverifiable without it.

**Alternatives considered**:

- **`pull_request_target`.** Rejected per the above.
- **A scheduled lane on `main` instead of per-PR.** Catches regressions after they land,
  which is not a merge gate.
- **A self-hosted runner holding the licence.** Removes the secret-exposure question and
  adds a machine to operate. Worth revisiting if the hosted lane proves slow, not before.

---

## D8 — How parity is actually compared

**Decision**: drive every operation in 008's committed snapshot through both transports as
the same subject, then compare **the verdict** and **a normalised projection of the audit
events**: event types, order, subject, and decision fields. Transport is recorded as a
field and excluded from the comparison.

**Rationale**: "equivalent audit events" is the easiest thing in this feature to assert
dishonestly. A comparison that checks "both produced some audit" is satisfied by two
surfaces that agree about nothing. Naming the projection makes the assertion falsifiable.

**The prerequisite that is also a check**: the comparison runs against
`specs/008-northbound-api/contracts/operations.snapshot.json`. If that snapshot has drifted
from the API, parity is measuring the wrong thing — so the parity row implicitly re-verifies
008's snapshot check, and a drift shows up here as the first failure rather than as a
mystery later.

**Alternatives considered**:

- **Compare full audit entries.** Fails on timestamps, correlation IDs, and hashes, all of
  which legitimately differ. Would be abandoned within a day and replaced with something
  weaker under time pressure.
- **Compare only verdicts.** Half of ADR-0033's requirement — "the same verdict *and
  equivalent audit events*".

---

## D9 — Check interval and flapping

**Decision**: a bounded check interval, plus **hysteresis on recovery**: a dependency is
marked healthy only after consecutive successful checks, while a single failure marks it
unhealthy.

**Rationale**: asymmetric on purpose. Marking unhealthy fast is safe — the cost is a run
suspending that might have succeeded, which the sweeper resolves. Marking healthy fast is
not: a flapping dependency would resume every waiting run into a product that fails again
immediately, and each cycle consumes real budget against the run's maximum duration. The
failure mode is a run that exhausts its ceiling on retries rather than on work.

**Alternatives considered**:

- **Symmetric thresholds.** Simpler and amplifies flapping into a resume storm.
- **Exponential backoff per run.** Puts the retry decision in each run instead of at the
  platform level, which is the "every run independently rediscovering the same outage"
  shape ADR-0049 rejects.

---

## D10 — What the sweeper runs as

**Decision**: the sweeper runs under the MCP service's own attested identity, and each
resumed run gets a **new allocation with its own new identity**.

**Rationale**: the sweeper's authority is "resume this run", not the run's authority. It
never holds or passes the run's credentials — the resumed allocation manufactures its own,
which is what makes re-authentication structural rather than a rule (ADR-0048). A sweeper
that carried a run's credential forward would reintroduce replay through the back door,
after 005 spent a whole feature making it unavailable.

**Alternatives considered**:

- **The sweeper resumes runs in-process.** Would mean the sweeper's identity executing the
  run's work — every resumed run acting as the service rather than as its subject.
- **Runs poll for their own dependency.** Requires a suspended run to still be running,
  which contradicts FR-011 and ADR-0049's "a suspended run is a record, not a process".
