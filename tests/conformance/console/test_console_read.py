# SPDX-License-Identifier: Apache-2.0
"""C9–C14, C26 — reading the posture, and who may (044, US1).

**C10 is the row that decides what an outage means.** An unreadable record and a permissive
configuration arrive identically — as no data — and an administrator shown an empty binding
where the truth is "nobody could look" may reasonably conclude nothing is configured and set
about configuring it. `MatrixSource` and 042's `ProtectedSet` both draw this line; this is the
same one at the display layer, where the consequence is a person acting on a false picture.

**C13 and C14 are the two directions of FR-016a**, and they fail differently. C13 is a
non-admin reaching configuration; C14 is an admin reaching the trail. Neither is implied by
the other, and the visibility map would still parse if either widened.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from surfaces.api.console import CONNECTIONS_PATH, ConsoleConfig
from tests.harness.api_fixtures import surface_under_test

MODEL = "anthropic/claude-sonnet@5"
JUDGE = "anthropic/claude-opus@5"


def _binding(**over: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "guidance_cell": f"vault:{MODEL}:ask",
        "estate_cell": f"vault:{MODEL}:ask",
        "relevance_cell": f"vault:{JUDGE}:judge",
        **over,
    }


def _matrix() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "cells": [
            {
                "pack": "vault",
                "model": MODEL,
                "role": "ask",
                "qualified_by": "live",
                "judge": JUDGE,
            },
            {
                "pack": "vault",
                "model": JUDGE,
                "role": "judge",
                "qualified_by": "live",
                "judge": "seed",
            },
        ],
    }


def _connections() -> dict[str, Any]:
    return {
        "data": {
            "data": {
                "tfe": {"address": "https://app.terraform.io", "organization": "acme"},
                "set_by": "console/alice",
            },
            "metadata": {"version": 4},
        }
    }


def _config(**over: Any) -> ConsoleConfig:
    defaults: dict[str, Any] = {
        "read_binding": lambda: _binding(),
        "read_matrix": _matrix,
        "read_versioned": lambda path: _connections() if path == CONNECTIONS_PATH else None,
        "quorum_configured": False,
    }
    return ConsoleConfig(**{**defaults, "quorum_configured": False, **over})


def _surface(**over: Any) -> Any:
    return surface_under_test(console_config=_config(**over))


def _admin_headers(surface: Any) -> dict[str, str]:
    """A subject whose claim maps to `admin` — a different claim value from the default."""
    headers: dict[str, str] = surface.bearer(claims={"groups": ["platform-admin"]})
    return headers


def test_row_c9_the_console_shows_what_the_fabric_holds() -> None:
    """C9 — field-for-field, against the records the row supplied."""
    surface = _surface()

    response = TestClient(surface.app).get(
        "/console/configuration", headers=_admin_headers(surface)
    )

    assert response.status_code == 200
    posture = response.json()
    assert posture["bindings"]["guidance_cell"] == f"vault:{MODEL}:ask"
    assert posture["bindings"]["relevance_cell"] == f"vault:{JUDGE}:judge"
    assert posture["bindings"]["relevance_enabled"] is True


def test_row_c9_qualified_cells_come_from_the_matrix_and_nothing_else() -> None:
    """FR-009's OFFER side (analyze C3).

    C1 refuses an unqualified cell at submit. This is the other half: the console must not
    present one either, or an administrator is invited to choose something that will be
    refused — which reads as the platform being broken rather than as governance working.
    """
    # ONE surface. Two `_surface()` calls build two fake identity providers, so a token from
    # the second is not valid for the first — the row then reads a 403 body and fails on a
    # missing key rather than on what it is about.
    surface = _surface()
    posture = (
        TestClient(surface.app)
        .get("/console/configuration", headers=_admin_headers(surface))
        .json()
    )

    assert sorted(posture["qualified_cells"]) == [
        f"vault:{JUDGE}:judge",
        f"vault:{MODEL}:ask",
    ]


def test_row_c10_an_unreadable_record_is_unavailable_not_empty() -> None:
    """C10 — the row this file exists for.

    Rendered per record rather than failing the page: an administrator whose connections
    record is missing still needs to see which model answers, and one unreadable record
    taking the console down would make a small gap look like an outage.
    """

    def _down() -> dict[str, Any]:
        raise ConnectionError("vault unreachable")

    surface = _surface(read_binding=_down)

    posture = (
        TestClient(surface.app)
        .get("/console/configuration", headers=_admin_headers(surface))
        .json()
    )

    assert posture["bindings"] == {"unavailable": True}, (
        "an unreadable binding must not render as an unbound one; a person told nothing is "
        "configured may set about configuring it"
    )
    # The rest of the page still answers.
    assert posture["qualified_cells"]


def test_row_c11_no_credential_appears_in_any_console_response() -> None:
    """[GATE:no-secret-leak] C11 — asserted over the rendered payload, not claimed.

    The structural guarantee is upstream: the connection vocabulary has no credential field
    and the console reads no credential path. This is where the two meet the artefact a
    person receives.
    """
    surface = _surface()

    body = (
        TestClient(surface.app).get("/console/configuration", headers=_admin_headers(surface)).text
    )

    for token in ("hvs.", "s.", "-----BEGIN", "api_key", "password", "secret/"):
        assert token not in body, f"{token!r} reached the console's response"


def test_row_c12_every_read_is_recorded_against_the_administrator() -> None:
    """C12 — evidence access is itself audited, and configuration is evidence of posture."""
    surface = _surface()

    TestClient(surface.app).get("/console/configuration", headers=_admin_headers(surface))

    reads = [
        entry for entry in surface.audit.all_entries() if entry.payload.get("surface") == "console"
    ]
    assert reads, "a surface a caller can read without trace is not a governed one"
    assert reads[-1].payload["actor"] == surface.subject_name


def test_row_c13_a_non_admin_is_refused_and_the_refusal_is_recorded() -> None:
    """C13 — FR-016a's first direction. The default subject is an `operator`, and stays one."""
    surface = _surface()

    response = TestClient(surface.app).get("/console/configuration", headers=surface.bearer())

    assert response.status_code == 403
    assert "administrative" in response.text
    # 022's rule: a refusal records. A boundary a caller can probe without trace is not one,
    # and repeated attempts against an administrative surface are what a trail should show.
    refusals = [
        entry
        for entry in surface.audit.all_entries()
        if entry.payload.get("reason_code") == "not_an_admin"
    ]
    assert refusals, "the console refused and said nothing about it"
    assert refusals[-1].payload["actor"] == surface.subject_name


