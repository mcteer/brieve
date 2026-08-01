<!-- SPDX-License-Identifier: Apache-2.0 -->
# Research: 019 — the MCP surface gets a server

Phase 0. Every finding below was measured against the running platform on 2026-07-31, not
inferred. The spec required exactly one thing to be measured before anything else was scoped,
and it turned out to invalidate the assumption it was checking.

---

## F1. Host-mode ports are NOT reachable from the developer's machine — **the spec's assumption is wrong**

**This was the measurement the clarification demanded come first**, on the grounds that every
estimate downstream depends on it. It does, and the answer is the unfavourable one.

Measured, with the API and portal jobs running and the API's own log confirming
`Uvicorn running on http://0.0.0.0:8081`:

| From | `api` 8081 | `portal` 8082 | `postgres` 5432 |
| --- | --- | --- | --- |
| The Docker VM's host namespace | **200** | **200** | — |
| **macOS** | **unreachable** | **unreachable** | **reachable** |

**Decision**: FR-014 is real work, and per the clarification it stays in scope regardless.

**Why**: `network_mode = "host"` on Docker Desktop puts the container in the **Linux VM's**
network namespace. That namespace is not macOS. A `network { port { static = 8081 } }` block
alongside host mode is inert — Docker publishes nothing, which the container list confirms:
every host-mode allocation shows an empty `Ports` column while the bridge-mode ones show
`127.0.0.1:5432->5432/tcp`.

**The fix already exists in this repository.** `postgres` and `collector-postgres` declare no
`network_mode` at all — bridge, with a mapped port — and both are reachable from macOS. The
host lanes connect to them from macOS on every run, which is not an inference: it is how
today's conformance rows got their database.

| Job | `network_mode` | Reachable from macOS |
| --- | --- | --- |
| `postgres`, `collector-postgres`, `harness-probe` | *(none — bridge)* | **yes** |
| `api`, `portal`, `mcp`, `agent-run`, `conformance` | `host` | **no** |

**Alternatives considered**:

- **Docker Desktop's host-networking support.** A per-developer setting in a GUI. Rejected as
  the primary answer: the repository cannot guarantee a setting it does not own, and a
  reachability requirement satisfied by "ask each developer to tick a box" is not satisfied.
- **A port-forward or proxy alongside the job.** Another moving part whose failure looks
  exactly like the surface being down. Rejected as a workaround for a supported mode already
  proven in-tree.
- **Leaving host mode and documenting the VM address.** Rejected outright — FR-014 says the
  developer's own machine, and the clarification says the feature absorbs the cost.

**The cost, stated plainly, because it is the real one.** Host mode is not decorative. These
jobs use it to reach the scheduler and the trust store at addresses that differ between the
VM and macOS — 014 paid for that lesson when the sweeper's dispatcher defaulted to a loopback
that was correct for a host process and wrong for an allocation. Moving a job to bridge mode
changes what its *outbound* addresses must be, and getting that wrong produces a service that
starts and cannot reach anything. **The new surface should be born in bridge mode rather than
converted**, so nothing already working is disturbed.

---

## F2. `make portal-up` prints an instruction that cannot work

Direct consequence of F1, found while measuring it. The bring-up ends with:

> Then open `http://127.0.0.1:8082/` and sign in.

Measured today: that address does not answer from macOS. The portal serves 200 inside the VM.

**Recorded, not fixed here.** It belongs to the portal, and this feature must not quietly
change another surface's networking while claiming to serve a new one. But it is written down
because the next person to follow that instruction will conclude the platform is broken, and
because it is evidence for the sharper point below.

**What this says about F1 that the table does not.** The instruction was written by someone who
believed the port was reachable. So did this feature's spec. Two independent authors made the
same wrong assumption about the same boundary, which is the signal that the boundary needs a
check rather than a correction.

---

## F3. The identity path already exists and must be reused, not rebuilt

**Decision**: carry the caller's bearer credential on each protocol request and resolve it
through the same verification the API uses.

**Rationale**: `src/surfaces/api/verification.py` already federates verifiers, distinguishes
human from machine credentials, and refuses a machine credential presented where a human is
declared. 016 wired it to a real identity provider. FR-009 through FR-013a describe exactly
what that component already does; a second path to a subject would be a second place for the
subject to be wrong, and the failure is silent by construction.

