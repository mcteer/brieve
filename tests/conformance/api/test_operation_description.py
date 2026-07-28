# SPDX-License-Identifier: Apache-2.0
"""Row: every operation is described, and an undescribed one is detected (FR-012, SC-010).

Two halves, and the second is the one that does the work. Generation is automatic, so
"every operation appears in the description" is nearly tautological. What SC-010 actually
requires is that adding an operation **without recording it** is *detected* — which needs a
committed baseline to diff against.
"""

from __future__ import annotations

import json
import pathlib

from fastapi import APIRouter

from surfaces.api.description import operation_snapshot, operation_summary
from tests.harness.api_fixtures import surface_under_test

SNAPSHOT = (
    pathlib.Path(__file__).resolve().parents[3]
    / "specs"
    / "008-northbound-api"
    / "contracts"
    / "operations.snapshot.json"
)


def test_the_snapshot_matches_the_implementation() -> None:
    app = surface_under_test().app
    assert operation_snapshot(app) == SNAPSHOT.read_text(), (
        "the operation set changed without updating "
        f"{SNAPSHOT.name} — update it deliberately, in the same change"
    )


def test_every_operation_is_described() -> None:
    app = surface_under_test().app
    described = {(o["method"], o["path"]) for o in operation_summary(app)}
    assert ("POST", "/runs") in described
    assert ("GET", "/evidence") in described


def test_the_openapi_document_is_generated_from_the_implementation() -> None:
    """Not maintained beside it: the same models that validate requests produce it."""
    schema = surface_under_test().app.openapi()
    assert "/runs" in schema["paths"]
    assert "StartRunRequest" in json.dumps(schema)


def test_an_operation_added_without_recording_it_is_detected() -> None:
    """The half SC-010 is actually about.

    Without the snapshot diff, a new route would appear in the generated document
    automatically and silently — described, but unrecorded, and therefore invisible to
    whoever builds the second transport and compares against it.
    """
    surface = surface_under_test()
    extra = APIRouter()

    @extra.get("/quietly-added")
    def quietly_added() -> dict[str, str]:
        return {}

    surface.app.include_router(extra)

    assert operation_snapshot(surface.app) != SNAPSHOT.read_text()
    assert ("GET", "/quietly-added") in {
        (o["method"], o["path"]) for o in operation_summary(surface.app)
    }


def test_the_snapshot_is_not_empty() -> None:
    """Guard: an empty snapshot would make the diff assertion pass against anything."""
    assert len(json.loads(SNAPSHOT.read_text())) >= 3