def test_row_c14_an_admin_gets_no_audit_visibility_from_the_role() -> None:
    """C14 — FR-016a's other direction, and it is not about the console at all.

    An administrator reaching the evidence read must be refused exactly as a stranger is.
    If `admin` ever gains the analyst's set, this fails while every console row stays green.
    """
    surface = _surface()

    response = TestClient(surface.app).get("/evidence", headers=_admin_headers(surface))

    # 200 with nothing in it, not 403: the evidence read deliberately returns zero rows
    # either way, because telling a caller *which* would leak the existence of what they may
    # not see. Asserted unconditionally rather than behind an `if` — a conditional assertion
    # is one that stops biting the moment the status changes.
    assert response.status_code == 200
    assert response.json()["entries"] == [], (
        "an administrator sees zero events by virtue of the role; anything here is the "
        "widening FR-016a forbids, arriving through the visibility map"
    )


def test_row_c26_the_presented_role_vocabulary_is_adr_0039s() -> None:
    """C26 — FR-018/SC-010 (analyze C1).

    R7 decided the console presents ADR-0039's real names and drops `research`/`validate`
    rather than aliasing them: a display alias invites a reader to believe a capability
    exists that does not. Nothing in the code resists that drift, so a row does.
    """
    from core.authority.matrix import ROLES

    surface = _surface()
    body = (
        TestClient(surface.app).get("/console/configuration", headers=_admin_headers(surface)).text
    )

    for invented in ("research", "validate"):
        assert f'"{invented}"' not in body, (
            f"{invented!r} is not a role this platform implements. Presenting it would name "
            f"a capability that does not exist — the drift FR-018 exists to stop."
        )
    # And the cells that ARE presented name only real roles.
    posture = (
        TestClient(surface.app)
        .get("/console/configuration", headers=_admin_headers(surface))
        .json()
    )
    for reference in posture["qualified_cells"]:
        assert reference.rsplit(":", 1)[-1] in set(ROLES)


def test_the_ungated_posture_is_disclosed_in_the_read_too() -> None:
    """FR-023b — a development estate must not look like a governed one on any page."""
    surface = _surface()

    posture = (
        TestClient(surface.app)
        .get("/console/configuration", headers=_admin_headers(surface))
        .json()
    )

    assert posture["gating"] == "ungated"


def test_the_connections_record_says_nothing_consumes_it_yet() -> None:
    """FR-022's honest middle. A setting shown as working that nothing reads is a lie of
    omission; a labelled one is a fact."""
    surface = _surface()

    posture = (
        TestClient(surface.app)
        .get("/console/configuration", headers=_admin_headers(surface))
        .json()
    )

    assert "not yet consumed" in posture["connections"]["consumed_by"]
    assert posture["connections"]["set_by"] == "console/alice"


@pytest.mark.parametrize("path", ["/console/configuration"])
def test_an_unauthenticated_caller_reaches_nothing(path: str) -> None:
    """The ordinary door, asserted because a console is a tempting place to forget it."""
    assert TestClient(_surface().app).get(path).status_code in (401, 403)
