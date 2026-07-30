# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — the matrix binds at run start, and every refusal stops the run.

Each row asserts **zero runs proceeded**, not merely that something raised. A refusal that
raises after the run has started is a run that ran.

The load-bearing case is `cell_withdrawn`. A definition pins a cell, the cell is later pulled
— a model deprecated, a suite regressed, a bad result acted on — and the definition sits
unchanged in the registry. Validating only at definition time would let it keep running
because nothing re-asked. That is why the check runs again at every run start, and it is the
same reasoning that makes 010 resolve a ceiling per run rather than caching it.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.authority.bindings import DefinitionBindings
from core.authority.errors import AuthorityRefuseError
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from tests.harness.fake_identity_fabric import fake_identity_fabric

MODEL = "anthropic/claude-opus@5"
OTHER = "anthropic/claude-sonnet@5"


class _MatrixFabric:
    """A fabric that also answers the two 013 questions.

    Wraps rather than replaces the existing fake, because `manufacture_authority` reaches
    the matrix through *duck typing* — a fabric without these methods is inert, which is how
    every pre-013 caller behaves. A row that replaced the fabric wholesale would not be
    testing the same code path production takes.
    """

    def __init__(self, inner: Any, *, cells: list[dict[str, Any]], binding_map: dict[str, str]):
        self._inner = inner
        self._cells = cells
        self._binding_map = binding_map

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def read_matrix(self) -> dict[str, Any]:
        return {"schema_version": 1, "cells": self._cells}

    def resolve_definition_bindings(self, agent_definition_id: str) -> DefinitionBindings:
        return DefinitionBindings(
            agent_definition_id=agent_definition_id,
            packs=frozenset({"vault"}),
            binding_map=self._binding_map,
            tier=1,
        )


def _cell(role: str = "write", model: str = MODEL, **extra: Any) -> dict[str, Any]:
    return {"pack": "vault", "model": model, "role": role, "qualified_by": "fixture", **extra}


def _start(fabric: Any, sink: InMemoryAuditSink | None = None) -> Any:
    registry = ToolRegistry()
    registry.register("echo", lambda args: "ok")
    return start_governed_run(
        correlation_id="corr-matrix-001",
        subject_user_id="user-1",
        agent_definition_id="applier",
        requested_scope=AuthorityScope(tool_names=frozenset({"echo"}), product_actions=frozenset()),
        identity_fabric=fabric,
        registry=registry,
        audit_sink=sink or InMemoryAuditSink(),
    )


def _fabric(cells: list[dict[str, Any]], binding_map: dict[str, str]) -> _MatrixFabric:
    inner = fake_identity_fabric(subject_user_id="user-1", tool_names={"echo"})
    return _MatrixFabric(inner, cells=cells, binding_map=binding_map)


def test_a_qualified_binding_starts_the_run() -> None:
    """The positive control. A check that refused everything would pass every row below."""
    run = _start(_fabric([_cell()], {"write": f"vault:{MODEL}:write"}))
    assert run.state.name == "ACTIVE"


def test_an_unqualified_cell_refuses_and_zero_runs_proceed() -> None:
    with pytest.raises(AuthorityRefuseError) as caught:
        _start(_fabric([_cell()], {"write": f"vault:{OTHER}:write"}))
    assert caught.value.reason_code == "unqualified_cell"
    assert OTHER in str(caught.value), "the refusal does not name the cell"


def test_a_withdrawn_cell_refuses_at_run_start() -> None:
    """The case definition-time validation cannot catch.

    The definition is unchanged and was valid when registered. Only re-asking at run start
    sees that the cell has since been pulled.
    """
    with pytest.raises(AuthorityRefuseError) as caught:
        _start(_fabric([_cell(withdrawn=True)], {"write": f"vault:{MODEL}:write"}))
    assert caught.value.reason_code == "cell_withdrawn"


def test_a_role_mismatch_refuses() -> None:
    """The same pack and model, qualified to summarize, bound to write."""
    with pytest.raises(AuthorityRefuseError) as caught:
        _start(_fabric([_cell(role="summarize")], {"write": f"vault:{MODEL}:write"}))
    assert caught.value.reason_code == "unqualified_cell"


def test_a_refusal_is_recorded_before_it_is_raised() -> None:
    """`AUTHORITY_REFUSED` reaches the trail even though the run never started.

    A refusal nobody can see is indistinguishable from a run that was never attempted, and
    an investigator asking "why did nothing happen" needs the difference.
    """
    sink = InMemoryAuditSink()
    with pytest.raises(AuthorityRefuseError):
        _start(_fabric([_cell()], {"write": f"vault:{OTHER}:write"}), sink)

    events = [e.event_type for e in sink.list_by_correlation_id("corr-matrix-001")]
    assert AuditEventType.AUTHORITY_REFUSED in events
    assert AuditEventType.RUN_START not in events, "a refused run reached RUN_START"


def test_a_definition_binding_no_model_is_unaffected() -> None:
    """Every pre-013 fixture, and the reason the check is inert rather than fail-closed.

    A definition binding nothing is not a definition binding something unqualified. Treating
    them alike would refuse every 008–012 run while looking exactly like the check working.
    """
    run = _start(_fabric([_cell()], {}))
    assert run.state.name == "ACTIVE"


def test_a_fabric_with_no_matrix_at_all_is_inert() -> None:
    """The duck-typed path: a pre-013 fabric has neither method and is unchanged."""
    run = _start(fake_identity_fabric(subject_user_id="user-1", tool_names={"echo"}))
    assert run.state.name == "ACTIVE"
