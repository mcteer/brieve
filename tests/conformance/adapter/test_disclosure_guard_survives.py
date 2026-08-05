# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the unreachable-wrapper guard survives disclosure (D7).

036 needed a toolset wrapper outside governance, and the obvious way to get one was to
delete or loosen `_reject_unreachable_wrappers`. That guard exists because `GovernedToolset`
is terminal: a co-resident capability's wrapper is never reached, so installing one without
complaint leaves it *looking* active while doing nothing — the silent-pass failure ADR-0047
exists to prevent.

The feature took the other route. The disclosure composition is a capability the **adapter
constructs**, whose ordering it states; the guard still refuses every wrapper handed in from
outside. This row is the regression test for that distinction, because "we needed a wrapper
so we removed the check" is the change a future reader will be tempted to make.
"""

from __future__ import annotations

import pytest
from pydantic_ai.capabilities import ToolSearch
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from adapters.pydantic_ai.agent import build_governed_agent
from adapters.pydantic_ai.tools import GovernedToolError


def _model() -> FunctionModel:
    return FunctionModel(lambda m, i: ModelResponse(parts=[TextPart(content="x")]))


def test_a_caller_supplied_toolset_wrapper_is_still_refused() -> None:
    """The guard, unchanged: governance will not silently swallow somebody's wrapper."""
    with pytest.raises(GovernedToolError) as raised:
        build_governed_agent(_model(), capabilities=[ToolSearch()])
    assert raised.value.reason_code == "unreachable_capability_wrapper"


def test_the_guard_holds_even_when_disclosure_is_on() -> None:
    """Opting into disclosure does not open the door for arbitrary wrappers.

    The sharpest case: a caller passes the very capability the feature installs internally.
    It is still refused, because what makes the adapter's own composition safe is that the
    adapter states its ordering — not the class of capability involved.
    """
    with pytest.raises(GovernedToolError) as raised:
        build_governed_agent(_model(), capabilities=[ToolSearch()], defer_disclosure=True)
    assert raised.value.reason_code == "unreachable_capability_wrapper"


def test_disclosure_builds_through_its_own_door() -> None:
    """And the supported path works — otherwise the rows above would pass trivially."""
    agent = build_governed_agent(_model(), defer_disclosure=True)
    assert agent is not None
