# SPDX-License-Identifier: Apache-2.0
"""054's run-scoped write rows.

**Its own directory, and not `authority/`, for a reason worth stating.** 018's
`test_nothing_here_widens_authority` forbids any module under `tests/conformance/authority`
from writing a policy — the sharpest safety property in that feature would otherwise rest on
nobody adding such a fixture later. 054's rows must do exactly that: seed a workspace
belonging to another run, and (row E5) restore the estate-wide grant to prove the safety case
can lose. Both are legitimate here and forbidden there, so the rows moved rather than the rule
bending.

**Marked `enclave` AND `host_enclave`, following 018.** `enclave` keeps them out of the
hermetic lane; `host_enclave` selects them in the lane that names this directory, and is also
simply true — a row that drives the scheduler cannot run inside something the scheduler placed.

**The directory had to be added to that lane by hand**, and forgetting is the trap this
repository has paid for three times: `make conformance` runs `-m enclave` over an explicit list
that does not include this path, so ten green rows would have run in no lane at all. The
Makefile's own comment records 018 nearly shipping exactly that.
"""
