# SPDX-License-Identifier: Apache-2.0
"""Resolution behaviour of the production fabric, over a fake transport.

The transport is faked, not the fabric — these rows exercise the real
:class:`VaultIdentityFabric`, deciding what it does with what the trust fabric returns.
Whether Vault actually returns those shapes is an enclave row's question; whether the
fabric refuses correctly when it does is this file's, and a live Vault could not make
these cases happen on demand.

**Every row here is about a refusal**, because the refusals are where this component can
be wrong in ways nothing else would notice. A fabric that resolved happily and refused
sloppily would pass every end-to-end assertion in the feature.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.errors import ResolutionRefused
from core.authority.vault_fabric import SubjectScopedVaultFabric, VaultIdentityFabric
from core.durability.credentials import VaultReadFailed

TOOLS = frozenset({"echo", "plan", "apply"})
ACTIONS = frozenset({"product.workspace.read", "product.workspace.write"})


class FakeTransport:
    """Stands in for `VaultDatabaseCredentials`, answering reads from a dict."""

    def __init__(self, paths: dict[str, Any], *, raises: Exception | None = None) -> None:
        self._paths = paths
        self._raises = raises
        self.reads: list[str] = []

    def read_path(self, path: str, *, token: str | None = None) -> dict[str, Any] | None:
        self.reads.append(path)
        if self._raises is not None:
            raise self._raises
        return self._paths.get(path)


def _kv(**data: Any) -> dict[str, Any]:
    """A KV v2 envelope: data nested one level down, as Vault returns it."""
    return {"data": {"data": {"schema_version": 1, **data}}}


def _fabric(paths: dict[str, Any], **kwargs: Any) -> VaultIdentityFabric:
    return VaultIdentityFabric(
        credentials=FakeTransport(paths),  # type: ignore[arg-type]
        known_tools=TOOLS,
        known_actions=ACTIONS,
        **kwargs,
    )


# ------------------------------------------------------------------ ceilings


def test_a_registered_definition_resolves_its_ceiling() -> None:
    """The positive control. Without it every refusal row could pass on a broken fabric."""
    fabric = _fabric(
        {
            "agent-registry/registration/display-name/planner": {"data": {"owner": "platform"}},
            "harness-authority/data/harness-ceilings/planner": _kv(
                tool_names=["echo", "plan"], product_actions=["product.workspace.read"]
            ),
        }
    )

    scope = fabric.resolve_ceiling("planner")

    assert scope.tool_names == frozenset({"echo", "plan"})
    assert scope.product_actions == frozenset({"product.workspace.read"})


def test_an_unregistered_definition_refuses() -> None:
    """Never a default ceiling, never an empty one that a later widening fills."""
    fabric = _fabric({})

    with pytest.raises(ResolutionRefused) as caught:
        fabric.resolve_ceiling("no-such-agent")

    assert caught.value.reason_code == "unknown_agent_definition"


def test_registered_without_a_ceiling_record_refuses() -> None:
    """The jurisdiction boundary, and the most dangerous shortcut in the module.

    The definition exists and has a credential-issuance policy. Reading that policy as a
    tool ceiling would turn a secrets grant into a tool grant, and it would look like
    resilience.
    """
    fabric = _fabric(
        {
            "agent-registry/registration/display-name/planner": {
                "data": {"ceiling_policies": ["agent-ceiling-planner", "default"]}
            }
        }
    )

    with pytest.raises(ResolutionRefused) as caught:
        fabric.resolve_ceiling("planner")

    assert caught.value.reason_code == "missing_ceiling_record"


def test_the_ceiling_is_never_inferred_from_ceiling_policies() -> None:
    """Stated as its own row because the previous one could pass by accident.

    A fabric that read `ceiling_policies` would still refuse when the record is missing
    *if it happened to find nothing useful there*. This asserts the policy content never
    reaches the resolved scope at all.
    """
    transport = FakeTransport(
        {
            "agent-registry/registration/display-name/planner": {
                "data": {"ceiling_policies": ["echo", "plan", "apply"]}
            }
        }
    )
    fabric = VaultIdentityFabric(
        credentials=transport,  # type: ignore[arg-type]
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )

    with pytest.raises(ResolutionRefused) as caught:
        fabric.resolve_ceiling("planner")

    assert caught.value.reason_code == "missing_ceiling_record", (
        "the policy's contents were readable as tool names and the fabric refused for the "
        "right reason anyway — but if this ever fails, a secrets grant has become a tool "
        "grant"
    )


# ------------------------------------------------------------------ user scope


def test_multiple_roles_union_rather_than_intersect() -> None:
    """Being granted a second role must never remove access.

    Intersection is the plausible alternative — it reads as the conservative choice — and
    it would make adding a role subtract permissions, which nobody would predict.
    """
    fabric = SubjectScopedVaultFabric(
        roles=["reader", "operator"],
        credentials=FakeTransport(
            {
                "harness-authority/data/role-bindings/reader": _kv(
                    tool_names=["echo"], product_actions=["product.workspace.read"]
                ),
                "harness-authority/data/role-bindings/operator": _kv(
                    tool_names=["plan", "apply"], product_actions=["product.workspace.write"]
                ),
            }
        ),
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )

    scope = fabric.resolve_user_scope("alice")

    assert scope.tool_names == frozenset({"echo", "plan", "apply"})
    assert scope.product_actions == {"product.workspace.read", "product.workspace.write"}


def test_the_three_no_scope_cases_are_distinguishable() -> None:
    """Nobody knows who you are / nobody said what your role means / your role means nothing.

    Only the third is a permissions answer. Collapsing them makes a platform failure look
    like a decision about a person, which is the wrong thing to tell an investigator.
    """
    # 1 — no claims at all: the base class has no roles to consult.
    with pytest.raises(ResolutionRefused) as unknown:
        _fabric({}).resolve_user_scope("alice")
    assert unknown.value.reason_code == "unknown_subject"

    # 2 — authenticated, but the claims mapped to nothing.
    no_role = SubjectScopedVaultFabric(
        roles=[],
        credentials=FakeTransport({}),
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )
    with pytest.raises(ResolutionRefused) as none_mapped:
        no_role.resolve_user_scope("alice")
    assert none_mapped.value.reason_code == "no_role_for_subject"

    # 3a — a role nobody has bound.
    unbound = SubjectScopedVaultFabric(
        roles=["ghost"],
        credentials=FakeTransport({}),
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )
    with pytest.raises(ResolutionRefused) as missing_binding:
        unbound.resolve_user_scope("alice")
    assert missing_binding.value.reason_code == "unbound_role"

    # 3b — a role bound to nothing. THIS one is a decision, and it must not raise.
    empty = SubjectScopedVaultFabric(
        roles=["intern"],
        credentials=FakeTransport(
            {"harness-authority/data/role-bindings/intern": _kv(tool_names=[], product_actions=[])}
        ),
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )
    scope = empty.resolve_user_scope("alice")
    assert scope.tool_names == frozenset()


# ------------------------------------------------------------------ failures


def test_unreachable_and_slow_are_different_reason_codes() -> None:
    """They get different responses from whoever investigates, so they get different codes."""
    unreachable = VaultIdentityFabric(
        credentials=FakeTransport({}, raises=VaultReadFailed("down")),  # type: ignore[arg-type]
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )
    with pytest.raises(ResolutionRefused) as down:
        unreachable.resolve_ceiling("planner")
    assert down.value.reason_code == "fabric_unreachable"

    slow = VaultIdentityFabric(
        credentials=FakeTransport(  # type: ignore[arg-type]
            {}, raises=VaultReadFailed("slow", timed_out=True)
        ),
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )
    with pytest.raises(ResolutionRefused) as timeout:
        slow.resolve_ceiling("planner")
    assert timeout.value.reason_code == "fabric_timeout"


def test_no_failure_path_returns_an_empty_scope() -> None:
    """The break fixture, as an assertion over every failure this component can produce.

    Returning ``AuthorityScope()`` from an exception handler is the shortest path in the
    module and reads as fail-closed. It would satisfy every "denied" row in this feature —
    denial is what an empty scope produces — and destroy the distinction between a person
    with no permissions and a platform that could not find out.
    """
    failures: list[Any] = [
        (_fabric({}), "resolve_ceiling", "no-such-agent"),
        (
            VaultIdentityFabric(
                credentials=FakeTransport({}, raises=VaultReadFailed("down")),  # type: ignore[arg-type]
                known_tools=TOOLS,
                known_actions=ACTIONS,
            ),
            "resolve_ceiling",
            "planner",
        ),
        (_fabric({}), "resolve_user_scope", "alice"),
    ]

    for fabric, method, argument in failures:
        with pytest.raises(ResolutionRefused):
            getattr(fabric, method)(argument)


def test_policy_absence_is_unrestricted_and_not_a_failure() -> None:
    """`None` means no policy record, which is a legitimate configuration.

    Distinct from a read that failed — which raises, and must, because "we could not check
    whether policy narrows this" is not "policy does not narrow this".
    """
    assert _fabric({}).resolve_policy("planner") is None

    failing = VaultIdentityFabric(
        credentials=FakeTransport({}, raises=VaultReadFailed("down")),  # type: ignore[arg-type]
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )
    with pytest.raises(ResolutionRefused):
        failing.resolve_policy("planner")


def test_policy_is_read_every_time_it_is_asked() -> None:
    """FR-008. A cache here would make a mid-run narrowing take an interval to bite."""
    transport = FakeTransport(
        {"harness-authority/data/policies/planner": _kv(tool_names=["echo"], product_actions=[])}
    )
    fabric = VaultIdentityFabric(
        credentials=transport,  # type: ignore[arg-type]
        known_tools=TOOLS,
        known_actions=ACTIONS,
    )

    fabric.resolve_policy("planner")
    fabric.resolve_policy("planner")
    fabric.resolve_policy("planner")

    reads = [p for p in transport.reads if "policies" in p]
    assert len(reads) == 3, f"policy was served from a cache: {len(reads)} reads for 3 calls"
