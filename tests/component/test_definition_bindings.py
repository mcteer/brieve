# SPDX-License-Identifier: Apache-2.0
"""The definition-bindings record: the three fields the whole feature reads.

Until analyze pass 8 `packs`, `binding_map`, and `tier` lived in the glossary, in four
tasks' logic, and in no record at all — every consumer written against something nothing
produced. These rows exist over the parser rather than only over the Vault reader, because
the parser is where a malformed record has to fail and the reader needs an enclave.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.bindings import DEFAULT_TIER, parse_definition_bindings
from core.authority.errors import ResolutionRefused


def _record(**overrides: Any) -> dict[str, Any]:
    return {"schema_version": 1, "agent_definition_id": "applier", **overrides}


def test_the_three_fields_round_trip() -> None:
    bindings = parse_definition_bindings(
        _record(packs=["vault"], binding_map={"write": "vault:m@1:write"}, tier=2),
        agent_definition_id="applier",
    )
    assert bindings.packs == frozenset({"vault"})
    assert bindings.binding_map == {"write": "vault:m@1:write"}
    assert bindings.tier == 2


def test_a_definition_naming_nothing_gets_the_narrowest_defaults() -> None:
    """What every pre-013 fixture is.

    008-012's definitions name no pack and bind no model, and a dozen conformance lanes run
    against them. The defaults must be the narrowest thing that still runs — no packs, no
    bindings, paved paths only — because a definition acquiring capability by *omission*
    would be widening arriving through a default.
    """
    bindings = parse_definition_bindings(_record(), agent_definition_id="planner")
    assert bindings.packs == frozenset()
    assert bindings.binding_map == {}
    assert bindings.tier == DEFAULT_TIER


@pytest.mark.parametrize("version", [None, 0, 2, "1"])
def test_an_unsupported_schema_version_refuses(version: object) -> None:
    """Absent and newer land in the same place, as `parse_ceiling_record` does it."""
    with pytest.raises(ResolutionRefused) as caught:
        parse_definition_bindings({"schema_version": version}, agent_definition_id="a")
    assert caught.value.reason_code == "unsupported_schema_version"


@pytest.mark.parametrize("tier", [0, -1, "two", 1.5, True])
def test_a_tier_that_is_not_a_positive_integer_refuses(tier: object) -> None:
    """`True` is in this list deliberately.

    `isinstance(True, int)` is true in Python, so a bool would otherwise parse as tier 1 and
    a record saying `tier = true` would silently become the narrowest valid tier instead of
    refusing as the malformed record it is.
    """
    with pytest.raises(ResolutionRefused) as caught:
        parse_definition_bindings(_record(tier=tier), agent_definition_id="a")
    assert caught.value.reason_code == "malformed_record"
