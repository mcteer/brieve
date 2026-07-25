# SPDX-License-Identifier: Apache-2.0
"""Fake identity fabric — user/ceiling/policy/entitlements with fault injection."""

from __future__ import annotations

from dataclasses import dataclass, field

from core.authority.types import AuthorityScope
from tests.harness.secrets import BROKERED_GRAIN_MARKER


class FabricFault(Exception):
    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


@dataclass
class FakeIdentityFabric:
    users: dict[str, AuthorityScope] = field(default_factory=dict)
    ceiling: AuthorityScope = field(default_factory=AuthorityScope)
    policy: AuthorityScope | None = None
    entitlements: dict[tuple[str, str], frozenset[str]] = field(default_factory=dict)
    brokered: dict[str, str] = field(default_factory=dict)

    fail_user: bool = False
    fail_ceiling: bool = False
    fail_policy: bool = False
    fail_entitlements: bool = False
    fail_exchange: bool = False
    fail_reason: str = "identity_unavailable"

    def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
        if self.fail_user:
            raise FabricFault("user resolution failed", reason_code=self.fail_reason)
        if subject_user_id not in self.users:
            raise FabricFault("unknown user", reason_code="identity_unavailable")
        return self.users[subject_user_id]

    def resolve_ceiling(self) -> AuthorityScope:
        if self.fail_ceiling:
            raise FabricFault("ceiling resolution failed", reason_code=self.fail_reason)
        return self.ceiling

    def resolve_policy(self) -> AuthorityScope | None:
        if self.fail_policy:
            raise FabricFault("policy resolution failed", reason_code=self.fail_reason)
        return self.policy

    def resolve_product_entitlements(self, subject_user_id: str, product: str) -> frozenset[str]:
        if self.fail_entitlements:
            raise FabricFault("entitlement resolution failed", reason_code=self.fail_reason)
        return self.entitlements.get((subject_user_id, product), frozenset())

    def issue_brokered_material(self, credential_id: str, marker: str) -> None:
        if self.fail_exchange:
            raise FabricFault("exchange failed", reason_code="exchange_failed")
        self.brokered[credential_id] = marker

    def get_brokered_material(self, credential_id: str) -> str | None:
        return self.brokered.get(credential_id)

    def shrink_policy(self, policy: AuthorityScope) -> None:
        """Mid-run policy shrink helper."""
        self.policy = policy

    def shrink_entitlements(
        self, subject_user_id: str, product: str, actions: frozenset[str]
    ) -> None:
        self.entitlements[(subject_user_id, product)] = actions


def fake_identity_fabric(
    *,
    subject_user_id: str = "user-1",
    tool_names: set[str] | frozenset[str] | None = None,
    product_actions: set[str] | frozenset[str] | None = None,
    ceiling_tools: set[str] | frozenset[str] | None = None,
    ceiling_actions: set[str] | frozenset[str] | None = None,
    policy: AuthorityScope | None = None,
    entitlements: dict[tuple[str, str], frozenset[str]] | None = None,
) -> FakeIdentityFabric:
    """Build a happy-path fabric; tools default to {echo} for 002 migration."""
    tools = frozenset(tool_names) if tool_names is not None else frozenset({"echo"})
    actions = frozenset(product_actions) if product_actions is not None else frozenset()
    c_tools = frozenset(ceiling_tools) if ceiling_tools is not None else tools
    c_actions = frozenset(ceiling_actions) if ceiling_actions is not None else actions
    user_scope = AuthorityScope(tool_names=tools, product_actions=actions)
    return FakeIdentityFabric(
        users={subject_user_id: user_scope},
        ceiling=AuthorityScope(tool_names=c_tools, product_actions=c_actions),
        policy=policy,
        entitlements=entitlements or {},
    )


def issue_default_brokered(fabric: FakeIdentityFabric, credential_id: str) -> None:
    fabric.issue_brokered_material(credential_id, BROKERED_GRAIN_MARKER)
