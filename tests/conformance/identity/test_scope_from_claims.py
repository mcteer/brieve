# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a person's authority comes from their identity (SC-004).

008 verifies a token and resolves its claims to roles; 007 governs the claim-to-role
mappings behind multi-party approval. What did not exist until 010 is the step from a role
to an authority scope — so a real, verified, correctly-mapped user still got their scope
from a fixture.

# HYBRID(user_scope): migrated at T046a
User scope resolves through the production fabric; ceiling and policy through the fake.

**Two users, and the difference has to be measurable.** "Scope comes from identity" is
satisfied trivially by a fabric that gives everyone the same thing — which is exactly what
the fake did, and what nobody noticed for eight features.
"""

from __future__ import annotations

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.vault_fabric import SubjectScopedVaultFabric
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from tests.conformance.identity.conftest import KNOWN_ACTIONS, KNOWN_TOOLS

pytestmark = pytest.mark.enclave


def _fabric_for(*roles: str) -> SubjectScopedVaultFabric:
    return SubjectScopedVaultFabric(
        roles=roles,
        credentials=VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="conformance"),
        known_tools=KNOWN_TOOLS,
        known_actions=KNOWN_ACTIONS,
    )


def test_row_two_roles_resolve_to_different_authority() -> None:
    """The measurable difference SC-004 asks for, from records an operator wrote."""
    reader = _fabric_for("reader").resolve_user_scope("alice")
    operator = _fabric_for("operator").resolve_user_scope("bob")

    assert reader.tool_names != operator.tool_names
    assert "apply" in operator.tool_names
    assert "apply" not in reader.tool_names, (
        "the reader role resolved to a scope including apply — either the binding record "
        "is wrong or the fabric is not reading it"
    )


def test_row_a_second_role_only_adds() -> None:
    """Union across roles, against the live records (FR-006).

    Intersection is the alternative that reads as conservative, and it would mean being
    granted a second role could take access away — which nobody would predict from being
    given one.
    """
    reader = _fabric_for("reader").resolve_user_scope("alice")
    both = _fabric_for("reader", "operator").resolve_user_scope("alice")

    assert reader.tool_names < both.tool_names
    assert reader.product_actions <= both.product_actions


def test_row_an_unbound_role_refuses() -> None:
    """A role nobody has bound is not an empty scope.

    Nobody has said what this role means, which is a different situation from it meaning
    nothing — and only one of the two is a statement about the person's permissions.
    """
    with pytest.raises(ResolutionRefused) as caught:
        _fabric_for("no-such-role").resolve_user_scope("alice")

    assert caught.value.reason_code == "unbound_role"


def test_row_no_role_at_all_refuses() -> None:
    """Authenticated and mapped to nothing. Never an empty scope (FR-007)."""
    with pytest.raises(ResolutionRefused) as caught:
        _fabric_for().resolve_user_scope("alice")

    assert caught.value.reason_code == "no_role_for_subject"
