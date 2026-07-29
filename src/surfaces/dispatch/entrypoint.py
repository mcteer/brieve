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
from datetime import UTC, datetime

from core.audit.postgres_sink import PostgresAuditSink
from core.authority.types import AuthorityScope
from core.authority.vault_fabric import SubjectScopedVaultFabric
from core.durability.checkpoint import stop_requested
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.postgres import PostgresDurabilityProvider
from core.durability.types import CheckpointBlob, IntentRecord, ResultRecord, RunOutcome
from core.run import RunState, start_governed_run
from core.threads.context import RESULT_KEY, resolve_run_input
from core.threads.postgres import PostgresThreadStore
from surfaces.toolset import build_registry, content_pins


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

    # The toolset. **This is the line capability packs were signposted to replace**, and
    # 013 is the feature that replaced it — the comment that stood here said "when they
    # land, this is the line they replace", and it was right about where and about why.
    #
    # The fixture tools stay, for definitions that name no pack: 008-012's rows are built
    # on them, and removing them would break a dozen lanes to prove a point about packs.
    # Packs named by RUN_PACKS are loaded alongside, and a definition reaches only what it
    # names.
    registry, _loaded_packs = build_registry(
        packs=[p for p in os.environ.get("RUN_PACKS", "").split(",") if p]
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
        content_pins=content_pins(_loaded_packs),
    )
    # The audit trail is the evidence that this happened, and the row reads it back
    # through the evidence path rather than trusting this line.
    print(f"run {run.correlation_id} started, state={run.state}")

    # Optional multi-step mode, for rows that need a run still running when something
    # happens to it. Every existing fixture completes immediately, so a stop row against
    # one passes whether the stop works or not — 010's T009 lesson in this feature's
    # clothes.
    #
    # **Each step runs the full 005 bracket**: intent, work, result, checkpoint. A fixture
    # that merely slept would have no step boundaries for a stop to be observed at and no
    # intents for the zero-open-intents row to count, which would make the row that exists
    # to prevent vacuous stop rows produce one.
    # No artificial delay. Each step is three durable writes — intent, result, checkpoint
    # — so a multi-step run takes real time doing real work, and the duration a stop row
    # needs comes from the bracket rather than from a sleep.
    #
    # That is not only tidier. `time.sleep` here would be a test affordance living in
    # production code, which is precisely what 010 spent a user story removing from the
    # identity protocol — and `tests/unit/test_surface_never_pauses.py` caught it, which
    # is the check doing its job rather than obstructing.
    steps = int(os.environ.get("RUN_STEPS", "0") or 0)
    if steps > 0:
        durability = PostgresDurabilityProvider(credentials=credentials)
        run.durability = durability
        blob_id = os.environ.get("RUN_ID", "").strip() or correlation_id
        for step in range(steps):
            if (reason := stop_requested(run)) is not None:
                # Noticed at the boundary — after the previous step's bracket closed and
                # before this one opens an intent. Nothing is left open, which is the whole
                # reason the check sits here rather than in a signal handler.
                print(f"run {correlation_id} ending at step {step}: {reason}", flush=True)
                return 0

            key = f"{blob_id}:step-{step}"
            durability.record_intent(
                IntentRecord(
                    run_id=blob_id,
                    idempotency_key=key,
                    step_index=step,
                    tool_name="echo",
                    recorded_at=datetime.now(UTC),
                )
            )
            durability.record_result(
                ResultRecord(
                    run_id=blob_id,
                    idempotency_key=key,
                    step_index=step,
                    recorded_at=datetime.now(UTC),
                )
            )
            durability.save(
                CheckpointBlob(
                    blob_id=blob_id,
                    payload={"step": step},
                    correlation_id=correlation_id,
                    grant_id=getattr(run.authority, "credential_id", ""),
                    step_index=step,
                    written_by="entrypoint",
                    outcome=None,
                )
            )

    # What this run was asked to do, and what it was given to work from.
    #
    # Read from durable state rather than from the environment, and that is the point: a
    # person's free text must not enter a jobspec, where it would be visible to anyone with
    # scheduler access and outside the tenant-scoped read path. `resolve_run_input` reads
    # the message and turns each carried run id into the bytes that run's result was
    # recorded as — reading the record rather than a copy that travelled, which is what
    # makes "byte-identical" true by construction.
    #
    # None means this run was started outside a thread. Not an error: those runs behave
    # exactly as they did before this feature existed.
    thread_store = PostgresThreadStore(credentials=credentials)
    resolved = resolve_run_input(
        run_id=os.environ.get("RUN_ID", "").strip() or correlation_id,
        store=thread_store,
        durability=PostgresDurabilityProvider(credentials=credentials),
    )

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
            payload={
                RESULT_KEY: {
                    "started": True,
                    "tools": sorted(tools),
                    # Echoed so a row can assert what the run actually received, rather
                    # than asserting that the resolver returned something and hoping the
                    # run read it.
                    "message": resolved.message if resolved else None,
                    "received_context": (
                        [{"run_id": rid, "result": body} for rid, body in resolved.context]
                        if resolved
                        else []
                    ),
                }
            },
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
