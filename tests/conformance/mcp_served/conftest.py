# SPDX-License-Identifier: Apache-2.0
"""Fixtures for the served-surface rows.

**Both markers live in the test MODULES, not here, and that is not a style choice.**
`pytestmark` in a conftest applies only to tests defined in the conftest itself — it does not
mark the modules beside it. Setting it here left every row unmarked, so the hermetic lane
collected rows that need a running surface and reported four errors.

Worse, it passed the lane-membership check *vacuously*:
`tests/unit/test_every_conformance_directory_is_run.py` scans `test_*.py` for markers, found
none in this directory, and concluded there was nothing to require a lane for. A check that
cannot see a marker cannot notice a lane that would deselect it.

The marks themselves: `enclave` because these need the enclave standing; `host_enclave`
because they run from the developer's machine rather than inside an allocation — the client
on the outside is the property FR-014 is about, and a row that ran inside the platform's
network would keep passing while meaning nothing.
"""

from __future__ import annotations

import pytest

from tests.conformance.mcp_served import surfaces

#: The allocation the first row in this session saw. Kept only so a REPLACEMENT can be named.
_FIRST_SEEN: list[str] = []


@pytest.fixture
def running_surface() -> str:
    """The allocation, or a failure that says the surface is absent rather than refusing.

    'Nothing replied' and 'the surface refused' are different findings and the second is the
    only interesting one. A fixture that let an absent surface read as a denial would make
    every refusal row in this directory satisfiable by the platform being down.

    **Resolved per row, not per session.** It was session-scoped, and the allocation id is not
    stable for a session's lifetime: anything that restarts `mcp-surface` mid-run — another
    lane, an operator, Nomad rescheduling — replaces it, and every row still holding the old id
    fails at once. That presented as seven unrelated failures in a full-suite run and none in a
    repeat, which reads as flake and is not: the surface really had moved.
    """
    alloc = surfaces.allocation()
    if alloc is None:
        pytest.fail(
            "no running mcp-surface allocation. These rows drive the SERVED process; they "
            "cannot be satisfied by constructing anything. Bring it up with "
            "`make mcp-surface-up`, or run the whole lane with "
            "`bash infra/bin/mcp-surface-conformance`."
        )
    # A replacement is REPORTED rather than absorbed. Re-resolving keeps the rows correct; a
    # silent re-resolve would also hide a surface that is restart-looping, which is a finding.
    if not _FIRST_SEEN:
        _FIRST_SEEN.append(alloc)
    elif alloc != _FIRST_SEEN[0]:
        print(
            f"\nmcp-surface was replaced mid-run: {_FIRST_SEEN[0]} -> {alloc}. Rows continue "
            f"against the live allocation; if this repeats, the surface is restart-looping.",
            flush=True,
        )
        _FIRST_SEEN[0] = alloc
    return alloc


@pytest.fixture
def caller(running_surface: str) -> str:
    """A real bearer token for an ordinary caller, from the provider the surface trusts."""
    # `permissions: platform:operator` is what the deployed claim mapping grants. A token
    # without it is refused, correctly — and a fixture that produced one could never tell
    # "the platform refused an unmapped claim" from "the surface is broken".
    return surfaces.caller_token(
        subject="caller-1", tenant="tenant-local", permissions=["platform:operator"]
    )


@pytest.fixture
def other_caller(running_surface: str) -> str:
    """A second, different person — so FR-011 can assert they are DISTINGUISHABLE.

    A single caller could only ever show that *a* subject was recorded, which passes
    perfectly against a shared service account. That is the defect this whole feature exists
    to prevent, and one token could not catch it.
    """
    return surfaces.caller_token(
        subject="caller-2", tenant="tenant-local", permissions=["platform:operator"]
    )
