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

**The claim got STRICTER on 2026-08-28, and E4 went with it.** The first fix bounded a run to
its own workspace, which worked and cost one permanent Vault identity entity per Build against
a ceiling that logins fail at (ADR-0072). The measurement moved to the long-lived surface
instead, so a run now holds no policy-write authority at all and has no own workspace to
reach. E4 required exactly that and is withdrawn with its reason; what replaces it is
`test_the_measurement_still_works`, because "refuses everything" must not be allowed to mean
"the product is broken".
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


def _admin_json_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    """Administrator POST. Setup only — never an assertion, because a refusal to an
    administrator proves nothing."""
    import json as _json

    addr = os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200")
    ctx = ssl.create_default_context(cafile=os.environ.get("VAULT_CACERT") or None)
    request = urllib.request.Request(  # noqa: S310
        f"{addr}/v1/{path}",
        method="POST",
        data=_json.dumps(body).encode(),
        headers={"X-Vault-Token": os.environ.get("VAULT_TOKEN", "")},
    )
    with urllib.request.urlopen(request, timeout=20, context=ctx) as response:  # noqa: S310
        return dict(_json.loads(response.read()))


def _as(token: str, path: str, *, method: str = "GET", body: dict[str, str] | None = None) -> int:
    """One request as a specific token. The verdict, not the payload."""
    import json as _json

    addr = os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200")
    ctx = ssl.create_default_context(cafile=os.environ.get("VAULT_CACERT") or None)
    request = urllib.request.Request(  # noqa: S310
        f"{addr}/v1/{path}",
        method=method,
        data=_json.dumps(body).encode() if body else None,
        headers={"X-Vault-Token": token},
    )
    try:
        with urllib.request.urlopen(request, timeout=20, context=ctx) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as error:
        return int(error.code)


def _admin_list(path: str) -> list[str]:
    """LIST as administrator. Enumeration for a measurement, never for an assertion of denial."""
    import json as _json

    addr = os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200")
    ctx = ssl.create_default_context(cafile=os.environ.get("VAULT_CACERT") or None)
    request = urllib.request.Request(  # noqa: S310
        f"{addr}/v1/{path}",
        method="LIST",
        headers={"X-Vault-Token": os.environ.get("VAULT_TOKEN", "")},
    )
    with urllib.request.urlopen(request, timeout=20, context=ctx) as response:  # noqa: S310
        return list(_json.loads(response.read())["data"]["keys"])


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


def test_the_measurement_still_works(another_runs_workspace: str) -> None:
    """WHAT REPLACED E4, and the row without which every refusal below is worthless.

    A run that can reach nothing is trivially safe and useless. E4 used to catch that by
    requiring the run to reach its OWN workspace; there is no own workspace now, so the same
    duty falls here: the surface must still be able to write, measure and destroy in the
    namespace, or 042's impact check has no instrument and 054 broke the product to secure it.

    Asserted against the deployed grant rather than by driving a measurement, because the
    surface's own rows drive that path and this one is about who holds the authority.
    """
    sweep = _admin_json("sys/policies/acl/scratch-sweep")["data"]["policy"]
    assert '"create"' in sweep and '"update"' in sweep, (
        "the surface cannot write in the measurement namespace, so nothing can — the run's "
        "grant was removed on the understanding that this one exists"
    )


@pytest.mark.parametrize("action", ["read", "write", "delete"])
@pytest.mark.parametrize("target", ["mine", "existing"])
def test_rows_e1_e3_a_run_reaches_no_scratch_policy(
    verdicts: dict[tuple[str, str], int], target: str, action: str
) -> None:
    """ROWS E1-E3, widened. A run reaches NO measurement policy — not another's, not one named
    after itself.

    The three actions against another run's workspace returned 200, 200 and 204 on 2026-08-27
    against the estate-wide grant. They are all 403 now, and so is every attempt on a name the
    run might think is its own, because a dispatched run holds no policy-write authority at all.
    """
    if (target, action) not in verdicts:
        pytest.skip(f"{target}/{action} is not one of the attempted pairs")
    assert verdicts[(target, action)] == 403, (
        f"a run can {action} a scratch policy ({target}). 054 removed `scratch-policy-check` "
        "from the agent-run role; if this passes, the grant is back, and with it one permanent "
        "Vault identity entity per Build unless the per-run mechanism came back too."
    )


