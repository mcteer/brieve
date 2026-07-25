# SPDX-License-Identifier: Apache-2.0
"""assert_scope_narrowed passes on narrowed tokens and fails on amplified."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.harness import assert_scope_narrowed

from core.authority.types import AuthorityScope, TaskCredentialRef


def _token(tools: set[str], actions: set[str] | None = None) -> TaskCredentialRef:
    return TaskCredentialRef(
        credential_id="cred-1",
        subject_user_id="user-1",
        expires_at=datetime(2026, 1, 1, tzinfo=UTC),
        effective=AuthorityScope(
            tool_names=frozenset(tools),
            product_actions=frozenset(actions or ()),
        ),
    )


def test_narrowed_passes() -> None:
    user = AuthorityScope(tool_names=frozenset({"a", "b"}), product_actions=frozenset({"p"}))
    assert_scope_narrowed(_token({"a"}, {"p"}), at_most=user)


def test_amplified_fails() -> None:
    user = AuthorityScope(tool_names=frozenset({"a"}), product_actions=frozenset())
    with pytest.raises(AssertionError):
        assert_scope_narrowed(_token({"a", "b"}), at_most=user)
