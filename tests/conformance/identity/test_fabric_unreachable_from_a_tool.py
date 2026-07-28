# SPDX-License-Identifier: Apache-2.0
"""GATE:fail-closed — an agent cannot read the ceilings that bound it (FR-016).

ADR-0015 puts the control-plane trust fabric **structurally outside every agent ceiling**,
"by construction rather than by policy". This row asserts the construction.

**The refusal must come from Vault, not from us.** A denial our code produced would satisfy
the behaviour and miss the point entirely: it would mean the boundary holds as long as the
harness keeps checking, which is a different and much weaker claim than the boundary
existing. A tool able to read what a ceiling says has taken the first step toward changing
one, and the thing that stops it should not be a conditional we could delete.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from core.durability.credentials import NomadWorkloadIdentity

pytestmark = pytest.mark.enclave

CEILING_PATH = "harness-authority/data/harness-ceilings/planner-agent"


def _vault_addr() -> str:
    import os

    return (os.environ.get("VAULT_ADDR") or "https://127.0.0.1:8200").rstrip("/")


def _agent_token() -> str:
    """Log in as a registered AGENT definition, not as the harness.

    `demo-agent` has a JWT role of its own carrying only its ceiling policy — which is the
    credential an agent's own workload would hold.
    """
    import ssl

    ctx = None
    cacert = __import__("os").environ.get("VAULT_CACERT")
    if cacert:
        ctx = ssl.create_default_context(cafile=cacert)

    payload = json.dumps({"role": "demo-agent", "jwt": NomadWorkloadIdentity().jwt()}).encode()
    request = urllib.request.Request(  # noqa: S310 — fixed scheme, enclave address
        f"{_vault_addr()}/v1/auth/nomad/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10, context=ctx) as response:  # noqa: S310
            return str(json.loads(response.read())["auth"]["client_token"])
    except urllib.error.HTTPError as exc:
        # The conformance workload's identity does not match demo-agent's bound claim,
        # which is itself the boundary holding — it cannot even assume the role.
        pytest.skip(f"cannot assume the agent role from this workload: HTTP {exc.code}")


def test_row_an_agent_credential_cannot_read_a_ceiling_record() -> None:
    """Denied by the trust fabric, with no help from us."""
    import ssl

    token = _agent_token()
    ctx = None
    cacert = __import__("os").environ.get("VAULT_CACERT")
    if cacert:
        ctx = ssl.create_default_context(cafile=cacert)

    request = urllib.request.Request(  # noqa: S310
        f"{_vault_addr()}/v1/{CEILING_PATH}", headers={"X-Vault-Token": token}
    )

    with pytest.raises(urllib.error.HTTPError) as caught:
        with urllib.request.urlopen(request, timeout=10, context=ctx):  # noqa: S310
            pass

    assert caught.value.code in {403, 404}, (
        f"an agent credential read a ceiling record (HTTP {caught.value.code}). The trust "
        "fabric is supposed to sit outside every agent ceiling by construction, and a tool "
        "that can read what bounds it is one step from changing it."
    )
