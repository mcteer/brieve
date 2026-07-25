# SPDX-License-Identifier: Apache-2.0
"""Authority scope and task credential reference types."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuthorityScope(BaseModel):
    """Harness-domain authorization set (tool names + product actions)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_names: frozenset[str] = Field(default_factory=frozenset)
    product_actions: frozenset[str] = Field(default_factory=frozenset)

    def issubset(self, other: AuthorityScope) -> bool:
        return self.tool_names <= other.tool_names and self.product_actions <= other.product_actions

    def intersect(self, other: AuthorityScope) -> AuthorityScope:
        return AuthorityScope(
            tool_names=self.tool_names & other.tool_names,
            product_actions=self.product_actions & other.product_actions,
        )


class TaskCredentialRef(BaseModel):
    """Opaque, non-secret handle bound to a governed run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    credential_id: str
    subject_user_id: str
    expires_at: datetime
    effective: AuthorityScope

    def public_dict(self) -> dict[str, Any]:
        """Fields safe to expose on run-state dumps (no secret material)."""
        return {
            "credential_id": self.credential_id,
            "subject_user_id": self.subject_user_id,
            "expires_at": self.expires_at.isoformat(),
            "effective": {
                "tool_names": sorted(self.effective.tool_names),
                "product_actions": sorted(self.effective.product_actions),
            },
        }
