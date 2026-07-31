# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — who may manufacture authority (016 T019, FR-020).

This feature creates a privilege that did not exist: whoever can sign with the grant key can
mint task scope for any registered agent. ADR-0056's Notes name it, and FR-020 requires it be
a bounded, named grant — which makes the signing policy as load-bearing as the ceiling
records themselves, because it is the ceiling's *issuer*.

**The failure this guards is silent.** Widening that policy breaks nothing visible: every
other row in this directory keeps passing, because the grants they use are still correctly
scoped. Only this row notices, which is why it exists rather than being left to the
observation that the policy looks narrow.
"""

from __future__ import annotations

import urllib.error
from typing import Any

import pytest

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

SIGN_PATH = "task-authority/sign/grant-issuer"


def test_row_the_signing_policy_grants_one_path_and_no_more(vault: Any) -> None:
    """The bound, read from the policy Vault is enforcing rather than from the Terraform.

    Reading the source would assert what we intended; reading the policy asserts what is in
    force. Those differ exactly when something went wrong, which is the case that matters.
    """
    document = vault("sys/policies/acl/task-authority-sign")["data"]["policy"]

    assert SIGN_PATH in document, "the policy does not name the signing path at all"
    assert "task-authority/*" not in document, (
        "the policy grants the whole transit mount. Anyone holding it could sign with any "
        "key there, and this feature's privilege is supposed to be one key, one operation."
    )
    assert '"sudo"' not in document and "sudo" not in document.split("capabilities")[-1][:80], (
        "the signing policy carries sudo"
    )


def test_row_a_workload_without_the_policy_cannot_mint(vault: Any) -> None:
    """The refusal is Vault's, against a token that holds every OTHER platform policy.

    Uses the agent-run role's own token rather than a contrived one: that is the identity a
    compromised allocation would actually have, and it is the identity that must not be able
    to manufacture authority for itself.
    """
    # A token carrying the run role's policies and nothing else.
    minted = vault(
        "auth/token/create",
        {"policies": ["harness-database", "harness-authority-read"], "ttl": "60s"},
    )["auth"]["client_token"]

    try:
        vault(
            SIGN_PATH,
            {"input": "YWJj", "hash_algorithm": "sha2-256", "marshaling_algorithm": "jws"},
            token=minted,
        )
    except urllib.error.HTTPError as exc:
        assert exc.code == 403, f"expected a refusal, got HTTP {exc.code}"
    else:
        raise AssertionError(
            "a workload holding only the run role's policies was able to sign a grant. "
            "Whoever can sign can mint task scope for any agent, so this is the whole "
            "ceiling made optional — and every other row here would still be green."
        )


def test_row_the_issuer_policy_itself_can_mint(vault: Any) -> None:
    """The positive half. Without it the row above passes when signing is broken for everyone.

    A bound that refuses everybody is not a bound, it is an outage, and the two look
    identical from the refusal side.
    """
    minted = vault("auth/token/create", {"policies": ["task-authority-sign"], "ttl": "60s"})[
        "auth"
    ]["client_token"]

    response = vault(
        SIGN_PATH,
        {"input": "YWJj", "hash_algorithm": "sha2-256", "marshaling_algorithm": "jws"},
        token=minted,
    )

    assert response["data"]["signature"].startswith("vault:v"), (
        "the issuer policy could not sign, so the refusal above proves nothing"
    )
