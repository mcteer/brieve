# SPDX-License-Identifier: Apache-2.0
"""Claim-to-role mapping — governed configuration, shared by every transport.

Pure data-to-roles with no dependency on how a token arrived, which is why it is here and
not beside the JWT verification. Changing a mapping is an authority change gated by quorum
(ADR-0016), not an administrative edit: without that, anyone with configuration access
grants themselves a role rather than being granted one.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ClaimMapping(BaseModel):
    """One claim value granting one role."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_name: str
    claim_value: str
    role: str


def resolve_roles(claims: dict[str, Any], mappings: list[ClaimMapping]) -> frozenset[str]:
    """Return the roles these claims map to.

    An **empty result means refuse**, and the caller must treat it that way. An unmapped
    claim is not a default role: the absence of a mapping is the absence of permission,
    and resolving it to anything else is the escalation path ADR-0033 closes.

    A claim whose value is a list grants every mapping matching any element, so
    ``groups: ["a", "b"]`` behaves the way an operator would expect rather than silently
    matching nothing.
    """
    granted: set[str] = set()
    for mapping in mappings:
        if mapping.claim_name not in claims:
            continue
        value = claims[mapping.claim_name]
        values = value if isinstance(value, (list, tuple, set, frozenset)) else [value]
        if any(str(v) == mapping.claim_value for v in values):
            granted.add(mapping.role)
    return frozenset(granted)


__all__ = ["ClaimMapping", "resolve_roles"]
