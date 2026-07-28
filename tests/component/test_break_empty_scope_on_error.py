# SPDX-License-Identifier: Apache-2.0
"""Break fixture — a fabric that returns an empty scope on error.

**The most likely regression in this feature, and the one that passes almost everything.**
Returning `AuthorityScope()` from an exception handler is the shortest path in
`vault_fabric.py`, it reads as fail-closed, and it produces a denial — so every row in this
repository that asserts "the call was denied" still passes. What it destroys is the
distinction between *this person may do nothing* and *the platform could not find out*,
which is the difference between a permissions decision and an outage.

The fixture below IS that mistake, constructed deliberately. The assertions show what it
survives and what catches it, because a break fixture whose failure is obvious teaches
nothing.
"""

from __future__ import annotations

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from tests.harness import capture_audit, frozen_clock
from tests.harness.fake_identity_fabric import DEFAULT_AGENT_DEFINITION_ID


class FabricThatSwallowsErrors:
    """The mistake: every failure becomes an empty scope.

    Note how reasonable it looks. Every method fails closed, nothing raises out of the
    fabric, and a run under it is refused rather than permitted.
    """

    def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
        try:
            raise ResolutionRefused("fabric down", reason_code="fabric_unreachable")
        except ResolutionRefused:
            return AuthorityScope()

    def resolve_ceiling(self, agent_definition_id: str) -> AuthorityScope:
        try:
            raise ResolutionRefused("fabric down", reason_code="fabric_unreachable")
        except ResolutionRefused:
            return AuthorityScope()

    def resolve_policy(self, agent_definition_id: str) -> AuthorityScope | None:
        return None

    def resolve_product_entitlements(self, subject_user_id: str, product: str) -> frozenset[str]:
        return frozenset()


def _start(fabric: object) -> object:
    registry = ToolRegistry()
    registry.register("echo", lambda _arguments: {"ok": "ran"})
    return start_governed_run(
        correlation_id="corr-swallow",
        subject_user_id="user-1",
        agent_definition_id=DEFAULT_AGENT_DEFINITION_ID,
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"})),
        identity_fabric=fabric,  # type: ignore[arg-type]
        registry=registry,
        clock=frozen_clock(),
        audit_sink=capture_audit(),
    )


def test_the_mistake_still_produces_a_denial() -> None:
    """What it survives: every assertion of the form "the run was refused".

    This is why the fixture exists. A reviewer looking at outcomes sees correct behaviour.
    """
    from core.authority.errors import AuthorityRefuseError

    with pytest.raises(AuthorityRefuseError):
        _start(FabricThatSwallowsErrors())


def test_but_the_refusal_reports_the_wrong_thing() -> None:
    """What catches it: the reason code.

    A run refused because the trust fabric was unreachable reports `authority_refused` —
    scope exceeded — under this fabric. An operator reads that as "the request asked for
    too much" and goes to check the ceiling, which is correct and unrelated. The outage is
    invisible.
    """
    from core.authority.errors import AuthorityRefuseError

    with pytest.raises(AuthorityRefuseError) as caught:
        _start(FabricThatSwallowsErrors())

    assert caught.value.reason_code == "authority_refused", (
        "the swallowing fabric no longer reports a scope error — if this changes, the "
        "fixture has stopped modelling the mistake it exists to model"
    )
    assert caught.value.reason_code != "fabric_unreachable"


def test_the_real_fabric_reports_the_outage() -> None:
    """The contrast, which is the whole point.

    The production fabric raises through, so the same failure arrives with a reason code
    that names the fabric — and an operator goes to the right system.
    """
    from core.authority.vault_fabric import VaultIdentityFabric
    from core.durability.credentials import VaultReadFailed

    class DeadTransport:
        def read_path(self, path: str, *, token: str | None = None) -> dict[str, object] | None:
            raise VaultReadFailed("down")

    fabric = VaultIdentityFabric(
        credentials=DeadTransport(),  # type: ignore[arg-type]
        known_tools=frozenset({"echo"}),
        known_actions=frozenset(),
    )

    with pytest.raises(ResolutionRefused) as caught:
        fabric.resolve_ceiling(DEFAULT_AGENT_DEFINITION_ID)

    assert caught.value.reason_code == "fabric_unreachable"
