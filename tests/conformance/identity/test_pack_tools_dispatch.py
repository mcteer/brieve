# SPDX-License-Identifier: Apache-2.0
"""GATE:conformance — a pack tool reaches a real product through the real pipeline (T023).

**This is the row the Vault pack exists for.** Terraform proves *adoption*; Vault proves
*invocation*: a dispatched allocation loads the pack under its own attested identity,
manufactures authority whose ceiling names `vault_read`, and invokes it through the same
hook pipeline as every other tool — against a Vault that actually answers.

**Dispatched, not simulated on the host.** The first version of this file called the
handler from the host and failed with `CredentialUnavailableError`: the handler
manufactures credentials from the allocation's workload identity, which no host process
holds — a property the platform is built on, not a test inconvenience. So the row drives
the scheduler (the thing a host process legitimately can) and asserts the allocation's
outcome, on the `test_dispatched_end_to_end` pattern.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid

import pytest

from surfaces.dispatch.nomad import NomadDispatcher
from surfaces.probes import vault_probe

# BOTH markers: `-m "not enclave"` does not deselect host_enclave alone.
pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

NOMAD_ADDR = "http://127.0.0.1:4646"
JOB_ID = "agent-run"
TENANT = "tenant-conformance"


def _job_registered() -> bool:
    try:
        with urllib.request.urlopen(f"{NOMAD_ADDR}/v1/job/{JOB_ID}", timeout=3) as response:  # noqa: S310
            return json.loads(response.read()).get("ParameterizedJob") is not None
    except (urllib.error.URLError, OSError):
        return False


def _allocation_state(dispatched_job_id: str, *, timeout: float = 720.0) -> tuple[str, str]:
    """Wait for the allocation to finish. Twelve minutes — a cold dependency install has
    been measured past seven, and a shorter budget reports `timeout` for a working run."""
    deadline = time.monotonic() + timeout
    alloc_id = ""
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(  # noqa: S310
                f"{NOMAD_ADDR}/v1/job/{dispatched_job_id}/allocations", timeout=5
            ) as response:
                allocations = json.loads(response.read())
        except (urllib.error.URLError, OSError):
            allocations = []
        if allocations:
            alloc = allocations[0]
            alloc_id = alloc.get("ID", "")
            status = alloc.get("ClientStatus", "")
            if status in {"complete", "failed"}:
                return status, alloc_id
        time.sleep(2)
    return "timeout", alloc_id


@pytest.fixture
def dispatcher() -> NomadDispatcher:
    if not _job_registered():
        pytest.fail(
            f"the parameterized job {JOB_ID!r} is not registered — run `make dev-up`. Not "
            "skippable: a pack tool proven only hermetically has not been proven to run."
        )
    return NomadDispatcher(nomad_addr=NOMAD_ADDR, job_id=JOB_ID)


def test_vault_is_reachable_from_the_probe_the_pack_names() -> None:
    """The precondition, separated so a Vault outage reports as a Vault outage rather than
    as a pack defect — the two look identical from a denied tool call.

    The probe's first live run failed HERE: it ignored `VAULT_CACERT`, so TLS under the
    enclave's own CA read as unreachability — the probe inventing an outage for a product
    that was up, which is the exact confusion it exists to remove. Fixed in the probe.
    """
    reachable, detail = vault_probe("vault")
    assert reachable, f"vault is not reachable ({detail}); the rows below cannot mean anything"


def test_a_dispatched_run_invokes_a_pack_tool_through_the_real_pipeline(
    dispatcher: NomadDispatcher,
) -> None:
    """FR-027b end to end: pack loaded, ceiling resolved, `vault_read` invoked, in an
    allocation, against the live product.

    The entrypoint fails the allocation if the invoke is refused, so `complete` means the
    tool ran — through `invoke_tool`, which is the one pipeline there is (FR-003). The
    definition, its ceiling naming `vault_read`, and its bindings record carrying the pack
    all come from the trust fabric; the allocation authenticates as itself.
    """
    correlation_id = f"pack-dispatch-{uuid.uuid4().hex[:12]}"

    dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        agent_definition_id="vault-agent",
        requested_tools=frozenset({"vault_read"}),
        subject_roles=frozenset({"vault-operator"}),
        packs=frozenset({"vault"}),
        invoke_tools=True,
    )

    dispatched = dispatcher.dispatched_job_id(correlation_id)
    assert dispatched, "the dispatcher returned a handle naming no scheduled job"
    status, alloc_id = _allocation_state(dispatched)
    assert status == "complete", (
        f"the pack-tool allocation ended {status!r} (alloc {alloc_id}). Run "
        f"`nomad alloc logs -stderr {alloc_id} run` — a refused invoke names its "
        f"reason_code there, and a resolution failure names which record was missing"
    )


def test_a_definition_without_the_pack_cannot_reach_its_tool(
    dispatcher: NomadDispatcher,
) -> None:
    """The negative, and what makes the row above mean something.

    `planner-agent` names no pack, and its ceiling does not know `vault_read` — so a
    dispatch requesting it must FAIL the allocation. An entrypoint that quietly loaded
    every pack, or a ceiling parser that accepted unknown tools, would complete this.
    """
    correlation_id = f"pack-dispatch-neg-{uuid.uuid4().hex[:12]}"

    dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id="alice",
        tenant_id=TENANT,
        agent_definition_id="planner-agent",
        requested_tools=frozenset({"vault_read"}),
        subject_roles=frozenset({"operator"}),
        # No packs. vault_read is not in the fixture registry, not in planner's ceiling,
        # and not in the operator role — three independent reasons this must refuse.
        invoke_tools=True,
    )

    dispatched = dispatcher.dispatched_job_id(correlation_id)
    assert dispatched, "the dispatcher returned a handle naming no scheduled job"
    status, alloc_id = _allocation_state(dispatched)
    assert status == "failed", (
        f"a run requesting a pack tool with no pack ended {status!r} (alloc {alloc_id}) — "
        f"something resolved authority for a tool nothing provided"
    )
