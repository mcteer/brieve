# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the ordering assertion actually fires when order is inverted.

**This test passes on a clean tree.** It is self-verifying: it deliberately
constructs the inverted arrangement and asserts that
``assert_governance_first`` *raises*. A gate nobody has watched fail is a gate
nobody knows works — SC-003 requires that at least one case fails if governance
order is reversed, and this is how that claim is checked without leaving a red
test in the suite.
"""

from __future__ import annotations

import pytest

from tests.conformance.adapter.test_governance_order import assert_governance_first
from tests.harness.adapter_fixtures import CountingHandler


def test_ordering_assertion_fails_when_governance_is_not_first() -> None:
    """Invert the observed order; the shared assertion must reject it."""
    handler = CountingHandler()
    handler.call_count = 1  # allow path otherwise satisfied
    # A co-resident capability that saw nothing recorded: governance had not run.
    inverted = ["co-resident:saw=nothing"]

    with pytest.raises(AssertionError, match="before governance"):
        assert_governance_first(inverted, handler)


def test_ordering_assertion_fails_when_co_resident_never_runs() -> None:
    """An empty probe log means ordering was never observed — not a pass."""
    handler = CountingHandler()
    handler.call_count = 1

    with pytest.raises(AssertionError, match="unobservable"):
        assert_governance_first([], handler)


def test_ordering_assertion_fails_when_tool_body_did_not_run() -> None:
    """Zero executions on the allow path is a failure, not a vacuous success."""
    handler = CountingHandler()

    with pytest.raises(AssertionError, match="exactly once"):
        assert_governance_first(["co-resident:saw=pre:adapter_governance"], handler)
