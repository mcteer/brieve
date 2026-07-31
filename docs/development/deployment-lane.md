<!-- SPDX-License-Identifier: Apache-2.0 -->
# The deployment lane

Proves the **deployed** processes run. Every other gate asserts about a process the test
itself constructs; this one asserts about the process a deployment constructs — the one code
path with no coverage by construction, because component tests build the application with
substitutes and the served process is a different object.

## Running it

```bash
make dev-up          # if the enclave is not up
make conformance     # the lane is its final line
```

Or on its own, against surfaces you already have:

```bash
bash infra/bin/deployment-conformance
bash infra/bin/deployment-conformance --repeat 3   # determinism (SC-008)
```

## What it asserts, and what it does not

**Reach, not correctness.** A collaborator wired to the *wrong* place still assembles,
answers, and passes. What this closes is the class where a collaborator is wired to
*nothing*. Calling it proof the deployment is correct would be an overstatement.

The assertions are **refusals**, not successes: an unauthenticated request must return the
surface's own reason code. A success needs a valid end-user token from an external provider,
and a merge gate depending on a third party's availability trades one flaky class for
another.

## Adding a process

Every job definition must be a **declared subject** or an **explicit exclusion**. Neither
fails the gate — coverage a process opts into is fail-open, and the process nobody remembered
to enrol is exactly the one nobody remembered to cover.

Declare it in its own `.nomad.hcl`:

```hcl
meta {
  harness_surface     = "true"
  harness_shape       = "served"          # or "dispatched"
  harness_covered_by  = "tests/conformance/deployment/test_your_surface.py"
  harness_lane_starts = "true"            # does this lane stand it up?
  harness_started_by  = var.harness_started_by
}
```

Or exclude it in `tests/conformance/deployment/surfaces.py` with a reason. Exclusions are
checked against the filesystem, so a stale one fails rather than hides.

## Two traps that cost real time

**Host networking is the VM's host, not yours.** Both surfaces use `network_mode = "host"`.
On a Linux runner a shell reaches `127.0.0.1:8081`; on Docker Desktop for macOS it does not.
Rows reach surfaces through `nomad alloc exec`, which is uniform on both — a row that curled
from the shell would pass in CI and fail locally for a reason unrelated to the tree.

**`nomad job run` against an unchanged jobspec places nothing.** It compares the spec, finds
no difference, and leaves the old allocation serving old code. The runner forces a new one.
The same trap is why `enclave-conformance` purges before submitting.

And one worth knowing when reading Nomad output: **flags go after the subcommand and before
positionals**, and a misplaced one can exit **zero** with a usage message. `nomad job status
api -address=X` prints "takes either no arguments or one" and returns 0, so a caller that
trusted the return code would read garbage as an empty result.

## The lifecycle

The gate owns the processes it starts, and the mark that says so lives in the job's `Meta`
rather than in the running gate's memory — an in-process record dies with the run, and a
later invocation could then only guess which surfaces were leftovers and which someone
started themselves. Both guesses are wrong.

| | |
|---|---|
| **Already running** | reused, never restarted — unmarked processes are not the gate's |
| **Passing run** | stops exactly what it started; spare capacity returns to what it was |
| **Failing run** | leaves them standing and says so — the allocation is what you need |
| **Next run** | reclaims leftovers *early*, in `enclave-conformance`'s purge phase, before the batch job needs that capacity |
| **A stop that fails** | fails the gate; swallowed, it reports green from the mechanism built to prevent that |

Clear a failed run's leftovers yourself with `make deployment-down`, or just run the gate
again.
