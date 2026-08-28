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
from typing import Any

import pytest

from tests.conformance.workspace.run_authority import attempt_under_run_authority

#: BOTH markers, following 018. `enclave` keeps these out of the hermetic lane, which runs
#: `-m "not enclave"` and would otherwise collect them and fail for want of an estate.
#: `host_enclave` is what selects them in the lane that names this directory — and is also
#: true: a row that drives the scheduler cannot run inside something the scheduler placed.
pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

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


def _admin_json(path: str) -> dict[str, Any]:
    """Read a record with administrator authority. Setup and inspection only, never assertion."""
    import json as _json

    addr = os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200")
    ctx = ssl.create_default_context(cafile=os.environ.get("VAULT_CACERT") or None)
    request = urllib.request.Request(  # noqa: S310
        f"{addr}/v1/{path}", headers={"X-Vault-Token": os.environ.get("VAULT_TOKEN", "")}
    )
    with urllib.request.urlopen(request, timeout=20, context=ctx) as response:  # noqa: S310
        return dict(_json.loads(response.read()))


def _admin_body(path: str) -> str:
    """The deployed policy text, so a row that widens it can put it back exactly."""
    return str(_admin_json(path)["data"]["policy"])


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


def test_row_e5_the_safety_case_can_lose(another_runs_workspace: str) -> None:
    """ROW E5 — **the row that makes every other row here mean something** (FR-004, SC-003).

    Widen the grant back to what it was, confirm the break-in succeeds again, and restore.
    Without this, E1-E3 could be passing for any reason at all — a broken login, an unrelated
    denial, a probe that never reached Vault — and nobody would know.

    Restores in a `finally`, because a row that widened the estate and died would leave the
    defect in place while reporting a failure that looks like the feature's.
    """
    widened = (
        'path "sys/policies/acl/scratch-agent-*" '
        '{ capabilities = ["create", "update", "delete", "read"] }\n'
        'path "auth/token/create/scratch-check" { capabilities = ["update"] }'
    )
    original = _admin_body("sys/policies/acl/scratch-policy-check")
    assert original, "the deployed grant could not be read, so it cannot be safely restored"
    try:
        assert _admin(
            "sys/policies/acl/scratch-policy-check", method="PUT", body={"policy": widened}
        ) in (200, 204)
        verdicts = {
            (a.path, a.action): a.status
            for a in attempt_under_run_authority(another_runs_workspace)
        }
        assert verdicts[("foreign", "write")] in (200, 204), (
            "the estate-wide grant is back and a run STILL cannot reach another run's "
            "workspace, so the refusal in E1-E3 is coming from something other than this "
            "feature — find out what before trusting any row in this file"
        )
    finally:
        _admin("sys/policies/acl/scratch-policy-check", method="PUT", body={"policy": original})

    restored = {
        (a.path, a.action): a.status for a in attempt_under_run_authority(another_runs_workspace)
    }
    assert restored[("foreign", "write")] == 403, "the narrowing was not restored"


def test_row_e6_no_read_a_run_could_make_before_is_refused_now(
    verdicts: dict[tuple[str, str], int],
) -> None:
    """ROW E6 — reads must not narrow (FR-006, SC-005).

    ADR-0057 parked 016 because narrowing READS starves context-hungry agents, and 054 reopened
    only the write case. A run's five policies are what it reads through; this asserts the set
    is untouched, because narrowing a read by accident would be the one outcome that record
    forbids.
    """
    expected = {
        "agent-pack-secrets",
        "harness-authority-read",
        "harness-database",
        "model-credential-read",
        "scratch-policy-check",
    }
    role = _admin_json("auth/nomad/role/agent-run")
    assert set(role["data"]["token_policies"]) == expected, (
        "a run's policy set changed. If a READ grant was removed, ADR-0057's reasoning is "
        "being reversed by accident, which is the thing 054 was scoped to avoid."
    )


