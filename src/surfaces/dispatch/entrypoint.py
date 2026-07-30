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
from typing import Any

from core.audit.postgres_sink import PostgresAuditSink
from core.audit.schema import AuditEventType
from core.authority.clock import Clock, SystemClock
from core.authority.grant import DEFAULT_MAX_RUN_DURATION, issue_grant
from core.authority.types import AuthorityScope
from core.authority.vault_fabric import SubjectScopedVaultFabric
from core.dependencies.store import PostgresDependencyStore
from core.durability.checkpoint import checkpoint_run, stop_requested
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.lease import RunLease
from core.durability.postgres import PostgresDurabilityProvider
from core.durability.resume import resume_run
from core.durability.types import CheckpointBlob, IntentRecord, ResultRecord, RunOutcome
from core.run import RunState, start_governed_run
from core.threads.context import RESULT_KEY, resolve_run_input
from core.threads.postgres import PostgresThreadStore
from surfaces.toolset import build_registry, content_pins, dependency_products

#: What a dispatched run passes a tool it was asked to invoke.
#:
#: A fixture affordance, and it always was — `invoke_tools` is the opt-in that exists so a
#: dispatched row can watch a pack tool reach a live product. What 014 added is `cas`, and the
#: reason is worth stating: `vault_write` REQUIRES it and raises without it, and a handler
#: exception does not make `outcome.allowed` false — `allowed` is `decision == "allow" and not
#: evidential_gap`, both of which hold when the body throws. So a probe call missing `cas`
#: would have every step report success while the tool errored, and the exactly-once row would
#: be counting invocations that never did anything.
_PROBE_ARGUMENTS = {"path": "conformance/probe", "cas": 0}

#: `_run_steps` met a mid-run suspension. Not an exit code — the caller files the index row
#: and then exits ZERO, because a suspension is a wait rather than a failure.
#:
#: A sentinel rather than a third return value: every existing caller reads the first element
#: as a process exit code, and a suspension that leaked out as one would be a wait presented
#: as a crash. The number is negative so it can never be mistaken for one.
_SUSPENDED = -1


def _product_action_of(registry: Any, tool_name: str) -> str:
    """The action a tool performs, or empty for unregistered/actionless tools."""
    try:
        return str(registry.resolve(tool_name).product_action or "")
    except Exception:  # noqa: BLE001 — manufacture refuses unknown tools; not our job here
        return ""


def _emit(sink: Any, *, correlation_id: str, tenant_id: str, event: Any, payload: Any) -> None:
    """Append an audit entry, letting failures propagate.

    Not swallowed. Every event this module writes is evidence for a claim a conformance row
    makes — a revival, a substituted model — and an unrecorded revival is a revival nobody
    can see, which FR-017 forbids as squarely as not bounding revivals at all.
    """
    sink.append_event(
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        event_type=event,
        payload=payload,
    )


def _step_key(blob_id: str, step: int) -> str:
    return f"{blob_id}:step-{step}"


def _tool_for_step(tools: list[str], step: int) -> str:
    """Which tool a bracketed step invokes, or empty for the fixture bracket.

    Round-robin so a run with one tool and five steps invokes that tool five times, which is
    what an interruption row needs: several real brackets to be killed *between*.
    """
    return tools[step % len(tools)] if tools else ""


