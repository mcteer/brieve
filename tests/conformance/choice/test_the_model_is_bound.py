# SPDX-License-Identifier: Apache-2.0
"""CONFORMANCE — the model is the one the matrix bound (020, US2, FR-005/FR-006).

An ungoverned model choice is the same defect as an ungoverned tool choice, one level up.
ADR-0022 and ADR-0039 decided this and — until this feature — had never been load-bearing:
the matrix reader, the binding map, and the run-start validation all existed, and every
definition bound nothing, so `_resolve_binding_map` returned before touching the matrix on
every run in the estate.

**Two shapes of row here, and the split is deliberate.** The first drives dispatched runs,
because SC-004's claim is about what a *run* used. The refusal rows resolve through the same
production function in-process, because their claim is that nothing is reached — and a
dispatched row can only ever observe that a run failed, which is consistent with a dozen
causes. The distinction each refusal row makes is the reason code, and that is legible where
the resolution happens.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.authority.errors import ResolutionRefused
from core.choice import resolve_bound_model
from tests.conformance.choice import harness as c
from tests.conformance.durability import dispatch_harness as h
from tests.harness.fake_identity_fabric import fake_identity_fabric
from tests.harness.scripted_chooser import FIXTURE_MODEL, binding_fabric

#: What `applier-agent` binds. The second cell exists so SC-004 can compare two runs.
OTHER_MODEL = "fixture/scripted@2"

#: SC-001's declaration, and this file is the sanctioned case rather than an exception to it.
#:
#: The refusal rows below exist **specifically to inject a resolution failure**: a definition
#: that binds no model, one bound to a cell the matrix does not qualify, one bound to a cell
#: since withdrawn, and a fabric that answers about models not at all. Those are four states
#: the dev enclave's control plane cannot be in at once, and arranging any of them in Vault
#: would mean breaking the estate every other dispatched row runs against.
#:
#: The row above this line — the one asserting what a run actually *used* — takes the
#: production fabric and dispatches, because that claim is about a run rather than about a
#: resolution refusing.
FAKE_FABRIC_IS_FAULT_INJECTION = (
    "these rows inject binding-map and matrix resolution failures: no binding for the role, "
    "an unqualified cell, a withdrawn cell, and a fabric with no matrix at all"
)


@pytest.fixture
def conn() -> Any:
    connection = h.connection()
    yield connection
    connection.close()


@pytest.mark.enclave
@pytest.mark.host_enclave
def test_the_bound_model_is_the_one_used(conn: Any) -> None:
    """FR-005, SC-004 — two definitions bound to different models, evidenced from the trail.

    **One definition cannot show this.** With a single cell in the estate, a run recording
    "the model was X" would pass against an implementation that hard-coded X and never read a
    binding map — which is the state the platform was in before this feature. So the row
    dispatches two definitions bound to different cells and requires the recorded models to
    differ, and to be the ones the control plane says.
    """
    planner_run = h.unique("choice-model-planner")
    c.run_to_completion(planner_run, answers=["plan"], definition=c.PLANNER)

    applier_run = h.unique("choice-model-applier")
    c.run_to_completion(applier_run, answers=["plan"], definition=c.APPLIER)

    planner_models = {str(e.get("model") or "") for e in c.choices(conn, planner_run)}
    applier_models = {str(e.get("model") or "") for e in c.choices(conn, applier_run)}

    assert planner_models == {FIXTURE_MODEL}, (
        f"{c.PLANNER} did not use the model its binding map names: {planner_models}"
    )
    assert applier_models == {OTHER_MODEL}, (
        f"{c.APPLIER} did not use the model its binding map names: {applier_models}"
    )
    assert planner_models != applier_models, (
        "two definitions bound to different cells produced runs recording the same model; "
        "the binding map is not being read"
    )


def test_an_unqualified_model_refuses_before_any_call() -> None:
    """FR-006 — a model the matrix does not qualify must not be REACHED.

    Not merely "not used". The ordering is the requirement: validation happens before
    anything constructs a client, so an unqualified cell cannot produce a provider call that
    is then discarded. The row asserts the refusal's reason code, because "the run failed" is
    consistent with a dozen causes and only `unqualified_cell` says this one.
    """
    fabric = binding_fabric(fake_identity_fabric(), qualify=False)
    with pytest.raises(ResolutionRefused) as excinfo:
        resolve_bound_model(fabric, agent_definition_id="planner-agent")
    assert excinfo.value.reason_code == "unqualified_cell", (
        f"an unqualified cell refused for the wrong reason: {excinfo.value.reason_code!r} — "
        "the reason is what sends someone to the matrix rather than to the definition"
    )


def test_a_withdrawn_cell_refuses() -> None:
    """FR-006 — a cell qualified once and since pulled stops being usable.

    **The case run-start validation exists for**, and the one a registration-time-only check
    would miss: the definition pinning the cell sits unchanged in the registry, so nothing
    about it changed and nothing would re-ask. `core.authority.matrix`'s own docstring makes
    this argument; this is the row behind it, now that something reads a binding map.
    """
    fabric = binding_fabric(fake_identity_fabric(), withdrawn=True)
    with pytest.raises(ResolutionRefused) as excinfo:
        resolve_bound_model(fabric, agent_definition_id="planner-agent")
    assert excinfo.value.reason_code == "cell_withdrawn"


def test_no_binding_refuses_rather_than_defaults() -> None:
    """FR-006 — never default.

    A default model is an ungoverned model choice, which is the same defect as an ungoverned
    tool choice one level up. The tempting implementation — fall back to the platform's
    usual model when a definition names none — is the one this forbids, and it would be
    invisible: every run would work.
    """
    fabric = binding_fabric(fake_identity_fabric(), bind=False)
    with pytest.raises(ResolutionRefused) as excinfo:
        resolve_bound_model(fabric, agent_definition_id="planner-agent")
    assert excinfo.value.reason_code == "no_binding_for_role"


def test_a_fabric_with_no_matrix_refuses_rather_than_going_inert() -> None:
    """FR-006 — and deliberately UNLIKE `manufacture._resolve_binding_map`.

    That function goes inert when the fabric supplies no matrix, which is correct where it
    lives: it keeps every pre-013 run working, and "a fabric with no matrix" is not "a fabric
    whose cells are all unqualified". Here the opposite is correct, because reaching this
    function means a run is about to consult a model — and consulting a model no record
    qualified is precisely what FR-006 forbids.

    Asserted because the two postures look contradictory in review, and the wrong resolution
    is to make this one inert too. That would be fail-open on the only path where a model is
    actually chosen.
    """
    with pytest.raises(ResolutionRefused) as excinfo:
        resolve_bound_model(fake_identity_fabric(), agent_definition_id="planner-agent")
    assert excinfo.value.reason_code == "no_binding_for_role"
