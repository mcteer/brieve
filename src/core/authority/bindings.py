# SPDX-License-Identifier: Apache-2.0
"""What a definition reaches, binds, and may compose — one control-plane record.

**In `core.authority` for the same reason the matrix is**: these three fields are
authorization facts. `packs` decides what a definition can reach, `binding_map` decides
which model it may use per role, and `tier` decides what it may compose. All three are
operator-authored, read-only to a run, and read while establishing what a run may do —
which is the definition of this package.

`core.packs.isolation` consumes this record; it does not own it. A pack module owning the
record that says which packs a definition may reach would put the answer inside the thing
being bounded.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from core.authority.errors import ResolutionRefused

SUPPORTED_SCHEMA_VERSION: Final[int] = 1

#: The narrowest tier: paved paths only. The default for a definition that declares none,
#: because a definition acquiring compositional freedom by omission is widening arriving
#: through a default.
DEFAULT_TIER: Final[int] = 1


@dataclass(frozen=True)
class DefinitionBindings:
    """The three fields the whole of 013 reads.

    Until analyze pass 8 they lived in the glossary, in four tasks' logic, and in no record
    at all — every consumer written against something nothing produced.
    """

    agent_definition_id: str
    packs: frozenset[str]
    #: role → qualified cell reference. Validated against the matrix, not here: this record
    #: says what a definition *claims*, and the matrix says whether the claim is permitted.
    binding_map: dict[str, str]
    tier: int = DEFAULT_TIER


def parse_definition_bindings(
    record: Mapping[str, Any], *, agent_definition_id: str
) -> DefinitionBindings:
    """Validate a bindings record.

    Refuses an unsupported schema version the way `parse_ceiling_record` does — absent and
    newer land in the same place, because a record with no version is either older than
    versioning or hand-written, and both are cases where guessing is how authority gets
    misread.
    """
    version = record.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        raise ResolutionRefused(
            f"definition-bindings record declares schema_version {version!r}; this platform "
            f"understands {SUPPORTED_SCHEMA_VERSION}",
            reason_code="unsupported_schema_version",
        )

    tier = record.get("tier", DEFAULT_TIER)
    if not isinstance(tier, int) or isinstance(tier, bool) or tier < DEFAULT_TIER:
        raise ResolutionRefused(
            f"definition {agent_definition_id!r} declares tier {tier!r}; a tier is an integer "
            f"of at least {DEFAULT_TIER}",
            reason_code="malformed_record",
        )

    return DefinitionBindings(
        agent_definition_id=agent_definition_id,
        packs=frozenset(str(p) for p in record.get("packs") or ()),
        binding_map={str(k): str(v) for k, v in (record.get("binding_map") or {}).items()},
        tier=tier,
    )


__all__ = [
    "DEFAULT_TIER",
    "SUPPORTED_SCHEMA_VERSION",
    "DefinitionBindings",
    "parse_definition_bindings",
]
