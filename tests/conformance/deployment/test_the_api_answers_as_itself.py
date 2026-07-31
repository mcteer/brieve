# SPDX-License-Identifier: Apache-2.0
"""Row: the northbound API is deployed, assembled, and answers as itself (017).

**Why a refusal and not a health check.** `surfaces/api/service.py::build()` migrates three
stores under the workload's attested identity BEFORE uvicorn binds — so for this surface,
answering at all already entails that Vault and Postgres were reached. That is why the
process *died* rather than serving badly when its Vault role was wrong.

A `/healthz` returning 200 would have passed throughout the entire period this API could not
start, because a process that exits and one that is slow are indistinguishable to a checker
that retries. The reason code is what makes the difference: it exists only if `create_app`
received a verifier, which is the exact wiring whose absence made this surface refuse
everyone (PR #78).
"""

from __future__ import annotations

import pytest

from tests.conformance.deployment.conftest import exec_request, require_running

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

API = "api"
RUNS = "http://127.0.0.1:8081/runs"


def test_the_api_reaches_a_working_state() -> None:
    """US1: deployed, placed, and not flapping."""
    assert require_running(API)


def test_the_api_answers_with_its_own_refusal() -> None:
    """US2: a response only a completed assembly can produce.

    `absent_identity` is the verifier's own reason code. A process that read no
    configuration has no verifier to produce it.
    """
    response = exec_request(API, RUNS)

    assert response.status == 401, (
        f"expected the API's own refusal, got HTTP {response.status}: {response.body[:300]}"
    )
    assert "absent_identity" in response.body, (
        "the API answered, but with nothing identifying it as this surface. A generic "
        "rejection is producible by anything listening on the port — SC-002 is the "
        "criterion this row exists for, and it is the one a liveness check fails."
    )


def test_a_generic_answer_does_not_satisfy_the_gate() -> None:
    """SC-002, stated as an assertion rather than as a comment.

    Keeps this gate from degrading into a liveness check: a bare 200, an empty body, or a
    refusal carrying no reason code must not count as the surface having answered.
    """
    response = exec_request(API, RUNS)

    assert response.status != 200, "an unauthenticated request must not succeed"
    assert response.body.strip(), "an empty body identifies no surface"
    assert "detail" in response.body, (
        "the refusal carries no reason code, so it proves only that something answered"
    )
