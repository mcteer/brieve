# SPDX-License-Identifier: Apache-2.0
"""What a dispatched allocation runs, for the conformance row.

The other half of :class:`~surfaces.dispatch.nomad.NomadDispatcher`. Without something on
this end the dispatcher submits to a job that does nothing, and "run start returns a
handle" would be true in the sense that a handle came back and false in the sense that
anything started.

**This lives under `tests/harness/` rather than `src/`, and that placement is a statement
about the platform rather than about this file.** A production entrypoint would resolve
the caller's scope through a real :class:`~core.authority.fabric.IdentityFabric` — and no
implementation of that protocol exists anywhere in this repository. 002 through 007 all
run against fakes; `fabric.py` says so in its first line. Putting a production-looking
entrypoint in `src/` that imported the test fake would make the gap invisible, which is
worse than the gap.

So what the enclave row proves is precisely this much, and no more: **the API dispatches,
Nomad places an allocation, and that allocation obtains its own credentials by presenting
its own attested identity.** Nothing is handed to it — the metadata says who the run is
for and what it may touch, and the authority comes from the attestation or not at all.
That is the part 008 owed. What a run then *does* waits on a real identity fabric.

**010 update — this module moves to `src/surfaces/dispatch/entrypoint.py` at T038a, and
not before.** The production fabric it will construct does not exist until the ceiling,
user-scope, and policy resolutions all land, because `manufacture_authority` resolves all
three from one object. Moving it earlier would force a module under `src/` to import the
fake — FR-015's violation, committed by the task meant to satisfy FR-015. The reason this
file sits here expires at integration and not at the first opportunity.
"""

from __future__ import annotations

import os
import sys

from core.audit.postgres_sink import PostgresAuditSink
from core.authority.types import AuthorityScope
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.registry.memory import ToolRegistry
from core.run import start_governed_run
from tests.harness.fake_identity_fabric import fake_identity_fabric


def main() -> int:
    correlation_id = os.environ.get("RUN_CORRELATION_ID", "").strip()
    subject_user_id = os.environ.get("RUN_SUBJECT_USER_ID", "").strip()
    tenant_id = os.environ.get("RUN_TENANT_ID", "").strip()
    definition_id = os.environ.get("RUN_DEFINITION_ID", "").strip()
    tools = frozenset(t for t in os.environ.get("RUN_REQUESTED_TOOLS", "").split(",") if t)

    missing = [
        name
        for name, value in (
            ("RUN_CORRELATION_ID", correlation_id),
            ("RUN_SUBJECT_USER_ID", subject_user_id),
            ("RUN_TENANT_ID", tenant_id),
            ("RUN_DEFINITION_ID", definition_id),
        )
        if not value
    ]
    if missing:
        # Fail loudly rather than inventing values. A run whose subject or tenant was
        # defaulted writes an audit trail naming the wrong person, or files it where
        # nobody will look for it.
        print(f"dispatch metadata missing: {', '.join(missing)}", file=sys.stderr)
        return 2

    # The allocation's own identity. No token reaches this process any other way.
    #
    # Role "agent-run", not "conformance": the Vault role is selected by the job id in the
    # workload identity's claims, and a dispatched run's id is agent-run/dispatch-*. Asking
    # for the wrong role fails as "could not obtain a database credential ... HTTPError",
    # which names the credential path rather than the identity mismatch that caused it.
    credentials = VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role="agent-run")
    audit = PostgresAuditSink(credentials=credentials)
    audit.migrate()

    run = start_governed_run(
        correlation_id=correlation_id,
        subject_user_id=subject_user_id,
        tenant_id=tenant_id,
        agent_definition_id=definition_id,
        requested_scope=AuthorityScope(tool_names=tools),
        identity_fabric=fake_identity_fabric(subject_user_id=subject_user_id, tool_names=tools),
        registry=ToolRegistry(),
        audit_sink=audit,
    )
    # The audit trail is the evidence that this happened, and the row reads it back
    # through the evidence path rather than trusting this line.
    print(f"run {run.correlation_id} started, state={run.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
