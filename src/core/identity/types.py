# SPDX-License-Identifier: Apache-2.0
"""The authenticated subject — the root of the delegation chain.

Defined in core rather than in a transport. Principle V names identity flows as sealed
core, and a type this central defined inside the *first* transport would leave the second
either importing the first or duplicating it. Core defines the subject; each transport
produces one. What stays in the transport is the part that needs a token library.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class SubjectKind(StrEnum):
    #: A person, via the organization's own OIDC provider.
    HUMAN = "human"
    #: A machine, via workload identity federation. Never a static key.
    WORKLOAD = "workload"


class AuthenticatedSubject(BaseModel):
    """Established at the surface; the subject of everything downstream.

    Not a session. Nothing is stored server-side, because storing it would be the
    credential store the platform deliberately does not operate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_user_id: str
    #: From an IdP claim. The outermost dimension of every evidence query.
    tenant_id: str
    #: Result of claim-to-role mapping. **Empty means refuse** — never a default role.
    roles: frozenset[str]
    subject_kind: SubjectKind
    #: The token's own expiry. Never extended, never honoured past.
    expires_at: datetime


__all__ = ["AuthenticatedSubject", "SubjectKind"]
