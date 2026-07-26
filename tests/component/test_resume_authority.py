# SPDX-License-Identifier: Apache-2.0
"""US2 — resume re-authenticates rather than replaying a credential (T030-T034).

The substrate already makes replay unavailable: a resumed run is a new Nomad
allocation with a new attested identity (ADR-0048), so the prior credential does not
exist to be replayed. What these tests prove is the **negative** — no path here
reintroduces one. Read a failure as "someone added a way to carry authority across a
disruption", not as "the substrate leaked".
"""

from __future__ import annotations

import inspect

from core.durability import resume as resume_module
from core.durability.checkpoint import checkpoint_run
from core.durability.lease import RunLease
from core.durability.memory import InMemoryDurabilityProvider
from core.durability.resume import resume_run
from core.durability.types import CheckpointBlob
from core.tools.invoke import invoke_tool
from tests.component.conftest import make_run
from tests.harness import (
    assert_no_secret_values,
    durability_grant,
    fake_identity_fabric,
    frozen_clock,
)


def test_resume_manufactures_fresh_authority() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    run, _, _ = make_run(scope={"echo"})
    run.clock = clock
    run.run_id = "run-1"
    run.durability = provider
    run.grant = grant
    run.lease = RunLease(provider, run_id="run-1", holder_identity="alloc-1")
    run.lease.acquire()
    invoke_tool(run, "echo")
    before = run.authority.credential_id
    checkpoint_run(run)

    decision = resume_run(
        provider,
        blob_id="run-1",
        run_id="run-1",
        grant=grant,
        holder_identity="alloc-2",
        identity_fabric=fake_identity_fabric(tool_names={"echo"}, ceiling_tools={"echo"}),
        clock=clock,
    )

    assert decision.authority is not None
    after = decision.authority.credential.credential_id
    assert after != before, "resume issued a new credential, it did not recover the old one"


def test_checkpoint_carries_nothing_a_credential_could_be_rebuilt_from() -> None:
    clock = frozen_clock()
    provider = InMemoryDurabilityProvider()
    grant = durability_grant(clock, tool_names={"echo"})

    run, _, _ = make_run(scope={"echo"})
    run.clock = clock
    run.run_id = "run-1"
    run.durability = provider
    run.grant = grant
    checkpoint_run(run, payload={"progress": "step-1"})

    blob = provider.load("run-1")
    assert blob is not None
    dumped = blob.model_dump()
    assert_no_secret_values(dumped)
    # The credential id itself is absent, not merely redacted: nothing to correlate.
    assert run.authority.credential_id not in str(dumped)


def test_resume_has_no_parameter_for_a_recovered_credential() -> None:
    """Structural. The guarantee is the absence of a path, so assert the absence."""
    params = set(inspect.signature(resume_run).parameters)
    assert not params & {"credential", "authority", "token", "resume_token", "task_credential"}


def test_resume_module_never_reads_authority_out_of_a_checkpoint() -> None:
    source = inspect.getsource(resume_module)
    # It manufactures; it must never load. If this ever fails, look for a new field on
    # CheckpointBlob being fed into authority construction.
    assert "manufacture_authority" in source
    for forbidden in ("checkpoint.credential", "blob.credential", "payload['credential']"):
        assert forbidden not in source


def test_checkpoint_model_rejects_unknown_fields() -> None:
    """extra='forbid' is what stops a credential being smuggled in as an extra key."""
    assert CheckpointBlob.model_config["extra"] == "forbid"