def _run_steps(
    run: Any,
    *,
    durability: Any,
    blob_id: str,
    total_steps: int,
    tools: list[str],
    invoke_tools: bool,
    already_done: Any,
) -> tuple[int, list[int], list[int]]:
    """Execute the run's steps, skipping the ones re-observation says already happened.

    **Each step is the full 005 bracket**: intent, work, result, checkpoint. A fixture that
    merely slept would have no step boundaries for a stop to be observed at and no intents
    for the zero-open-intents row to count — which would make the row that exists to prevent
    vacuous stop rows produce one.

    ``already_done`` decides skipping and is the only difference between a fresh run and a
    resumed one, which is deliberate: the skip is a *predicate*, not a second code path, so a
    resumed run cannot execute a step through any route a fresh run does not. The skip
    happens **before** invocation, so nothing reaches a tool without passing the hooks
    (Principle II).

    Returns ``(exit_code, executed, skipped)``.
    """
    executed: list[int] = []
    skipped: list[int] = []

    for step in range(total_steps):
        if already_done(step):
            # Not re-executed, and not silently forgotten either — the caller reports the
            # counts, because "skipped 3 and ran 2" is what an investigator needs and a bare
            # completion cannot distinguish from "ran none of them".
            skipped.append(step)
            continue

        if (reason := stop_requested(run)) is not None:
            # Noticed at the boundary — after the previous step's bracket closed and before
            # this one opens an intent. Nothing is left open, which is the whole reason the
            # check sits here rather than in a signal handler.
            print(f"run {run.correlation_id} ending at step {step}: {reason}", flush=True)
            return 0, executed, skipped

        run.step_index = step
        tool_name = _tool_for_step(tools, step) if invoke_tools else ""

        # WHO OWNS THE BRACKET (T018), and the task's premise needed correcting here.
        #
        # The task said this loop "brackets a literal `echo` regardless of what runs, so
        # re-observation would consult the wrong observer for every real tool". The first
        # half was true and the conclusion was not: `invoke_tool` **already** brackets every
        # non-repeatable tool itself, in `core.hooks.engine`, with the real tool name and the
        # key `{run_id}:{step_index}:{tool}`. So the real bracket was never missing.
        #
        # The actual defect was a DOUBLE bracket. A step that invoked a real tool got the
        # engine's correctly-named intent *and* this loop's `"echo"` one, under different
        # keys — so a disrupted run left two open intents for one call, re-observation asked
        # the echo observer about a Vault write, and the answer was believed.
        #
        # So the fix is to stop writing the second bracket rather than to rename it. When a
        # step invokes a tool, the engine owns the bracket, and it brackets exactly when one
        # is needed: a repeatable tool has nothing to re-observe, which is what the flag
        # means. When a step invokes nothing — every fixture tool is repeatable, and
        # `invoke_tools` is off by default — this loop's own bracket is what gives a
        # multi-step run the step boundaries a stop is observed at and the open intents the
        # zero-open-intents row counts.
        if tool_name:
            from core.tools.invoke import invoke_tool

            outcome = invoke_tool(run, tool_name, _PROBE_ARGUMENTS)
            print(f"tool {tool_name}: allowed={outcome.allowed}", flush=True)
            if not outcome.allowed:
                print(f"tool {tool_name} refused: {outcome.reason_code}", file=sys.stderr)
                # A SUSPENSION IS NOT A REFUSAL, and until 014 this line could not tell them
                # apart (analyze C3). The dependency gate suspends a run whose product is
                # unreachable — `suspend_for_dependency` sets the state and names what it
                # waits on — and every such run arrived here, returned 1, and failed the
                # allocation. So the spec's own US1 narrative, the fabric blinking mid-run,
                # presented as a crashed run with no index row and nothing for the sweeper to
                # find. A wait that looks like a failure is a wait nobody comes back for.
                if run.state is RunState.SUSPENDED:
                    return _SUSPENDED, executed, skipped
                # Any intent the engine opened stays OPEN on purpose. A refused step did not
                # happen, and the record of "we were about to" is what lets a resume resolve
                # it by observation rather than by assumption.
                return 1, executed, skipped
        else:
            key = _step_key(blob_id, step)
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
                correlation_id=run.correlation_id,
                # The GRANT's id, not the credential's (research F1). See `_issue_consent`.
                grant_id=run.grant.grant_id if run.grant else "",
                step_index=step,
                written_by=getattr(run.lease, "holder_identity", "") or "entrypoint",
                outcome=None,
                # Threaded, or `save()`'s whole-row overwrite resets the bound to zero on the
                # first step after a revival — making the cap clear itself whenever any work
                # happens, and a flapping run immortal.
                resume_count=run.resume_count,
            )
        )
        executed.append(step)

    return 0, executed, skipped


