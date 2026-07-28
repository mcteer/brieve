# Quickstart: MCP Surface

**Feature**: `specs/009-mcp-surface` | **Date**: 2026-07-27

How to run this feature and prove it works. Validation guide — implementation belongs in
`tasks.md`.

## Prerequisites

```bash
make dev-up        # Terraform -> Vault -> Nomad -> harness, plus the MCP service
make dev-status    # Nomad up, Vault up (unsealed), Postgres up
```

`make dev-up` now also brings up a **persistent** service. That is new: everything else the
enclave runs is a batch job that ends when its work ends, and ADR-0049 makes that ending part
of the guarantee. If the MCP service is not running, the health checker is not checking and
the sweeper is not sweeping — suspended runs will simply stay suspended, which looks like a
hang and is not one.

## What is faked, and what is not

**The products agents operate are faked**; they are outside our boundary. Everything else —
Vault, Postgres, the scheduler, allocations, the MCP protocol itself — is real.

Making a fake product unreachable is how dependency outages are simulated. That is the correct
place to fake, and it is also the only way to test an outage without breaking something you
need for the rest of the suite.

## Validation

### 1. Hermetic

```bash
make check          # lint, typecheck, unit + component
```

### 2. The full lane

```bash
make conformance
```

### 3. The one CI now runs for you

```bash
# On a pull request from a branch in this repository:
#   the enclave lane stands the stack up and runs `make conformance`.
# On a pull request from a fork:
#   the fast lane runs; the enclave lane does not.
```

**This is the change worth checking by hand once.** Push a branch with a deliberately broken
enclave row and confirm the lane fails. Sixteen merge-blocking rows have been protected by an
instruction in `AGENTS.md` until now, and the point of this feature is that they stop being.

### 4. The four things worth checking by hand

Each is easy to implement in a way that passes tests without holding.

**Parity is comparing something.** Add an operation to MCP and not the API:

```bash
# Expected: the coverage row fails, naming the operation and the transport.
# If it passes, the comparison is enumerating one side.
```

**The refusal is where it says it is.** Not "a refused call was refused" — check placement:

```bash
# Mark a dependency unhealthy, attempt a call, and read the trail.
# Expected: the pre-decision hook records the refusal, in hook order.
# If the denial appears without hook records, the gate has been moved to a pre-flight
# and works — which is exactly the failure the placement row exists for.
```

**A suspended run holds nothing.** Suspend a run and look at the scheduler:

```bash
# Expected: no allocation running for it. A suspended run is a record.
# An idling container is the ADR-0049 violation that costs nothing until it costs a slot
# per suspended run.
```

**The sweep re-attests.** Restore the dependency and watch the resumption:

```bash
# Expected: a NEW allocation, with a new identity.
# Resuming into the same allocation would look identical from outside — the run completes
# either way. Only the new-identity assertion tells replay from re-authentication.
```

### 5. The denial classes

```bash
# Refuse a call for scope, and one for availability.
# Expected in the trail: distinguishable classes.
# Expected in what the model sees: the availability refusal invites an alternative;
#   the scope refusal does not.
```

Getting this backwards is the subtlest failure available here. An agent told a scope refusal
is adaptable will look for another route, which is the one behaviour the governance layer
exists to prevent — and nothing would break visibly.

## What you will not find

- **No prompt, notification, or approval queue.** Nothing here waits on a human (FR-014).
  If you find yourself looking for where to approve something, the absence is the feature.
- **No `PARKED`.** ADR-0049 removed the category; grant expiry stops and a dependency
  suspends.
- **No retry counter on a suspended run.** It waits on a named machine condition, not a
  clock and not an attempt budget.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Suspended runs never resume | The MCP service is not running, so nothing sweeps. `make dev-status` |
| Every call refuses after a restart | Health starts unknown, and unknown is unhealthy — by design. It resolves on the first check |
| A recovered dependency does not resume runs immediately | Recovery is hysteretic: several consecutive successes, deliberately, so a flapping product does not resume every waiting run into another failure |
| The enclave CI lane does not run | Expected on fork pull requests — it needs a licence secret. Check the head repository |
| The enclave lane fails at bring-up | Reads as a failure, never a pass. That is FR-020 working |
