# SPDX-License-Identifier: Apache-2.0
"""The entitlement seam is real; the product behind it is not (spec C2).

ADR-0044's compensating control: where a brokered credential is coarser than the
individual user, the requester's **own** effective entitlements are resolved and enforced
before that credential is wielded, so an agent cannot exceed the person it acts for.

Until 010 the answer came from a dictionary keyed by `(user, product)` inside the identity
fake. The product stays faked — its authorization system is outside this platform's
boundary and the constitution says to keep it that way — but the interface that *asks* a
product is ours, and it did not exist. Keeping the product faked is a decision; having no
way to ask one was a gap.
"""

from __future__ import annotations

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.vault_fabric import VaultIdentityFabric
from tests.harness.fake_product_api import FakeProductApi

TOOLS = frozenset({"echo", "plan", "apply"})
ACTIONS = frozenset({"product.workspace.read", "product.workspace.write"})


def _fabric(source: FakeProductApi | None) -> VaultIdentityFabric:
    return VaultIdentityFabric(
        # Not reached: these rows exercise the entitlement seam, which needs no transport.
        credentials=object(),  # type: ignore[arg-type]
        known_tools=TOOLS,
        known_actions=ACTIONS,
        entitlement_source=source,
    )


def test_the_seam_returns_what_the_product_says() -> None:
    """The positive control, and the shape of the whole seam in one line."""
    product = FakeProductApi(entitlements={"alice": frozenset({"product.workspace.read"})})

    assert _fabric(product).resolve_product_entitlements("alice", "workspace") == frozenset(
        {"product.workspace.read"}
    )


def test_a_user_the_product_does_not_know_has_nothing() -> None:
    """Empty is a legitimate answer: this person may do nothing here.

    Distinct from the row below, and the distinction is the entire point of the seam.
    """
    product = FakeProductApi(entitlements={"alice": frozenset({"product.workspace.read"})})

    assert _fabric(product).resolve_product_entitlements("bob", "workspace") == frozenset()


def test_an_unreachable_product_refuses_rather_than_returning_empty() -> None:
    """FR-011. Unknown is neither empty nor full.

    Returning empty would deny with a reason nobody decided — it reads as fail-closed and
    reports a permissions answer where the truth is that nobody could be asked. Returning
    full is the catastrophe nobody would write on purpose and that a `.get(..., ALL)`
    default would produce.
    """
    with pytest.raises(ResolutionRefused) as caught:
        _fabric(FakeProductApi(unreachable=True)).resolve_product_entitlements("alice", "workspace")

    assert caught.value.reason_code == "entitlement_unavailable"


def test_no_configured_source_refuses() -> None:
    """A deployment that never wired a source must not silently permit or silently deny."""
    with pytest.raises(ResolutionRefused) as caught:
        _fabric(None).resolve_product_entitlements("alice", "workspace")

    assert caught.value.reason_code == "entitlement_unavailable"