def resume_dispatched_run(
    *,
    durability: Any,
    audit_sink: Any,
    registry: Any,
    identity_fabric: Any,
    clock: Clock,
    correlation_id: str,
    blob_id: str,
    tenant_id: str,
    holder_identity: str,
    observers: dict[str, Any],
    depends_on: dict[str, str],
    total_steps: int,
    tools: list[str],
    invoke_tools: bool,
    record_suspension: Any = None,
) -> int:
    """Revive a disrupted run, or record why it will not be revived.

    **The integration this whole feature exists for.** `resume_run` shipped in 005 with five
    conformance properties asserted against it and no caller in `src/` — so the platform's
    claim to durable execution rested on a function nothing invoked. This is the caller.

    It consumes the three pieces 013 left orphaned, and each was orphaned in the same way —
    built, correct, and reachable from nothing:

    - ``observers`` from the registry, so re-observation asks the tool's own observer.
    - ``depends_on`` from the loaded packs, so a suspension names the **product** the health
      checker watches rather than the tool nobody watches.
    - the resume refusal path, so a stop is recorded rather than raised past the contract.

    Every outcome is handled and an unrecognized one refuses (FR-003): a decision this
    function does not understand must not fall through to "proceed", because proceeding is
    the one response that cannot be undone.
    """
    # The checkpoint is loaded here as well as inside `resume_run`, and the duplication is
    # the point: the grant is a REQUIRED argument to `resume_run`, and the only pointer to it
    # is on the checkpoint. So the id must be read before the call that would also read it.
    checkpoint = durability.load(blob_id)
    if checkpoint is None:
        # Mirroring the library's own decision rather than inventing one. `resume_run`
        # answers STOPPED/`checkpoint_missing` for exactly this case — a missing checkpoint
        # means we cannot know what already happened, and guessing is the failure
        # re-observation exists to prevent. **Never a fresh start**: that would re-execute
        # everything the run had already done, silently.
        print(f"resume refused: checkpoint_missing for {blob_id}", file=sys.stderr)
        _emit(
            audit_sink,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            event=AuditEventType.RUN_RESUMED,
            payload={
                "run_id": blob_id,
                "attempt": 0,
                "outcome": "stopped",
                "reason": "checkpoint_missing",
                "completed_steps": 0,
                "pending_steps": 0,
            },
        )
        return 1

    grant = durability.load_grant(checkpoint.grant_id) if checkpoint.grant_id else None
    if grant is None:
        # A MISSING GRANT IS NOT "NO CONSENT REQUIRED" (FR-013). Fail-closed, and the reason
        # is recorded rather than inferred from an exit code. Before 014 this was not merely
        # unhandled but unreachable: nothing persisted a grant, so every dispatched resume
        # would have landed here.
        print(f"resume refused: grant_missing for {blob_id}", file=sys.stderr)
        _emit(
            audit_sink,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            event=AuditEventType.RUN_RESUMED,
            payload={
                "run_id": blob_id,
                "attempt": checkpoint.resume_count,
                "outcome": "stopped",
                "reason": "grant_missing",
                "completed_steps": 0,
                "pending_steps": 0,
            },
        )
        return 1

    decision = resume_run(
        durability,
        blob_id=blob_id,
        run_id=blob_id,
        grant=grant,
        holder_identity=holder_identity,
        identity_fabric=identity_fabric,
        clock=clock,
        observers=observers,
        correlation_id=correlation_id,
        depends_on=depends_on,
    )

    outcome_word = {
        RunState.ACTIVE: "continued",
        RunState.STOPPED: "stopped",
        RunState.COMPLETED: "stopped",
        RunState.SUSPENDED: "suspended",
    }.get(decision.state)
    # A SUSPENDED decision carries both an `awaiting` and a `stop_reason` — the product and
    # the diagnostic ("unobservable_step:terraform_apply#1"). The trail's `reason` is the
    # PRODUCT, because the question a suspended run raises is "what is it waiting on" and the
    # answer has to be the name the sweeper matches recoveries against. The diagnostic goes
    # to the allocation log, where whoever is debugging the observer is already looking.
    reason = decision.awaiting if decision.state is RunState.SUSPENDED else decision.stop_reason
    if outcome_word is None:
        # FR-003: an unhandled outcome must not default to proceeding. A state this function
        # does not recognise is a state whose meaning it cannot honour, and the safe reading
        # of "I do not know what this means" is never "carry on executing".
        print(f"resume refused: unhandled decision state {decision.state}", file=sys.stderr)
        return 1

    # BEFORE ANY PENDING STEP, so an investigator reading in order sees the revival before
    # its consequences (FR-017). Emitted for every outcome, including the ones that do no
    # work — a run that was revived and immediately stopped is exactly the event someone is
    # looking for when they ask why a run never finished.
    _emit(
        audit_sink,
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        event=AuditEventType.RUN_RESUMED,
        payload={
            "run_id": blob_id,
            "attempt": decision.resume_count,
            "outcome": outcome_word,
            "reason": reason or "",
            # Counts, not contents. Enough to see "it skipped 3 and ran 2" without the trail
            # carrying step payloads.
            "completed_steps": len(decision.completed_steps),
            "pending_steps": len(decision.pending_steps),
        },
    )

    # The loop 013's plan documented for the resume caller, closed. `resume_run` holds
    # neither a sink nor a tenant, so it carries the fallback back on the decision and this
    # caller records it — for every outcome, which is why it is emitted here rather than left
    # to `start_governed_run`: a resume that falls back and then suspends never reaches that
    # function, and the substitution would go unrecorded in exactly that case.
    if decision.matrix_fallback is not None:
        _emit(
            audit_sink,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            event=AuditEventType.MATRIX_FALLBACK,
            payload=decision.matrix_fallback.as_payload(run_id=blob_id),
        )

    if decision.state is RunState.SUSPENDED:
        awaiting = decision.awaiting or ""
        print(
            f"run {blob_id} suspended awaiting {awaiting} ({decision.stop_reason})",
            flush=True,
        )
        _file_suspension(
            record_suspension,
            run_id=blob_id,
            correlation_id=correlation_id,
            awaiting=awaiting,
            step_index=checkpoint.step_index,
            grant=grant,
            tenant_id=tenant_id,
            tools=tools,
            total_steps=total_steps,
            invoke_tools=invoke_tools,
        )
        durability.save(
            checkpoint.model_copy(
                update={
                    "written_by": holder_identity,
                    "resume_count": decision.resume_count,
                }
            )
        )
        # EXIT ZERO. A suspension is a wait, not a failure: the sweeper revives it when the
        # dependency recovers, and a failed allocation would present the wait as a crash.
        return 0

    if decision.state.is_terminal():
        reason = decision.stop_reason or "stopped"
        print(f"run {blob_id} stopped on resume: {reason}", flush=True)
        durability.save(
            checkpoint.model_copy(
                update={
                    "written_by": holder_identity,
                    "resume_count": decision.resume_count,
                    "outcome": RunOutcome(state=RunState.STOPPED.value, stop_reason=reason),
                }
            )
        )
        # EXIT ZERO. A bound is an ending, not a failure — expired consent and an exhausted
        # revival budget are the platform working. Exiting non-zero would make every bound
        # look like a crash to whoever reads allocation states.
        return 0

    # ACTIVE. The run continues, under authority manufactured by this allocation from its own
    # attested identity — passed to `start_governed_run` rather than re-derived, so the
    # credential the run executes under is the one resume vetted (ADR-0048).
    run = start_governed_run(
        correlation_id=correlation_id,
        subject_user_id=grant.subject_user_id,
        tenant_id=tenant_id,
        agent_definition_id=grant.agent_definition_id,
        requested_scope=grant.requested_scope,
        identity_fabric=identity_fabric,
        registry=registry,
        audit_sink=audit_sink,
        clock=clock,
        manufactured=decision.authority,
    )
    run.run_id = blob_id
    run.durability = durability
    run.grant = grant
    run.resume_count = decision.resume_count
    # The claim `resume_run` already made, in this instance's hands so every checkpoint and
    # every tool call is fenced against the allocation this one superseded (FR-009).
    run.lease = RunLease(durability, run_id=blob_id, holder_identity=holder_identity)

    # WHAT ALREADY HAPPENED, and the two halves are different questions.
    #
    # `completed_steps` are open intents that re-observation found had taken effect: their
    # work landed but their bracket never closed, so nothing else can tell. A step at or
    # below the checkpoint's mark closed its bracket and is done — unless re-observation
    # says otherwise, which is what `pending` overrides.
    completed = {intent.step_index for intent in decision.completed_steps}
    pending = {intent.step_index for intent in decision.pending_steps}
    resume_from = checkpoint.step_index + 1

    def already_done(step: int) -> bool:
        if step in pending:
            return False
        return step in completed or step < resume_from

    code, executed, skipped = _run_steps(
        run,
        durability=durability,
        blob_id=blob_id,
        total_steps=total_steps,
        tools=tools,
        invoke_tools=invoke_tools,
        already_done=already_done,
    )
    print(f"resumed {blob_id}: executed={executed} skipped={skipped}", flush=True)
    if code == _SUSPENDED:
        # A revived run that suspended AGAIN mid-flight — the flapping case, and the one the
        # attempt cap exists to bound. Indexed and exited zero like any other wait; the next
        # recovery revives it, and the revival after the cap stops it terminally.
        return _suspend_mid_run(
            run,
            durability=durability,
            blob_id=blob_id,
            record_suspension=record_suspension,
            grant=grant,
            tenant_id=tenant_id,
            tools=tools,
            total_steps=total_steps,
            invoke_tools=invoke_tools,
        )
    if code != 0:
        return code

    durability.save(
        CheckpointBlob(
            blob_id=blob_id,
            payload={**checkpoint.payload, RESULT_KEY: {"resumed": True, "steps": executed}},
            correlation_id=correlation_id,
            grant_id=grant.grant_id,
            step_index=max(executed) if executed else checkpoint.step_index,
            written_by=holder_identity,
            outcome=RunOutcome(state=RunState.COMPLETED.value, stop_reason=None),
            resume_count=decision.resume_count,
        )
    )
    return 0


