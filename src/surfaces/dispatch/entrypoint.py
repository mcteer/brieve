# SPDX-License-Identifier: Apache-2.0
"""The task body a dispatched run executes — a real entrypoint, in `src/`.

**This module lived under `tests/harness/` until 010, and why is the interesting part.**
008 built the dispatch path and had nowhere to put the thing it dispatched: a production
entrypoint must resolve the caller's scope through an identity fabric, and the only
implementation was a test double. The choice was between a file in the wrong directory and
a module under `src/` importing from `tests/`, and 008 correctly took the first — putting a
production-looking entrypoint in `src/` that imported the fake would have hidden the gap
rather than recorded it.

010 built the fabric, so the reason expired and the file moved. That is the whole story of
this module, and it is worth keeping because the shape recurs: a seam with one
implementation looks finished until something else needs it.

Everything it constructs comes from the allocation's own attested identity. No token, no
password, and no fallback reaches this process any other way — which is what makes a
resumed run re-authenticate rather than replay (ADR-0048).
"""

from __future__ import annotations

import os
import sys

from core.audit.postgres_sink import PostgresAuditSink
from core.authority.types import AuthorityScope
from core.authority.vault_fabric import SubjectScopedVaultFabric
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.postgres import PostgresDurabilityProvider
from core.durability.types import CheckpointBlob, RunOutcome
from core.registry.memory import ToolRegistry
from core.run import RunState, start_governed_run
from surfaces.api.runs import RESULT_KEY


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

    # The reference toolset. An empty registry knows no tools, so a ceiling naming any of
    # them would refuse `unknown_ceiling_entry` — correct behaviour, and useless as an
    # entrypoint. 008 could leave this empty because it only proved a run STARTS; a run
    # that resolves a real ceiling has to know what the ceiling is talking about.
    #
    # Hardcoded here because the real toolset arrives with capability packs, which are a
    # later feature. When they land, this is the line they replace.
    registry = ToolRegistry()
    registry.register("echo", lambda _arguments: {"ok": "ran"})
    # Product-tagged, because the ceiling records name product actions and a ceiling may
    # only name things the platform can do. The registry is the source of that truth, so
    # a toolset declaring no product actions makes every product-shaped ceiling refuse
    # `unknown_ceiling_entry` — which is correct, precise, and impossible to satisfy.
    registry.register(
        "plan",
        lambda _arguments: {"ok": "planned"},
        product_mode="federate",
        product="workspace",
        product_action="product.workspace.read",
    )
    registry.register(
        "apply",
        lambda _arguments: {"ok": "applied"},
        product_mode="federate",
        product="workspace",
        product_action="product.workspace.write",
    )

    # The roles the dispatching surface already resolved from this subject's verified
    # claims. Passed rather than re-derived: a second derivation is a second answer to
    # "who is this", and the two would diverge exactly when it mattered.
    roles = [r for r in os.environ.get("RUN_SUBJECT_ROLES", "").split(",") if r]

    run = start_governed_run(
        correlation_id=correlation_id,
        subject_user_id=subject_user_id,
        tenant_id=tenant_id,
        agent_definition_id=definition_id,
        requested_scope=AuthorityScope(tool_names=tools),
        # The production fabric, resolving every term from the control-plane trust fabric
        # under this allocation's own identity. What this line used to say is the whole
        # reason the module lived under `tests/`.
        identity_fabric=SubjectScopedVaultFabric(
            roles=roles,
            credentials=credentials,
            known_tools=registry.tool_names(),
            known_actions=registry.product_actions(),
        ),
        registry=registry,
        audit_sink=audit,
    )
    # The audit trail is the evidence that this happened, and the row reads it back
    # through the evidence path rather than trusting this line.
    print(f"run {run.correlation_id} started, state={run.state}")

    # A terminal checkpoint, so the run has an ending anyone can read.
    #
    # Before 011 this entrypoint started a run, printed, and exited — leaving no terminal
    # record at all, so every API-started run read as *not finished* forever and only one
    # arm of the three-way result disposition was reachable. The result goes under the
    # reserved key in the same write, because the terminal checkpoint is the one place a
    # run's ending is recorded and a second place would eventually disagree with it.
    durability = PostgresDurabilityProvider(credentials=credentials)
    durability.save(
        CheckpointBlob(
            blob_id=os.environ.get("RUN_ID", "").strip() or correlation_id,
            payload={RESULT_KEY: {"started": True, "tools": sorted(tools)}},
            correlation_id=correlation_id,
            grant_id=getattr(run.authority, "credential_id", ""),
            step_index=0,
            written_by="entrypoint",
            outcome=RunOutcome(state=RunState.COMPLETED.value, stop_reason=None),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
