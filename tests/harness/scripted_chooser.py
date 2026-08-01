# SPDX-License-Identifier: Apache-2.0
"""The lane's model double — and the reason it is thin.

**The replay lives in `src/`, not here** (`core.choice.recorded.RecordedChooser`), because the
rows that matter drive a *dispatched* run inside an allocation and an allocation cannot be
handed a Python object. It resolves its chooser the way production does: from the model
identifier the definition's binding map names. A double reachable only from a test process
would have left every enclave row either calling a vendor or not consulting a model at all.

So this module is the **authoring** surface — build a recording, and get the in-process
chooser for the hermetic rows that never dispatch. The thing under test is the same class
either way.

Injected **at the binding, never at the loop** (research F5): `build_chooser` dispatches on
the provider segment of ``provider/model@version``, so every line between "the run needs a
choice" and "a choice came back" is production code in both lanes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from core.authority.bindings import DefinitionBindings
from core.choice.chooser import CHOICE_ROLE
from core.choice.recorded import NOTHING, RecordedChooser

#: A model identifier the matrix can qualify and a definition can bind, whose provider
#: resolves to a recording. It is a real `provider/model@version` — `MODEL_IDENTIFIER` refuses
#: anything else, and a double exempt from the identifier rules would be a double exempt from
#: the resolution it exists to exercise.
FIXTURE_MODEL = "fixture/scripted@1"


def recording(*answers: str) -> str:
    """The wire form of a scripted sequence, as a run receives it.

    ``recording("plan", "apply")`` → ``"plan,apply"``. Use `NOTHING` for "the model names
    nothing here", which ends the run terminally.
    """
    return ",".join(answers)


def scripted_chooser(answers: Sequence[str]) -> RecordedChooser:
    """The in-process double, for rows that construct a run rather than dispatching one."""
    return RecordedChooser(answers)


@dataclass
class BindingFabric:
    """An identity fabric that also answers the two questions a model binding needs.

    `FakeIdentityFabric` answers about users, ceilings, and policy — everything authority
    manufacture needs — and nothing about models, because until 020 nothing on a run path
    asked. Wrapping rather than extending, on the shape `tests/component/test_matrix_refusals`
    already uses: the delegate stays the thing under test everywhere else, and a row that
    wants an unbound or unqualified definition changes only the two fields here.
    """

    inner: Any
    #: role → cell reference. Empty means the definition binds no model, which must refuse.
    binding_map: dict[str, str] = field(default_factory=dict)
    #: Raw matrix cells, as the control plane would hold them.
    cells: list[dict[str, Any]] = field(default_factory=list)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def resolve_definition_bindings(self, agent_definition_id: str) -> DefinitionBindings:
        return DefinitionBindings(
            agent_definition_id=agent_definition_id,
            packs=frozenset(),
            binding_map=dict(self.binding_map),
            tier=1,
        )

    def read_matrix(self) -> dict[str, Any]:
        return {"schema_version": 1, "cells": list(self.cells)}


def fixture_cell(
    *, pack: str = "vault", model: str = FIXTURE_MODEL, role: str = CHOICE_ROLE
) -> dict[str, Any]:
    """One qualified cell naming the recording provider.

    ``qualified_by="fixture"`` is the matrix's own word for a cell qualified against a
    recording — the vocabulary already existed, which is what makes the double reachable
    through the real resolution rather than around it.
    """
    return {
        "pack": pack,
        "model": model,
        "role": role,
        "qualified_by": "fixture",
        "judge": "seed",
    }


def cell_reference(
    *, pack: str = "vault", model: str = FIXTURE_MODEL, role: str = CHOICE_ROLE
) -> str:
    return f"{pack}:{model}:{role}"


def binding_fabric(
    inner: Any,
    *,
    model: str = FIXTURE_MODEL,
    bind: bool = True,
    qualify: bool = True,
    withdrawn: bool = False,
) -> BindingFabric:
    """A fabric bound to ``model``, or deliberately missing one of the two records.

    ``bind=False`` is "no binding for the role" (FR-006, must refuse rather than default) and
    ``qualify=False`` is "bound to a cell the matrix does not qualify" (FR-006, must refuse
    before any provider call). They are separate switches because they are separate failures
    with separate fixes, and a fabric that could only produce one of them would leave the
    other assertion untestable.
    """
    cell = fixture_cell(model=model)
    if withdrawn:
        cell = {**cell, "withdrawn": True}
    return BindingFabric(
        inner=inner,
        binding_map={CHOICE_ROLE: cell_reference(model=model)} if bind else {},
        cells=[cell] if qualify else [],
    )


__all__ = [
    "FIXTURE_MODEL",
    "NOTHING",
    "BindingFabric",
    "RecordedChooser",
    "binding_fabric",
    "cell_reference",
    "fixture_cell",
    "recording",
    "scripted_chooser",
]