def _suspend_mid_run(
    run: Any,
    *,
    durability: Any,
    blob_id: str,
    record_suspension: Any,
    grant: Any,
    tenant_id: str,
    tools: list[str],
    total_steps: int,
    invoke_tools: bool,
) -> int:
    """File a mid-run suspension and end the allocation cleanly.

    The second writer of the suspended-run index, and after 014 there are exactly two — this
    one and the resume-time arm. Both are in this module because both are the caller that owns
    the run's durability, which is the division `core.hooks.suspension` describes: the hook
    marks the state, the owner persists it and indexes it.

    The checkpoint carries the suspended state and **no terminal outcome** — a suspended run
    must stay resumable, and a terminal record would make `resume_run` refuse it and the
    sweeper drop it as stale.
    """
    awaiting = str(run.stop_reason or "").removeprefix("awaiting:") or "unknown"
    print(f"run {blob_id} suspended mid-run awaiting {awaiting}", flush=True)
    _file_suspension(
        record_suspension,
        run_id=blob_id,
        correlation_id=run.correlation_id,
        awaiting=awaiting,
        step_index=run.step_index,
        grant=grant,
        tenant_id=tenant_id,
        tools=tools,
        total_steps=total_steps,
        invoke_tools=invoke_tools,
    )
    checkpoint_run(run, payload={"step": run.step_index})
    # Zero. The run is waiting, and the sweeper is what ends the wait.
    return 0


