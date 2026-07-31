# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — the failure path prints allocation output (017, FR-004).

Not boilerplate here. FR-004 requires reporting the failing process's own account, and an
allocation's stderr is exactly where a credential surfaces: this platform's surfaces obtain
Vault tokens and dynamic database credentials during the start-up that fails.

So the one thing this gate must print is the one place a secret would be.
"""

from __future__ import annotations

import pytest

from tests.conformance.deployment.conftest import redact

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


def _token_shaped(prefix: str) -> str:
    """A value with a real credential's SHAPE and none of its meaning.

    Assembled at runtime rather than written out. A literal here matches the provider's
    published secret-scanning pattern, so committing one gets the push blocked — correctly,
    since a scanner cannot tell a fixture from a leak, and one that tried would be the
    weaker tool. The redaction under test keys on the prefix, which is all this needs.
    """
    return prefix + "CAESI" + ("x" * 24)


def test_a_vault_token_never_reaches_the_report() -> None:
    leaked = f"authenticated with {_token_shaped('hvs.')} and proceeded"

    assert _token_shaped("hvs.") not in redact(leaked)
    assert "redacted" in redact(leaked)


def test_a_service_token_never_reaches_the_report() -> None:
    leaked = f"batch token {_token_shaped('hvb.')} issued"

    assert _token_shaped("hvb.") not in redact(leaked)


def test_a_bearer_token_never_reaches_the_report() -> None:
    # A JWT header, base64 of {"alg":"RS256","typ":"JWT"} — structure, not a credential.
    leaked = "Authorization: Bearer " + "eyJ" + "hbGciOiJSUzI1NiJ9" + ".body.sig"

    assert "hbGciOiJSUzI1NiJ9" not in redact(leaked)


def test_redaction_keeps_the_diagnosis_readable() -> None:
    """A redaction that blanked everything would satisfy the rule and destroy FR-004.

    The refusal that motivated this whole feature is the text that must survive.
    """
    real = 'error validating claims: claim "nomad_job_id" does not match any bound value'
    assert redact(real) == real
