# SPDX-License-Identifier: Apache-2.0
"""GATE:authority — a run's write grant names only its own workspace (054, rows E1-E4).

**The defect these rows replace was demonstrated, so they are demonstrated too.** On
2026-08-27 a token carrying exactly what the `agent-run` role grants read (200), overwrote
(200) and deleted (204) another run's measurement policy. `scratch.tf` granted
`scratch-agent-*` estate-wide while the names it protected were already per-run: the namespace
was partitioned by convention and unpartitioned by authority.

**These rows make the attempt rather than reading the configuration.** Same shape as 018's
registry-isolation rows — a real attempt under a real run's authority, against the live control
plane, with every refusal observed. `run_authority.py` explains why borrowing that authority
needed a probe job rather than a minted token; the short version is that a minted token has no
identity entity, so it would be refused everything and this file would pass while asserting
nothing.

**E4 is not optional and is the reason the others mean anything.** An authority that resolves
to nothing refuses everything. Without a row requiring the run to reach its OWN workspace, a
completely broken grant satisfies every refusal here.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest
from tests.conformance.authority.run_authority import attempt_under_run_authority

pytestmark = pytest.mark.enclave

#: A policy in the measurement namespace that belongs to somebody else. Seeded and removed with
#: administrator authority, because the whole question is whether a RUN can touch it.
FOREIGN = "scratch-agent-not-this-run-054-current"


def _admin(path: str, *, method: str = "GET", body: dict[str, str] | None = None) -> int:
    addr = os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200")
    token = os.environ.get("VAULT_TOKEN", "")
    if not token:
        pytest.fail(
            "VAULT_TOKEN is unset. These rows attempt a real break-in against the real control "
            "plane and cannot invent an estate; they fail rather than skip. Run `make dev-up`."
        )
    ctx = ssl.create_default_context(cafile=os.environ.get("VAULT_CACERT") or None)
    request = urllib.request.Request(  # noqa: S310
        f"{addr}/v1/{path}",
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"X-Vault-Token": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=20, context=ctx) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)


@pytest.fixture
def another_runs_workspace() -> Iterator[str]:
    """A measurement policy owned by a different run, for the duration of one test."""
    document = {"policy": 'path "secret/data/other" { capabilities = ["read"] }'}
    assert _admin(f"sys/policies/acl/{FOREIGN}", method="PUT", body=document) in (200, 204)
    yield FOREIGN
    _admin(f"sys/policies/acl/{FOREIGN}", method="DELETE")


@pytest.fixture
def verdicts(another_runs_workspace: str) -> dict[tuple[str, str], int]:
    """What a real run's authority actually got, one login, five attempts."""
    return {
        (a.path, a.action): a.status for a in attempt_under_run_authority(another_runs_workspace)
    }


def test_row_e4_a_run_reaches_its_own_workspace(verdicts: dict[tuple[str, str], int]) -> None:
    """ROW E4 — and the row that makes E1-E3 evidence rather than noise.

    A grant that resolves to nothing refuses everything and would satisfy every refusal row
    here while breaking the impact check entirely. Asserted FIRST for that reason.
    """
    assert verdicts[("own", "write")] in (200, 204), (
        "a run cannot write its own measurement policy, so `vault_policy_impact` has no "
        "instrument and every refusal below proves only that the grant is broken"
    )
    assert verdicts[("own", "read")] == 200


@pytest.mark.parametrize("action", ["read", "write", "delete"])
def test_rows_e1_e3_a_run_cannot_touch_another_runs_workspace(
    verdicts: dict[tuple[str, str], int], action: str
) -> None:
    """ROWS E1-E3 — the defect, attempted again under the fix.

    These three actions returned 200, 200 and 204 on 2026-08-27 against the estate-wide grant.
    """
    assert verdicts[("foreign", action)] == 403, (
        f"a run {action}s another run's measurement policy. The grant in `scratch.tf` is "
        f"estate-wide again, or `user_claim` no longer names the allocation — the two must "
        f"change together, and E4 above is what catches the other direction."
    )
