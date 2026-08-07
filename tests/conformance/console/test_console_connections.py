# SPDX-License-Identifier: Apache-2.0
"""C23–C25 — connections are governed like everything else, and *reachable* is its own fact.

**This is the scope the maintainer chose over the recommendation**, and the spec carries the
cost rather than hiding it: a binding names a cell the matrix either qualifies or does not, and
its failure is governance; a connection names an endpoint, and its failure is **connectivity**.
A governed value can be a wrong value. So `verification` never folds into a change's outcome —
"the fabric accepted it" and "the product answered" are two facts, and reporting the first as
the second tells an administrator the opposite of what happened.

**C25 is enforced by vocabulary, not by a filter.** A filter over credential-shaped names is
something a future field slips past; a closed set of location fields has nowhere to put one.
"""

from __future__ import annotations

from typing import Any

import pytest

from surfaces.api import console
from surfaces.api.authority_submit import ChangeOutcome
from surfaces.api.console import (
    CONNECTION_FIELDS,
    CONNECTIONS_PATH,
    ConsoleConfig,
    probe_connection,
)
from tests.harness.api_fixtures import surface_under_test

MODEL = "anthropic/claude-sonnet@5"


class _Submitter:
    def __init__(self) -> None:
        self.submitted: list[Any] = []

    def submit_change(self, change: Any) -> Any:
        self.submitted.append(change)
        return ChangeOutcome(state="applied")


def _connections_record() -> dict[str, Any]:
    return {
        "data": {
            "data": {
                "tfe": {"address": "https://app.terraform.io", "organization": "acme"},
                "vault": {"address": "https://vault.example", "namespace": "platform"},
            },
            "metadata": {"version": 2},
        }
    }


def _surface(submitter: Any = None) -> Any:
    config = ConsoleConfig(
        read_matrix=lambda: {"schema_version": 1, "cells": []},
        read_versioned=lambda path: _connections_record() if path == CONNECTIONS_PATH else None,
        quorum_configured=False,
    )
    return surface_under_test(console_config=config, authority_submitter=submitter)


def _admin(surface: Any) -> dict[str, str]:
    headers: dict[str, str] = surface.bearer(claims={"groups": ["platform-admin"]})
    return headers


# ── C23: the same governed path ────────────────────────────────────────────────────────


def test_row_c23_a_connection_change_rides_the_same_three_outcome_path() -> None:
    """C23 — a connection is not a special case with its own write mechanism."""
    from fastapi.testclient import TestClient

    submitter = _Submitter()
    surface = _surface(submitter)

    response = TestClient(surface.app).post(
        "/console/changes",
        json={
            "record": "product-connections",
            "payload": {"tfe": {"address": "https://app.terraform.io", "organization": "acme"}},
        },
        headers=_admin(surface),
    )

    assert response.status_code == 200
    assert response.json()["gating"] == "ungated"
    assert len(submitter.submitted) == 1
    assert submitter.submitted[0].record == "product-connections"


# ── C24: accepted is not reachable ─────────────────────────────────────────────────────


def test_row_c24_verification_is_reported_separately_from_the_change() -> None:
    """C24 — FR-018c, the row this phase exists for.

    A change response says what the *fabric* did. It says nothing about whether the product
    answered, because at submit time nobody has asked it.
    """
    from fastapi.testclient import TestClient

    surface = _surface(_Submitter())

    body = (
        TestClient(surface.app)
        .post(
            "/console/changes",
            json={
                "record": "product-connections",
                "payload": {"tfe": {"address": "https://nope.invalid"}},
            },
            headers=_admin(surface),
        )
        .json()
    )

    assert "verification" not in body, (
        "a change outcome must not carry a verification verdict; folding them is how "
        "'accepted' comes to read as 'working'"
    )