def test_row_e7_the_sweeper_keeps_the_breadth_it_needs() -> None:
    """ROW E7 — narrowing a run must not narrow the service (FR-008).

    Finding an orphan means finding a name nobody told you about, so the sweep genuinely needs
    `list` over the namespace — which is exactly why a dispatched run must not have it. Two
    grants, two jurisdictions, and 054 touches only one.
    """
    sweep = _admin_json("sys/policies/acl/scratch-sweep")["data"]["policy"]
    assert '"list"' in sweep and "sys/policies/acl" in sweep, (
        "the sweeper lost its enumeration. Orphans from a killed allocation are now "
        "unfindable, and 'always destroyed' stops being checkable."
    )

    run = _admin_json("sys/policies/acl/scratch-policy-check")["data"]["policy"]
    assert '"list"' not in run, (
        "a dispatched run can now enumerate the policy namespace. That is reconnaissance, and "
        "it is what lets a run discover the workspace names 054 stops it reaching."
    )


def test_row_e8_the_refusal_is_vaults_and_not_the_pipelines(
    verdicts: dict[tuple[str, str], int],
) -> None:
    """ROW E8 — the bound must survive a platform bug (FR-002).

    `b7c2a2f` refuses a call claiming another run's id, in the governance hook. That is layer
    two. 042's own comment says why layer three matters: the ACL is *"the only one that
    survives a platform bug"*.

    This row is satisfied by construction and asserts it anyway: the probe talks to Vault
    directly and never enters the dispatch pipeline, so no hook, no handler and no guard is
    between it and the refusal. What denies it is the trust fabric.
    """
    from tests.conformance.workspace import run_authority

    source = run_authority._ATTEMPT
    assert "auth/nomad/login" in source and "sys/policies/acl" in source
    assert "vault_policy_impact" not in source and "hook" not in source.lower(), (
        "the probe now goes through platform code, so these rows would pass on a pipeline "
        "guard rather than on the estate's own answer — which is the claim E8 exists to make."
    )
    assert verdicts[("foreign", "write")] == 403


def test_row_e10_a_restarted_run_gets_its_own_workspace(another_runs_workspace: str) -> None:
    """ROW E10 — FR-016, as REVERSED on 2026-08-27.

    The original requirement said a restarted run must reach the workspace it had before. The
    maintainer reversed it, and the reasoning is the point: a dependency outage restarting a
    job repeatedly would have every attempt contending for ONE workspace — this feature's own
    defect, self-inflicted.

    So each attempt gets its own, and cannot reach the one before it. That is asserted here by
    treating a *previous* attempt's workspace exactly as a foreign one, because to a restarted
    run that is precisely what it is.

    What a dead attempt leaves behind is the sweep's job (E7), which is what that sweep exists
    for.
    """
    verdicts = {
        (a.path, a.action): a.status for a in attempt_under_run_authority(another_runs_workspace)
    }
    assert verdicts[("own", "write")] in (200, 204)
    assert verdicts[("foreign", "read")] == 403, (
        "a run reaches a workspace that is not its own. A restarted run must not inherit the "
        "previous attempt's, or an outage turns repeated restarts into repeated contention."
    )


def test_row_e9_the_grant_expires_and_is_not_standing() -> None:
    """ROW E9 — SC-008's second half. A credential that outlives its work is a standing one.

    The renewal half needs a Build slower than one lifetime and belongs to the eval lane; what
    is checkable here is the property that makes renewal necessary at all — the run's token is
    short-lived by construction, so nothing it holds becomes permanent.

    Asserted against the deployed role rather than a fixture, because a TTL that drifted in
    Terraform would leave this feature handing out long-lived write authority while every other
    row stayed green.
    """
    role = _admin_json("auth/nomad/role/agent-run")["data"]
    ttl = int(role.get("token_ttl") or 0)
    assert 0 < ttl <= 3600, (
        f"a dispatched run's token lives {ttl}s. Short by construction is what keeps per-task "
        "authority from becoming a standing credential (Principle IV)."
    )
    assert role.get("token_type") == "service", (
        "a batch token cannot be renewed, so a Build slower than one lifetime would fail its "
        "measurement rather than continue — the outcome FR-014 exists to avoid"
    )
