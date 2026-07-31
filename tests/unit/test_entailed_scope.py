# SPDX-License-Identifier: Apache-2.0
"""Deriving a task's scope from the tools it asked for (016 T012).

The property being bought is *relative*: a run requesting fewer tools reaches fewer paths.
These rows assert that, and assert the two ways the derivation is allowed to refuse — an
undeclared secret-touching tool, and a scope that exceeds the ceiling.

What they deliberately do not assert is that the narrowing is *tight*. It is exactly as tight
as the tools' declarations, which the spec records as an accepted limit rather than a defect.
"""

from __future__ import annotations

from core.authority.scope import EntailedScope, ScopeUndetermined, entailed_scope
from core.packs.manifest import ToolDeclaration, ToolPathGrant


def _tool(
    name: str, *, paths: tuple[ToolPathGrant, ...] = (), risk: str = "read"
) -> ToolDeclaration:
    return ToolDeclaration(
        name=name,
        risk_class=risk,  # type: ignore[arg-type]
        transport="native",
        handler=name,
        paths=paths,
    )


READ_AGENT = (ToolPathGrant(path="{agent_space}", capabilities=("read",)),)
WRITE_AGENT = (ToolPathGrant(path="{agent_space}", capabilities=("create", "update")),)
OTHER = (ToolPathGrant(path="secret/data/elsewhere/*", capabilities=("read",)),)

REGISTRY = {
    "vault_read": _tool("vault_read", paths=READ_AGENT, risk="secret_touching"),
    "vault_write": _tool("vault_write", paths=WRITE_AGENT, risk="secret_touching"),
    "reach_elsewhere": _tool("reach_elsewhere", paths=OTHER, risk="secret_touching"),
    "echo": _tool("echo"),
    "undeclared": _tool("undeclared", risk="secret_touching"),
}


PLANNER_SPACE = frozenset({"secret/data/planner/*"})


def _scope(*names: str, space: frozenset[str] = PLANNER_SPACE) -> EntailedScope:
    return entailed_scope(requested_tools=frozenset(names), tools=REGISTRY, agent_space=space)


def test_fewer_tools_reach_fewer_paths() -> None:
    """The whole point, stated as a subset relation rather than an absolute one."""
    both = _scope("vault_read", "reach_elsewhere")
    one = _scope("vault_read")

    assert set(one.paths) < set(both.paths), "requesting fewer tools did not narrow the scope"
    assert set(one.paths) == {"secret/data/planner/*"}


def test_the_space_comes_from_the_ceiling_not_from_the_agents_name() -> None:
    """The bug this row exists for shipped in the first draft and was caught live.

    Templating on the definition id produced `secret/data/planner-agent/*` where the ceiling
    grants `secret/data/planner/*` — and `vault-agent`, whose space is
    `secret/data/conformance/*`, could never have matched anything name-derived. A convention
    that must agree with a record is a second source of truth.
    """
    assert set(_scope("vault_read").paths) == {"secret/data/planner/*"}
    conformance = frozenset({"secret/data/conformance/*"})
    assert set(_scope("vault_read", space=conformance).paths) == {"secret/data/conformance/*"}
    assert "{agent_space}" not in "".join(_scope("vault_read").paths)


def test_a_ceiling_granting_several_spaces_expands_to_all_of_them() -> None:
    """A definition may reach more than one place; the template is not singular."""
    two = frozenset({"secret/data/planner/*", "secret/data/shared/*"})

    assert set(_scope("vault_read", space=two).paths) == two


def test_capabilities_union_across_tools_sharing_a_path() -> None:
    """The narrowing that actually bites today: read-only versus read-and-write.

    Every tool in the shipped packs reaches the same agent space, so the path set does not
    vary with the request. The capability set does, and a run that asked only to read must
    never receive create or update.
    """
    scope = _scope("vault_read", "vault_write")

    assert scope.paths == {"secret/data/planner/*": frozenset({"read", "create", "update"})}


def test_a_tool_reaching_nothing_contributes_nothing_and_is_not_an_error() -> None:
    """`echo` touches no secret. Saying so is different from failing to say anything."""
    scope = _scope("echo")

    assert scope.paths == {}
    assert scope.undetermined == frozenset()
    scope.require_determined()  # must not raise


def test_an_undeclared_secret_touching_tool_refuses_the_launch() -> None:
    """FR-004 — the alternative is granting the ceiling to be safe, which is the failure."""
    scope = _scope("undeclared")

    assert scope.undetermined == frozenset({"undeclared"})
    try:
        scope.require_determined()
    except ScopeUndetermined as exc:
        assert "undeclared" in str(exc)
        assert "decorative" in str(exc), "the refusal does not say why granting broadly is wrong"
    else:  # pragma: no cover - the assertion above is the point
        raise AssertionError("an undeclared tool did not refuse")


def test_a_requested_tool_outside_the_registry_is_not_a_scope_problem() -> None:
    """It is an authorization problem, and reporting it here would misdirect the reader.

    A tool the run may not use at all is refused by the ceiling check in its own vocabulary.
    Calling it "undetermined scope" would send whoever reads the failure to the pack
    manifests when the answer is in the ceiling record.
    """
    scope = _scope("vault_read", "not_in_this_registry")

    assert scope.undetermined == frozenset()
    assert set(scope.paths) == {"secret/data/planner/*"}


def test_the_authorization_details_are_vaults_shape() -> None:
    """Not ours. A translation layer here is where the two representations would drift."""
    details = _scope("vault_read", "vault_write").as_authorization_details()

    assert details == [
        {
            "type": "vault:path_access",
            "path": "secret/data/planner/*",
            "capabilities": ["create", "read", "update"],
        }
    ]


def test_the_ceiling_comparison_understands_policy_globs() -> None:
    """The ceiling speaks Vault policy (`prefix/*`); a grant names exact paths.

    Compared as strings they never match, and every legitimate grant would be refused —
    which fails closed, and would look exactly like the feature not working.
    """
    ceiling = {"secret/data/planner/*": frozenset({"read"})}
    inside = EntailedScope(paths={"secret/data/planner/greeting": frozenset({"read"})})

    assert inside.issubset_of(ceiling)


def test_a_capability_the_ceiling_withholds_is_outside_it() -> None:
    """Capability-aware, because a path-only check would call `update` on a read-only path fine."""
    ceiling = {"secret/data/planner/*": frozenset({"read"})}
    writing = EntailedScope(paths={"secret/data/planner/greeting": frozenset({"update"})})

    assert not writing.issubset_of(ceiling)


def test_a_path_the_ceiling_never_names_is_outside_it() -> None:
    ceiling = {"secret/data/planner/*": frozenset({"read"})}
    elsewhere = EntailedScope(paths={"secret/data/applier/deploy": frozenset({"read"})})

    assert not elsewhere.issubset_of(ceiling)