def test_row_c24_an_unreachable_product_renders_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The verdict a wrong address earns, and it must not be 'verified'."""
    # **Patched by dotted string, so this module imports no HTTP client at all.**
    # `test_no_live_dependencies.py` forbids one outside the enclave paths, and it is right
    # to: a test module holding an HTTP client is one call away from reaching a real product.
    # The string form patches the same object without the import.
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: (_ for _ in ()).throw(OSError("no route to host")),
    )

    assert probe_connection("tfe", "https://nope.invalid") == "unreachable"


def test_row_c24_any_http_answer_counts_as_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The finding analyze A1 predicted, pinned.

    TFE's API answers **401 without a token**, and 401 proves the endpoint is there. A probe
    treating non-2xx as down would report every correctly secured product as unreachable —
    and an administrator would go looking for a network fault that does not exist.
    """

    def _unauthorised(*_: Any, **__: Any) -> Any:
        import urllib.error  # noqa: PLC0415 — function-scoped so no HTTP client is imported here

        raise urllib.error.HTTPError("https://app.terraform.io", 401, "Unauthorized", {}, None)  # type: ignore[arg-type]

    monkeypatch.setattr("urllib.request.urlopen", _unauthorised)

    assert probe_connection("tfe", "https://app.terraform.io") == "verified", (
        "401 is the product telling us it is there and we are not authenticated — which is "
        "exactly right, since the console holds no credential"
    )


def test_an_unconfigured_address_is_unverified_not_unreachable() -> None:
    """Three states, and the third is 'nobody has said where it is'.

    Collapsing unverified into unreachable would report an estate that has not configured a
    product as one whose product is down.
    """
    assert probe_connection("tfe", "") == "unverified"
    assert probe_connection("tfe", "   ") == "unverified"


def test_the_verify_route_reports_per_product(monkeypatch: pytest.MonkeyPatch) -> None:
    """The route exists and is admin-gated like everything else on this surface."""
    from fastapi.testclient import TestClient

    monkeypatch.setattr(console, "probe_connection", lambda product, address: "verified")
    surface = _surface(_Submitter())

    response = TestClient(surface.app).post("/console/connections/verify", headers=_admin(surface))

    assert response.status_code == 200
    assert response.json()["verification"] == {"tfe": "verified", "vault": "verified"}


def test_the_verify_route_refuses_a_non_admin() -> None:
    from fastapi.testclient import TestClient

    surface = _surface(_Submitter())

    assert (
        TestClient(surface.app)
        .post("/console/connections/verify", headers=surface.bearer())
        .status_code
        == 403
    )


# ── C25: no credential can be entered ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "field", ["token", "password", "secret", "api_key", "client_secret", "credential"]
)
def test_row_c25_no_credential_shaped_field_is_accepted(field: str) -> None:
    """[GATE:no-secret-leak] C25 — the vocabulary has nowhere to put one.

    Parametrised over names somebody might reach for, but the guarantee is not the list: the
    permitted set is closed, so *any* field outside it refuses, including ones nobody thought
    to enumerate here.
    """
    from fastapi.testclient import TestClient

    submitter = _Submitter()
    surface = _surface(submitter)

    response = TestClient(surface.app).post(
        "/console/changes",
        json={
            "record": "product-connections",
            "payload": {"tfe": {"address": "https://app.terraform.io", field: "value"}},
        },
        headers=_admin(surface),
    )

    assert response.status_code == 400
    assert submitter.submitted == []


def test_row_c25_the_permitted_vocabulary_is_locations_only() -> None:
    """Asserted against the constant, so a widening is a deliberate edit somebody makes."""
    for product, fields in CONNECTION_FIELDS.items():
        assert fields, f"{product} permits no fields at all"
        for name in fields:
            assert name in {"address", "organization", "workspace", "namespace"}, (
                f"{name!r} is not a location. Connections name WHERE a product is; the "
                f"material used to authenticate to it lives in the trust store."
            )


def test_an_unknown_product_is_refused() -> None:
    """The closed set applies to products as well as fields."""
    from fastapi.testclient import TestClient

    submitter = _Submitter()
    surface = _surface(submitter)

    response = TestClient(surface.app).post(
        "/console/changes",
        json={"record": "product-connections", "payload": {"nomad": {"address": "https://x"}}},
        headers=_admin(surface),
    )

    assert response.status_code == 400
    assert submitter.submitted == []