**How it satisfies FR-013a and FR-013 together**: the subject is resolved once, when the
session is established, and pinned for the session's life. The credential's *validity* is
re-evaluated on every operation. A lapsed credential therefore stops authorizing without the
session ever changing whose it is.

**Alternatives considered**: a session token minted at handshake (rejected — it is a grant that
outlives the credential, precisely what FR-013 forbids); the platform's own workload identity
(rejected — FR-010; it is the shared-account defect the feature exists to prevent, and it
would pass every existing row).

---

## F4. The transport SDK is present, current, and unused

`mcp==1.28.1` is a declared dependency. Nothing in `src/` imports it; no `initialize`,
`tools/list`, or `tools/call` appears anywhere in the tree.

**Decision**: use the SDK for both the server and the acceptance client.

**Rationale**: SC-001's gate is the SDK's own client. A hand-rolled framing on either side
would make the row a test of our framing rather than of the protocol, and the two disagreeing
is the exact defect a conformance row should catch.

---

## F5. The supervisory loop must not share fate — and today it would

FR-015a forbids shared fate. The current `mcp` job runs one process containing health checks,
the sweeper, and audit egress, in a `while` loop.

**Decision**: the served transport is a **separate job** from the supervisory loop.

**Rationale**: it satisfies FR-015a structurally rather than by careful exception handling,
which is the distinction ADR-0025 draws generally. A crash in protocol framing cannot stop
suspended runs from resuming if the two are not in the same process. It also composes with
F1 — the new job is born in bridge mode and the supervisory loop keeps the host-mode home it
already works in, so nothing that works today is disturbed.

**Alternatives considered**: a thread or task inside the existing process (rejected — an
unhandled exception in either half can end the process, and "we will catch everything" is the
promise FR-015a exists because nobody can keep); supervising and restarting in-process
(rejected — more machinery than separation, and it fails in the way it is meant to prevent).

**Consequence to carry into tasks**: the `mcp` job's name currently describes a surface it does
not serve — and it keeps that name. The workload identity binds on it (`variables.tf` defaults
the bound job name to `mcp`; `auth.tf` defines the matching JWT role), so renaming without
re-binding leaves the supervisory loop unable to authenticate. T036 records the bindings a
future rename must update rather than performing one here.

---

## F6. Assembly is the one path no test covers

**Decision**: the conformance rows drive the **served process** over a real socket, and the
lane brings that process up.

**Rationale**: this is ROADMAP gap 0d's lesson and 017 built the lane that learned it. A row
constructing the transport in a fixture asserts what fifty-six rows already assert. FR-004 and
FR-016 exist because the gap being closed is *exactly* the distance between a correct object
and a running service.

**Prior art to follow rather than reinvent**: `tests/conformance/deployment/` and
`infra/bin/deployment-conformance` — 017's lifecycle, including the mark in the job's `Meta`
that distinguishes a lane-started surface from a developer's own.

**A trap this feature must not repeat, recorded because it happened four days ago**: a new
conformance directory must be named by a lane that *selects its markers*. 018 shipped rows no
lane collected and its contract asserted otherwise;
`tests/unit/test_every_conformance_directory_is_run.py` now checks both shapes and will catch
this one automatically.

---

## F7. Where the honest limit has to be repeated

The spec's out-of-scope section says this feature does not put a model in the loop. Research
adds only that the demonstration will be **more** convincing than the feature is broad: a
client attaching to a governed surface, seeing refusals refuse and evidence written, reads as
"the agent platform works." The tool choice is still a scripted round-robin (ROADMAP 0e).

**Decision**: FR-018 is discharged in the conformance contract *and* in whatever setup document
FR-015 produces — the two places a reader arrives from. A limit recorded only where nobody
lands is not recorded.

---

## Unknowns remaining after Phase 0

**None blocking.** One carried forward deliberately: whether the bridge-mode job can reach the
trust store and the scheduler at the addresses it will need. F1 establishes the pattern works
for inbound reachability; outbound is the direction 014 paid for, and it is a first-task
verification rather than a research question — the answer is either "it connects" or "it does
not", observed in one bring-up.