def test_row_e5_the_safety_case_can_lose(another_runs_workspace: str) -> None:
    """ROW E5 — **the row the rest depend on**, rebuilt for the new mechanism (FR-004, SC-003).

    It used to widen the deployed grant and confirm the break-in worked again. That proves
    nothing now: the run holds no scratch grant at all, so widening a policy it does not carry
    would change nothing and the row would pass while asserting nothing — the exact failure it
    exists to prevent.

    So the attribution moves to where the property now lives. A token carrying
    `scratch-policy-check` — the grant that was removed from the run — CAN write in the
    namespace. Therefore the run's refusal is caused by not holding that policy, and not by a
    broken template, an unreachable Vault, or a probe that never got a token.

    **Mints rather than mutates.** An earlier version of this row rewrote the deployed policy
    and restored it in a `finally`; touching a role or a policy in a shared estate to prove a
    point is a risk this version does not need to take.
    """
    document = {"policy": 'path "secret/data/e5" { capabilities = ["read"] }'}
    minted = _admin_json_post(
        "auth/token/create",
        {"policies": ["scratch-policy-check"], "ttl": "2m", "no_parent": True},
    )
    token = minted["auth"]["client_token"]

    name = "scratch-agent-e5-attribution-current"
    try:
        assert _as(token, f"sys/policies/acl/{name}", method="PUT", body=document) in (200, 204), (
            "the grant removed from the run does not itself permit writing, so the refusals "
            "above are caused by something other than its absence. Find out what before "
            "trusting any row in this file."
        )
    finally:
        _admin(f"sys/policies/acl/{name}", method="DELETE")


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
    }
    role = _admin_json("auth/nomad/role/agent-run")
    assert set(role["data"]["token_policies"]) == expected, (
        "a run's policy set changed. If a READ grant was removed, ADR-0057's reasoning is "
        "being reversed by accident, which is the thing 054 was scoped to avoid. If "
        "`scratch-policy-check` is back, so is one permanent identity entity per Build."
    )
    assert "scratch-policy-check" not in role["data"]["token_policies"], (
        "the run holds policy-write authority again — the grant 054 removed, and the reason "
        "the per-run identity that cost an entity per Build is no longer needed"
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
    assert verdicts[("existing", "write")] == 403


def test_row_e10_a_restarted_run_inherits_nothing(verdicts: dict[tuple[str, str], int]) -> None:
    """ROW E10, and FR-016 is now satisfied by there being nothing to inherit.

    The original requirement said a restarted run must reach the workspace it had before. The
    maintainer reversed it: a dependency outage restarting a job repeatedly would have every
    attempt contending for one workspace, which is this feature's own defect self-inflicted.

    After the measurement moved off the run, the requirement is met the strongest way available
    — a run has no workspace at all, so an attempt cannot inherit one. The previous attempt's
    is refused for the same reason every other name is.
    """
    assert verdicts[("existing", "read")] == 403
    assert verdicts[("mine", "write")] == 403, (
        "a run can write a policy named after its own allocation. That was the previous "
        "design and it cost one permanent identity entity per Build."
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


def test_a_build_creates_no_identity_entity() -> None:
    """**FR-018, and the row whose absence let a correct feature ship an unbounded cost.**

    054's first mechanism bounded a run to its own workspace and created one permanent Vault
    identity entity per Build to do it. Every gate the feature had asked whether the bound
    *held*; none asked what it *cost to maintain*. Entities have no TTL, the documented ceiling
    on integrated storage is a hard 256 MiB across 256 shards, and entity writes happen on every
    login — so the failure mode was that logins stop and every Build fails, in about 2.4 months
    at 10,000 users (ADR-0072).

    This row is what that requirement bought. It reads the identity store either side of a real
    dispatch, which is how the defect was found in the first place.
    """
    import subprocess
    import time

    def entity_count() -> int:
        listed = _admin_list("identity/entity/id")
        return len(listed)

    before = entity_count()
    correlation = f"corr-fr018-{int(time.time())}"
    dispatched = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "nomad",
            "job",
            "dispatch",
            "-detach",
            "-meta",
            f"correlation_id={correlation}",
            "-meta",
            "subject_user_id=alice",
            "-meta",
            "tenant_id=default",
            "-meta",
            "agent_definition_id=vault-agent",
            "-meta",
            f"run_id={correlation}",
            "-meta",
            "step_index=0",
            "agent-run",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert dispatched.returncode == 0, f"could not dispatch: {dispatched.stderr[:200]}"
    time.sleep(20)

    after = entity_count()
    assert after == before, (
        f"a Build created {after - before} identity entity(ies). They never expire, the "
        "ceiling is hard, and entity writes happen on every login — so this grows until "
        "logins fail. `user_claim` is naming something per-run again (ADR-0072)."
    )
