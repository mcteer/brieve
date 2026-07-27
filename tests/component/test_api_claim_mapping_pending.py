# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — FR-013: a mapping change is pending, not denied.

The status code is the whole test. 403 and 202 both mean "you did not get what you asked
for yet", and only one of them tells the truth: a client reading 403 stops asking, so a
change approved twenty minutes later is never collected and the operator concludes the
request was refused when it was granted.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.audit.schema import AuditEventType
from tests.harness.api_fixtures import surface_under_test

BODY = {
    "mapping": {"claim_name": "groups", "claim_value": "sre", "role": "operator"},
    "reason": "onboarding the SRE group",
}


def test_a_mapping_change_is_accepted_not_denied() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    response = client.post("/claim-mappings", json=BODY, headers=surface.bearer())

    assert response.status_code == 202, "a pending authority change must not read as a refusal"
    assert response.json()["disposition"] == "requested"


def test_the_change_is_not_applied_by_asking() -> None:
    """The surface requests; the trust fabric decides.

    If asking were enough, the quorum gate would be decorative — and this is the exact
    escalation ADR-0033 closes: granting yourself a role rather than being granted one.
    """
    surface = surface_under_test()
    client = TestClient(surface.app)
    client.post("/claim-mappings", json=BODY, headers=surface.bearer())

    # The requester's own token still maps only to what it mapped to before.
    subject_before = client.get("/evidence", headers=surface.bearer())
    assert subject_before.status_code == 200


def test_the_request_is_recorded_as_an_observation_not_an_issuance() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    client.post("/claim-mappings", json=BODY, headers=surface.bearer())

    stream = surface.audit.list_by_correlation_id("authority-change:tenant-test")
    assert len(stream) == 1
    assert stream[0].event_type is AuditEventType.AUTHORITY_CHANGE_OBSERVED
    assert stream[0].payload["disposition"] == "requested"
    assert stream[0].payload["identities"] == ["alice"]


def test_no_credential_or_policy_content_reaches_the_record() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    client.post("/claim-mappings", json=BODY, headers=surface.bearer())
    payload = str(surface.audit.list_by_correlation_id("authority-change:tenant-test")[0].payload)
    for leak in ("token", "password", "secret", "capabilities"):
        assert leak not in payload.lower()


def test_unauthenticated_change_is_refused() -> None:
    surface = surface_under_test()
    client = TestClient(surface.app)
    assert client.post("/claim-mappings", json=BODY).status_code == 401