def _file_suspension(
    record_suspension: Any,
    *,
    run_id: str,
    correlation_id: str,
    awaiting: str,
    step_index: int,
    grant: Any,
    tenant_id: str,
    tools: list[str],
    total_steps: int,
    invoke_tools: bool,
) -> None:
    """Index the suspension so the sweeper can find it.

    Carries what the run needs to be **itself** when revived — roles are absent here because
    this process holds the ones it was dispatched with, and they are passed by the caller
    that read them from the environment. Nothing here grants anything.

    A suspension that is not indexed is a run the sweeper never finds: it would sit
    suspended forever, which is precisely the hang ADR-0049 removed a human to avoid,
    produced by the mechanism meant to prevent it. So a failure to index is loud.
    """
    if record_suspension is None:
        return
    record_suspension(
        run_id=run_id,
        correlation_id=correlation_id,
        awaiting=awaiting,
        step_index=step_index,
        subject_user_id=grant.subject_user_id,
        tenant_id=tenant_id,
        agent_definition_id=grant.agent_definition_id,
        packs=frozenset(p for p in os.environ.get("RUN_PACKS", "").split(",") if p),
        subject_roles=frozenset(r for r in os.environ.get("RUN_SUBJECT_ROLES", "").split(",") if r),
        steps=total_steps or None,
        invoke_tools=invoke_tools,
    )


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

    fabric = SubjectScopedVaultFabric(
        roles=roles,
        credentials=credentials,
        known_tools=registry.tool_names(),
        known_actions=registry.product_actions(),
    )
    blob_id = os.environ.get("RUN_ID", "").strip() or correlation_id
    steps = int(os.environ.get("RUN_STEPS", "0") or 0)
    invoke_tools = os.environ.get("RUN_INVOKE_TOOLS", "").strip() == "1"
    # This allocation's identity, for the lease. Nomad supplies it; a blank one would compare
    # equal to another blank one and silently disable fencing, so it falls back to something
    # distinct rather than to the empty string.
    holder_identity = os.environ.get("NOMAD_ALLOC_ID", "").strip() or f"entrypoint-{os.getpid()}"

    # THE DISCRIMINATOR (D1). A resume is declared by the dispatcher, never inferred here —
    # see `NomadDispatcher.dispatch`'s comment for why both candidate inferences turn a
    # coincidence into a resume. A fresh dispatch carrying a used run_id stays a fresh
    # dispatch, which is the id-collision edge case resolved by construction.
    if os.environ.get("RUN_RESUME", "").strip() == "1":
        durability = PostgresDurabilityProvider(credentials=credentials)
        store = PostgresDependencyStore(credentials=credentials)
        return resume_dispatched_run(
            durability=durability,
            audit_sink=audit,
            registry=registry,
            identity_fabric=fabric,
            clock=SystemClock(),
            correlation_id=correlation_id,
            blob_id=blob_id,
            tenant_id=tenant_id,
            holder_identity=holder_identity,
            # The three orphans 013 built and nothing consumed.
            observers=registry.observers(),
            depends_on=dependency_products(_loaded_packs),
            total_steps=steps,
            tools=sorted(tools),
            invoke_tools=invoke_tools,
            record_suspension=store.record_suspension,
        )

    run = start_governed_run(
        correlation_id=correlation_id,
        subject_user_id=subject_user_id,
        tenant_id=tenant_id,
        agent_definition_id=definition_id,
        # Tools AND the product actions those tools perform, both derived from the
        # registry. The intersection algebra is strict — an empty requested action set
        # yields an empty effective action set — so a request naming only tools
        # manufactures authority that can hold a product tool and never invoke it:
        # the authority hook refuses `authority_insufficient` at the first call. Nothing
        # dispatched ever invoked a product tool before 013's opt-in step, which is why
        # five features' worth of dispatched rows never met this. Unknown names skip —
        # manufacture refuses them on the tool set, which is the right refusal.
        requested_scope=AuthorityScope(
            tool_names=tools,
            product_actions=frozenset(
                action
                for name in tools
                for action in [_product_action_of(registry, name)]
                if action
            ),
        ),
        # The production fabric, resolving every term from the control-plane trust fabric
        # under this allocation's own identity. What this line used to say is the whole
        # reason the module lived under `tests/`.
        identity_fabric=fabric,
        registry=registry,
        audit_sink=audit,
        content_pins=content_pins(_loaded_packs),
    )
    # The audit trail is the evidence that this happened, and the row reads it back
    # through the evidence path rather than trusting this line.
    print(f"run {run.correlation_id} started, state={run.state}")

    # DURABLE CONSENT (research F1, T012). ADR-0026 said a checkpoint references consent by
    # `grant_id`; until 014 the dispatched path issued no grant at all, and wrote
    # `run.authority.credential_id` into that column — the 15-minute task credential's id in
    # the column meant for hours-long consent, pointing at something stored nowhere. So the
    # reference did not merely dangle, it named the wrong kind of thing.
    #
    # On the duration: `DEFAULT_MAX_RUN_DURATION`, named honestly. An earlier draft of this
    # said "the definition's ceiling", and no record anywhere carries a per-definition maximum
    # run duration — `issue_grant`'s `max_run_duration` is a defaulted parameter, not a
    # resolved fact. The platform default is the real source today; a per-definition maximum
    # is a future record, and when it exists it is read here.
    grant = issue_grant(
        subject_user_id=subject_user_id,
        agent_definition_id=definition_id,
        requested_scope=run.authority.effective,
        clock=run.clock,
        duration=DEFAULT_MAX_RUN_DURATION,
        correlation_id=correlation_id,
    )
    durability = PostgresDurabilityProvider(credentials=credentials)
    durability.save_grant(grant)
    run.grant = grant
    run.run_id = blob_id
    run.durability = durability

    # 013, opt-in: invoke each requested tool once through the real pipeline. This is what
    # makes "a pack tool reaches a live product through the same hooks as any other tool"
    # a demonstrated fact rather than a structural argument — the allocation holds the
    # attested identity the tool's handler manufactures credentials from, which no host
    # process has. Opt-in because every pre-013 dispatched row asserts a trail this
    # appends TOOL_OUTCOME events to.
    #
    # Only when this run takes NO steps. With steps, the invocation moves inside the bracket
    # (T018) so the intent names the tool that actually ran — this loop and that one would
    # otherwise invoke everything twice.
    if invoke_tools and steps == 0:
        from core.tools.invoke import invoke_tool

        for tool_name in sorted(tools):
            outcome = invoke_tool(run, tool_name, _PROBE_ARGUMENTS)
            print(f"tool {tool_name}: allowed={outcome.allowed}", flush=True)
            if not outcome.allowed:
                # A refused invoke fails the allocation, so the dispatch row's
                # "complete" assertion means every requested tool actually ran.
                print(f"tool {tool_name} refused: {outcome.reason_code}", file=sys.stderr)
                return 1

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
    if steps > 0:
        # Nothing is already done on a fresh dispatch, and saying so as a predicate rather
        # than as a second loop is what keeps the resumed path from having an execution route
        # of its own.
        code, _, _ = _run_steps(
            run,
            durability=durability,
            blob_id=blob_id,
            total_steps=steps,
            tools=sorted(tools),
            invoke_tools=invoke_tools,
            already_done=lambda _step: False,
        )
        if code == _SUSPENDED:
            # A FRESH run can suspend too, and this arm is the more common one in production:
            # the fabric blinks or a product goes unreachable partway through work that had
            # never been disrupted. Same index row, same exit zero — the sweeper does not care
            # which arm filed it, and the run must not reach the terminal COMPLETED checkpoint
            # below, because it has not completed.
            return _suspend_mid_run(
                run,
                durability=durability,
                blob_id=blob_id,
                record_suspension=PostgresDependencyStore(
                    credentials=credentials
                ).record_suspension,
                grant=grant,
                tenant_id=tenant_id,
                tools=sorted(tools),
                total_steps=steps,
                invoke_tools=invoke_tools,
            )
        if code != 0:
            return code

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
        run_id=blob_id,
        store=thread_store,
        durability=durability,
    )

    # A terminal checkpoint, so the run has an ending anyone can read.
    #
    # Before 011 this entrypoint started a run, printed, and exited — leaving no terminal
    # record at all, so every API-started run read as *not finished* forever and only one
    # arm of the three-way result disposition was reachable. The result goes under the
    # reserved key in the same write, because the terminal checkpoint is the one place a
    # run's ending is recorded and a second place would eventually disagree with it.
    durability.save(
        CheckpointBlob(
            blob_id=blob_id,
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
            # THE GRANT's id (research F1). This said `run.authority.credential_id` for nine
            # features — a 15-minute task credential in the column ADR-0026 defined as
            # referencing durable consent, and stored nowhere at all. A resume loading consent
            # by this value would have found nothing and refused every revival, so the store
            # existing and this line being right are one change, not two.
            grant_id=grant.grant_id,
            step_index=max(steps - 1, 0),
            written_by="entrypoint",
            outcome=RunOutcome(state=RunState.COMPLETED.value, stop_reason=None),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
