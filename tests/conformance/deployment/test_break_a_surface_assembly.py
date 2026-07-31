# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — the gate detects a surface that cannot start (017, FR-012).

**A gate nobody has seen fail is a gate nobody knows works**, which is this feature's whole
thesis applied to itself.

The full demonstration is manual and recorded in the conformance contract with its output:
the API was submitted pointed at a Vault role that does not exist, and the lane failed
naming the API and printing the API's own error. It is not automated here because doing so
means editing source, redeploying, and waiting out a cold start — minutes per run, on every
run, to re-prove something that does not change. That is a deliberate limit, recorded per
ADR-0047 rather than papered over.

What IS automated is the detection mechanism underneath it: an absent surface must FAIL and
must never skip, and the failure must carry the process's own account rather than only that
an assertion did not hold. Those are the two properties a broken assembly relies on, and
they are cheap to assert against a job that does not exist.
"""

from __future__ import annotations

import pytest

from tests.conformance.deployment import conftest as helpers

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: A job the scheduler has never heard of. Stands in for "the assembly died before serving",
#: which is what a broken credential role produces — the allocation is gone or never placed.
ABSENT = "no-such-surface-017"


def test_an_absent_surface_fails_rather_than_skipping() -> None:
    """FR-006. A gate that skipped here would report green for the state it exists to catch."""
    with pytest.raises(helpers.SurfaceUnreachable) as refusal:
        helpers.wait_for_working_state(ABSENT)

    assert ABSENT in str(refusal.value), "the failure does not name the surface (FR-004)"


def test_the_failure_says_no_allocation_was_placed() -> None:
    """FR-004: the verdict must be attributable, not merely negative.

    "did not reach a working state" plus what the surface itself said is the difference
    between a report someone can act on and one that sends them to the wrong component.
    """
    with pytest.raises(helpers.SurfaceUnreachable) as refusal:
        helpers.wait_for_working_state(ABSENT)

    message = str(refusal.value)
    assert "did not reach a working state" in message
    assert "no allocation was ever placed" in message, (
        "the failure does not distinguish 'never placed' from 'placed and broken', which "
        "are different problems with different first steps"
    )
