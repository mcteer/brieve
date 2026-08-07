# SPDX-License-Identifier: Apache-2.0
"""US5 — two writers, zero silent disagreements (044, FR-019/020, SC-012).

**The failure this guards is not a conflict — it is a *silent* conflict.** Terraform still
writes every record it wrote before; the console now writes three of them. An administrator's
change reverted by the next estate apply, with nothing to show it happened, is discovered when
behaviour changes and not before.

**Provenance is read from the record itself.** The console stamps `set_by` on every change; a
record written by an apply carries none. So "last set by" needs no second store — and no second
store means no two answers that disagree exactly when somebody needs to know which writer won.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from surfaces.api.authority_submit import ChangeOutcome
from surfaces.api.console import ASK_BINDING_PATH, ConsoleConfig
from tests.harness.api_fixtures import surface_under_test

MODEL = "anthropic/claude-sonnet@5"


class _Submitter:
    def __init__(self) -> None:
        self.submitted: list[Any] = []

    def submit_change(self, change: Any) -> Any:
        self.submitted.append(change)
        return ChangeOutcome(state="applied")


def _binding(set_by: str | None, version: int = 1) -> dict[str, Any]:
    body: dict[str, Any] = {"schema_version": 1, "guidance_cell": f"vault:{MODEL}:ask"}
    if set_by is not None:
        body["set_by"] = set_by
    return {"data": {"data": body, "metadata": {"version": version}}}


def _surface(binding_record: dict[str, Any], submitter: Any = None) -> Any:
    config = ConsoleConfig(
        read_matrix=lambda: {"schema_version": 1, "cells": []},
        # ONE reader for every record, keyed by path — the shape the console now takes, so a
        # row cannot accidentally supply a binding through a path production does not use.
        read_versioned=lambda path: binding_record if path == ASK_BINDING_PATH else None,
        quorum_configured=False,
    )
    return surface_under_test(console_config=config, authority_submitter=submitter)


def _admin(surface: Any) -> dict[str, str]:
    headers: dict[str, str] = surface.bearer(claims={"groups": ["platform-admin"]})
    return headers


def _posture(surface: Any) -> dict[str, Any]:
    body: dict[str, Any] = (
        TestClient(surface.app).get("/console/configuration", headers=_admin(surface)).json()
    )
    return body


def test_a_record_written_by_terraform_says_so() -> None:
    """A record with no `set_by` was written by an apply, and the console names it.

    Rendering an empty string would leave a reader to infer, and the inference most people
    make is "nobody" rather than "the estate".
    """
    posture = _posture(_surface(_binding(set_by=None)))

    assert posture["bindings"]["set_by"] == "an estate apply"


def test_a_record_written_by_the_console_names_its_administrator() -> None:
    """The other half: a console write is attributable to a person, not to a surface."""
    posture = _posture(_surface(_binding(set_by="console/alice")))

    assert posture["bindings"]["set_by"] == "console/alice"


def test_an_estate_apply_over_a_console_change_is_visible() -> None:
    """SC-012 — the disagreement surfaces rather than being discovered through behaviour.

    Simulated as the fabric would present it: the record's version moves and the `set_by`
    stamp is gone, because an apply writes the module's own body. Both facts are in the
    console's read, so an administrator sees their change was replaced rather than wondering
    why the estate stopped doing what they set.
    """
    before = _posture(_surface(_binding(set_by="console/alice", version=4)))
    after = _posture(_surface(_binding(set_by=None, version=5)))

    assert before["bindings"]["set_by"] == "console/alice"
    assert after["bindings"]["set_by"] == "an estate apply"
    assert after["bindings"]["version"] > before["bindings"]["version"], (
        "the version is what makes 'replaced' distinguishable from 'never set'"
    )


def test_the_version_the_administrator_read_is_the_one_a_change_guards_on() -> None:
    """The CAS story from the read end (C7's other half).

    The console shows the version it read, so a change submitted from that page guards
    against *what was seen*. Re-reading at submit would guard against nothing — it would
    fetch whatever is current and agree with it.
    """
    posture = _posture(_surface(_binding(set_by="console/alice", version=9)))

    assert posture["bindings"]["version"] == 9


def test_the_console_stamps_provenance_on_every_change_it_submits() -> None:
    """FR-019's write half — asserted on the `ConfigChange` the route built.

    `authority_submit`'s own rows assert the stamp reaches the payload; this asserts the
    console supplies the requester that makes it meaningful.
    """
    submitter = _Submitter()
    surface = _surface(_binding(set_by=None), submitter)

    TestClient(surface.app).post(
        "/console/changes",
        json={"record": "ask-bindings", "payload": {"schema_version": 1}},
        headers=_admin(surface),
    )

    assert submitter.submitted[0].requester == surface.subject_name
