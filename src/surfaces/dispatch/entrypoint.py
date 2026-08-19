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
from pathlib import Path
from typing import Any

from adapters.model_chooser import FIXTURE_PROVIDER, build_chooser
from core.audit.postgres_sink import PostgresAuditSink
from core.audit.schema import AuditEventType
from core.authoring.artifact import AuthoredArtifact
from core.authoring.credential import AuthoringCredentials
from core.authoring.progress import (
    PROGRESS_KEY,
    PhaseName,
    PhaseStatus,
    ProposeProgress,
    advance,
    complete,
    fail,
    initial_progress,
    phase_to_fail,
)
from core.authoring.proposal import branch_for, compose, files_from_write_plan
from core.authoring.publish import ProposalObserver, ProposalPublisher
from core.authoring.retention import scrub_authoring_requests
from core.authoring.tool import AUTHOR_FILE, OPEN_PROPOSAL, READ_SUBJECT, WRITE_ROLE
from core.authoring.workspace import Trees
from core.authority.clock import Clock, SystemClock
from core.authority.errors import AuthorityRefuseError, ResolutionRefused
from core.authority.grant import DEFAULT_MAX_RUN_DURATION, issue_grant
from core.authority.manufacture import manufacture_authority
from core.authority.matrix import parse_matrix_record
from core.authority.model_credential import BrokeredModelCredential
from core.authority.types import AuthorityScope
from core.authority.vault_fabric import SubjectScopedVaultFabric
from core.choice import (
    CHOICE_ROLE,
    Answer,
    ChoiceOutcome,
    ChooserUnavailable,
    record_unconsulted_step,
    resolve_bound_model,
    resolve_step_tool,
)
from core.dependencies.store import PostgresDependencyStore
from core.durability.checkpoint import checkpoint_run, stop_requested
from core.durability.credentials import NomadWorkloadIdentity, VaultDatabaseCredentials
from core.durability.lease import RunLease
from core.durability.postgres import PostgresDurabilityProvider
from core.durability.resume import resume_run
from core.durability.types import CheckpointBlob, IntentRecord, ResultRecord, RunOutcome
from core.observation.record import observe_effects
from core.run import RunState, start_governed_run
from core.threads.context import RESULT_KEY, resolve_run_input
from core.threads.postgres import PostgresThreadStore
from core.tools.invoke import invoke_tool
from surfaces.dispatch.authoring import (
    ANALYZER,
    PROPOSAL_PAYLOAD_KEY,
    PROPOSER,
    authoring_registry_for,
    authoring_role,
    proposal_from_payload,
    proposal_payload,
    trees_for,
)
from surfaces.dispatch.terraform_authoring import quality_judge_may_publish, reviewer_copy
from surfaces.toolset import (
    AUTHORING_VOCABULARY,
    build_registry,
    content_pins,
    dependency_products,
)

#: Where Postgres answers from inside a bridge-mode allocation (same name as mcp/served.py).
_DB_HOST_ENV = "HARNESS_DB_HOST"


def _db_host() -> str:
    """Host for Postgres collaborators. Loopback is correct only in host-network jobs."""
    return os.environ.get(_DB_HOST_ENV, "").strip() or "127.0.0.1"


#: What every pre-040 invoke ran with, kept for exactly two jobs — neither on the ask path.
#:
#: Until 040 this constant was passed as the arguments for EVERY tool a model named — "a
#: fixture affordance, and it always was" — so a model could choose the verb and never the
#: object. The ask path no longer touches it: the model's answer carries the arguments now.
#:
#: Job one: the pre-040 intent (research R4). An intent whose ``arguments`` is None was
#: recorded before the column existed, and its FIRST attempt ran with these values — so its
#: revival must supply them, byte for byte. Reviving with ``{}`` would repeat a *different*
#: act than the one attempted, which is the defect even when the different act is emptier.
#:
#: Job two: the zero-step probe loop below, which invokes each requested tool once with NO
#: model consulted — there, the platform supplying the arguments is the point, because the
#: row is proving tool reach, not model direction. That loop is outside 040's subject: the
#: spec governs what a MODEL may say, and no model says anything on that path.
#:
#: (`cas` is here because `vault_write` REQUIRES it — 014's lesson, kept with the values.)
_LEGACY_PRE_040_ARGUMENTS = {"path": "conformance/probe", "cas": 0}

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


def _current_progress(run: Any) -> ProposeProgress:
    live = getattr(run, "propose_progress", None)
    if isinstance(live, ProposeProgress):
        return live
    parsed = ProposeProgress.from_payload(live if isinstance(live, dict) else None)
    return parsed or initial_progress()


def _phase_status(progress: ProposeProgress, name: PhaseName) -> PhaseStatus:
    for phase in progress.phases:
        if phase.name == name:
            return phase.status
    return PhaseStatus.PENDING


def _payload_with_progress(payload: dict[str, Any], run: Any) -> dict[str, Any]:
    """Keep Build phases on every blob write — finish-path saves replace the payload."""
    out = dict(payload)
    live = getattr(run, "propose_progress", None)
    if live is None:
        return out
    data = live if isinstance(live, dict) else live.to_payload()
    out[PROGRESS_KEY] = data
    result = out.get(RESULT_KEY)
    if isinstance(result, dict):
        out[RESULT_KEY] = {**result, PROGRESS_KEY: data}
    return out


def _mark_research_active(run: Any) -> None:
    progress = _current_progress(run)
    if _phase_status(progress, PhaseName.RESEARCH) == PhaseStatus.PENDING:
        run.propose_progress = advance(progress, into=PhaseName.RESEARCH)
    else:
        run.propose_progress = progress


def _run_write_plan(
    run: Any,
    *,
    chooser: Any,
    task: str,
    consulted: tuple[str, ...],
    author: Any,
) -> str | None:
    """Research is done: record what will be written, then open Write.

    This is the user-visible Plan phase — an outline of the change, not a product
    plan oracle. ``author_file`` stays refused until this returns.
    """
    progress = _current_progress(run)
    if _phase_status(progress, PhaseName.RESEARCH) == PhaseStatus.ACTIVE:
        progress = complete(progress, phase=PhaseName.RESEARCH)
    if _phase_status(progress, PhaseName.PLAN) != PhaseStatus.ACTIVE:
        progress = advance(progress, into=PhaseName.PLAN)
    run.propose_progress = progress
    checkpoint_run(run, payload=_payload_with_progress({}, run))
    print(f"run {run.correlation_id}: planning what to write", flush=True)
    try:
        drafter = getattr(chooser, "draft_write_plan", None)
        text = (
            drafter(task=task, consulted=consulted, max_files=_MAX_AUTHOR_FILES)
            if callable(drafter)
            else "Write the files required by the task."
        )
    except Exception as exc:  # noqa: BLE001 — plan failure is a phase failure, not a crash
        reason = f"could not plan the change ({type(exc).__name__})"
        _fail_current_phase(run, reason)
        checkpoint_run(run, payload=_payload_with_progress({}, run))
        return reason
    outline = (text or "").strip()
    if not outline:
        reason = "the write plan was empty"
        _fail_current_phase(run, reason)
        checkpoint_run(run, payload=_payload_with_progress({}, run))
        return reason
    run.write_plan = outline
    run.propose_progress = complete(_current_progress(run), phase=PhaseName.PLAN)
    # Write is the next work. Activate it here so a later EMPTY/deny cannot rewind
    # Research — ``current`` would otherwise be None and fail() defaulted to Research.
    run.propose_progress = advance(_current_progress(run), into=PhaseName.WRITE)
    if author is not None:
        author.plan_ready = True
    checkpoint_run(run, payload=_payload_with_progress({}, run))
    print(f"run {run.correlation_id}: write plan recorded", flush=True)
    return None


#: After the write plan exists, a few more reads are allowed; then only ``author_file``.
#: Without this cap a live write model burns the whole step budget on research and Judge
#: never sees a file.
_POST_PLAN_READ_BUDGET = 2
#: A live write model will keep emitting files until the step budget dies. Bound it so
#: Write can finish and Judge can run in a single Build.
_MAX_AUTHOR_FILES = 6


def _authoring_step_tools(
    tools: list[str],
    *,
    planned: bool,
    post_plan_reads: int,
) -> list[str]:
    """Narrow the chooser's permitted set as authoring phases complete.

    Research: ``read_subject`` only. After the plan: both tools for a short read budget,
    then ``author_file`` only. Narrowing, never widening.
    """
    if not planned:
        return [name for name in tools if name == READ_SUBJECT] or tools
    if post_plan_reads >= _POST_PLAN_READ_BUDGET:
        return [name for name in tools if name == AUTHOR_FILE] or tools
    return list(tools)


def _remaining_planned(*, write_plan: str, authored: dict[str, str] | None) -> list[str]:
    """Planned paths that have not been authored yet (exact path or matching basename)."""
    have = set((authored or {}).keys())
    have_base = {p.rsplit("/", 1)[-1] for p in have}
    remaining: list[str] = []
    for path in files_from_write_plan(write_plan):
        base = path.rsplit("/", 1)[-1]
        if path in have or base in have_base:
            continue
        remaining.append(path)
    return remaining


def _write_locked_task(
    task: str,
    *,
    write_plan: str,
    authored: dict[str, str] | None,
) -> str:
    """Steer the write-cell model at remaining planned paths, not a second copy of one file."""
    have = sorted((authored or {}).keys())
    remaining = _remaining_planned(write_plan=write_plan, authored=authored)
    authored_txt = ", ".join(have) or "(none yet)"
    plan_txt = (write_plan or "").strip() or "(none recorded)"
    if remaining:
        still = ", ".join(remaining)
        return (
            f"{task}\n\nWrite plan: {plan_txt}\n"
            f"Already authored: {authored_txt}\n"
            f"Still to write: {still}\n"
            "You must call author_file for one path that is still to write, with a full "
            "file body. Do not write a second copy of an already-authored module under a "
            "different folder. Do not overwrite an already-authored path unless its body "
            "is incomplete. Answering NONE is not completion — it abandons the pull request."
        )
    return (
        f"{task}\n\nWrite plan: {plan_txt}\n"
        f"Already authored: {authored_txt}\n"
        "The planned files are written. Do not add duplicate copies under other folders. "
        "If you have nothing new, answering NONE ends Write and the run proceeds to Judge."
    )


def _empty_after_plan(
    *,
    planned: bool,
    authored: int,
    outcome: Any,
    remaining: int = 0,
) -> str:
    """What an empty/exhausted choice means once a write plan exists.

    ``done`` — files exist, remaining planned paths are empty, and the model named nothing.
    ``retry`` — nothing authored yet, or planned paths are still missing (NONE is not a Build end).
    ``stop`` — not an authoring write loop, or a real bound exhaustion after files exist.
    """
    if not planned:
        return "stop"
    name = str(outcome)
    empty = name == str(ChoiceOutcome.EMPTY)
    exhausted = name == str(ChoiceOutcome.EXHAUSTED)
    if authored > 0 and empty:
        if remaining > 0:
            return "retry"
        return "done"
    if authored == 0 and (empty or exhausted):
        return "retry"
    return "stop"


def _mark_write_active(run: Any) -> None:
    progress = _current_progress(run)
    if _phase_status(progress, PhaseName.WRITE) in (PhaseStatus.ACTIVE, PhaseStatus.COMPLETED):
        return
    run.propose_progress = advance(progress, into=PhaseName.WRITE)


def _complete_write(run: Any) -> None:
    progress = _current_progress(run)
    if _phase_status(progress, PhaseName.WRITE) == PhaseStatus.PENDING:
        progress = advance(progress, into=PhaseName.WRITE)
    if _phase_status(progress, PhaseName.WRITE) == PhaseStatus.ACTIVE:
        progress = complete(progress, phase=PhaseName.WRITE)
    run.propose_progress = progress


def _fail_current_phase(run: Any, reason: str) -> None:
    progress = _current_progress(run)
    run.propose_progress = fail(progress, phase=phase_to_fail(progress), reason=reason)


#: `_tool_for_step` STOOD HERE, and its deletion is the feature (FR-002, T011).
#:
#: It returned ``tools[step % len(tools)]`` — an index nobody chose. Every governance
#: guarantee this platform holds was asserted around that expression: interception, ordering,
#: refusal, evidence, all correct, all about a sequence no model named.
#:
#: **It is not kept as a fallback**, and research F4 is why. A surviving fallback would be
#: taken exactly when the provider is down — so the platform would silently revert to a
#: scripted sequence at the moment nobody is watching, **while every governance row kept
#: passing**. That is this feature's own defect preserved as a feature. FR-007 makes a
#: provider failure terminal instead, and `tests/conformance/choice` asserts by source
#: inspection that no arithmetic selection returned.


def _run_steps(
    run: Any,
    *,
    durability: Any,
    blob_id: str,
    total_steps: int,
    tools: list[str],
    invoke_tools: bool,
    skip_reason: Any,
    chooser: Any = None,
    model: str = "",
    task: str = "",
    already_chosen: Any = None,
    effects: dict[int, str] | None = None,
    require_write_plan: bool = False,
    author: Any = None,
    reader: Any = None,
) -> tuple[int, list[int], list[int], str | None]:
    """Execute the run's steps, skipping the ones re-observation says already happened.

    **Each step is the full 005 bracket**: intent, work, result, checkpoint. A fixture that
    merely slept would have no step boundaries for a stop to be observed at and no intents
    for the zero-open-intents row to count — which would make the row that exists to prevent
    vacuous stop rows produce one.

    ``skip_reason`` decides skipping and is the only difference between a fresh run and a
    resumed one, which is deliberate: the skip is a *predicate*, not a second code path, so a
    resumed run cannot execute a step through any route a fresh run does not. The skip
    happens **before** invocation, so nothing reaches a tool without passing the hooks
    (Principle II).

    It returns a REASON rather than a boolean, because the reason is evidence. A skipped step
    whose effect already happened has no `TOOL_OUTCOME` of its own — the allocation that ran
    it may have died before writing one — so without a record of the skip the trail is simply
    short, and an investigator counting outcomes finds a step missing with nothing to explain
    it (ROADMAP gap 0c).

    Returns ``(exit_code, executed, skipped, ended_reason)``. ``ended_reason`` is set when the
    step loop stops early for a governed ending (empty choice, exhausted re-choice, stop
    request) so the terminal checkpoint — and the Build UI under Stopped — can say why.
    """
    executed: list[int] = []
    skipped: list[int] = []
    # WHICH TOOL RAN AT WHICH STEP (021). Read back before the run ends, so the report can say
    # whether an effect landed rather than only that it was allowed. Accumulated here because
    # this is the only place that knows both — the step index and the name the model chose.
    #
    # Mutated in place rather than returned: every caller already unpacks three values, and a
    # fourth would be a signature change across four call sites for a mapping only one of them
    # reads.
    ran: dict[int, str] = effects if effects is not None else {}
    researched = False
    planned = False
    post_plan_reads = 0
    write_locked = False
    if require_write_plan and author is not None:
        author.plan_ready = False

    for step in range(total_steps):
        if (why := skip_reason(step)) is not None:
            # Not re-executed, and not silently forgotten either. The caller reports the
            # counts, because "skipped 3 and ran 2" is what an investigator needs and a bare
            # completion cannot distinguish from "ran none of them" — and each skip also
            # records ITSELF, so the step is accounted for in the trail rather than only in a
            # summary that has to be trusted.
            skipped.append(step)
            _emit(
                run.audit_sink,
                correlation_id=run.correlation_id,
                tenant_id=run.tenant_id,
                event=AuditEventType.STEP_REOBSERVED,
                payload={"run_id": blob_id, "step_index": step, "reason": why},
            )
            continue

        if (reason := stop_requested(run)) is not None:
            # Noticed at the boundary — after the previous step's bracket closed and before
            # this one opens an intent. Nothing is left open, which is the whole reason the
            # check sits here rather than in a signal handler.
            print(f"run {run.correlation_id} ending at step {step}: {reason}", flush=True)
            return 0, executed, skipped, str(reason)

        if require_write_plan and researched and not planned:
            plan_failed = _run_write_plan(
                run,
                chooser=chooser,
                task=task,
                consulted=tuple(reader.consulted) if reader is not None else (),
                author=author,
            )
            if plan_failed:
                return 0, executed, skipped, plan_failed
            planned = True

        run.step_index = step

        # WHO NAMES THE TOOL (020). A model does, and this is the line where that became
        # true. Everything below is unchanged: the name goes to `invoke_tool`, which is the
        # same governed entry a scripted name went through, so no new path to a capability is
        # introduced by the model's involvement (FR-003).
        #
        # THE CARVE-OUT, named rather than left implicit (FR-002a). A run with `invoke_tools`
        # off runs steps and invokes no tool — it exists for the durability fixtures, which
        # need brackets to be killed *between* without caring what runs inside them. It has
        # nothing to choose, so asking a model would be a provider call whose answer is
        # discarded: cost and a failure mode for nothing. It stays, and it consults nobody.
        #
        # What it does NOT get is invisibility. `record_unconsulted_step` writes the fact into
        # the trail (FR-002b), because otherwise the carve-out becomes a way to produce a run
        # that looks governed, executed nothing, and consulted nobody — distinguishable from a
        # model-driven run only by the *absence* of entries, which is the weak evidence
        # `STEP_REOBSERVED` was added one feature ago to stop relying on.
        if not invoke_tools:
            record_unconsulted_step(run, step_index=step)
            tool_name = ""
        else:
            try:
                step_tools = tools
                if require_write_plan:
                    step_tools = _authoring_step_tools(
                        tools,
                        planned=planned,
                        post_plan_reads=post_plan_reads,
                    )
                    if planned and not write_locked and post_plan_reads >= _POST_PLAN_READ_BUDGET:
                        write_locked = True
                        print(
                            f"run {run.correlation_id}: write plan complete; "
                            "remaining steps must author",
                            flush=True,
                        )
                    if write_locked:
                        print(
                            f"run {run.correlation_id}: asking model to author (step {step})",
                            flush=True,
                        )
                resolution = resolve_step_tool(
                    run,
                    task=(
                        _write_locked_task(
                            task,
                            write_plan=str(getattr(run, "write_plan", "") or ""),
                            authored=author.contents if author is not None else None,
                        )
                        if write_locked
                        else task
                    ),
                    permitted=step_tools,
                    step_index=step,
                    model=model,
                    chooser=chooser,
                    # The act this step ALREADY chose, when a disrupted run left an open
                    # intent naming one (FR-008) — the tool AND, since 040, the arguments it
                    # was chosen with (FR-004). Honouring both is what makes re-observation
                    # honest — re-asking could return a different act from the one whose
                    # bracket is open, and the resumed run would then execute something the
                    # first allocation never chose while claiming to have observed it.
                    already_chosen=(already_chosen or {}).get(step),
                )
            except ChooserUnavailable as exc:
                # FR-007. Terminal and recorded, with no path back to a non-model selection.
                # The run fails the allocation rather than completing quietly, because a run
                # that could not consult its model has not done what it was dispatched to do
                # — and a completion here would be the platform's central claim going false
                # in exactly the case nobody is watching.
                print(
                    f"run {run.correlation_id} step {step}: {exc} ({exc.reason_code})",
                    file=sys.stderr,
                )
                _emit(
                    run.audit_sink,
                    correlation_id=run.correlation_id,
                    tenant_id=run.tenant_id,
                    event=AuditEventType.TOOL_CHOSEN,
                    payload={
                        "run_id": blob_id,
                        "step_index": step,
                        "attempt": 0,
                        "model": model,
                        "named": "",
                        # NOT `empty`. A model that declined to act and a provider that did
                        # not answer are different events, and the first dispatched run of
                        # this feature recorded the second as the first.
                        "outcome": str(ChoiceOutcome.PROVIDER_UNAVAILABLE),
                        "reason": exc.reason_code,
                    },
                )
                return 1, executed, skipped, str(exc.reason_code)

            if resolution.suspended:
                # A wait, not a refusal. The caller files the index row and exits zero.
                return _SUSPENDED, executed, skipped, None

            if resolution.is_terminal():
                authored_n = len(author.contents) if author is not None else 0
                empty_kind = (
                    _empty_after_plan(
                        planned=planned,
                        authored=authored_n,
                        remaining=len(
                            _remaining_planned(
                                write_plan=str(getattr(run, "write_plan", "") or ""),
                                authored=author.contents if author is not None else None,
                            )
                        ),
                        outcome=resolution.outcome,
                    )
                    if require_write_plan
                    else "stop"
                )
                if empty_kind == "done":
                    print(
                        f"run {run.correlation_id}: write complete ({authored_n} file(s))",
                        flush=True,
                    )
                    break
                if empty_kind == "retry":
                    print(
                        f"run {run.correlation_id}: model named nothing; asking again to author",
                        flush=True,
                    )
                    checkpoint_run(run, payload=_payload_with_progress({}, run))
                    executed.append(step)
                    continue
                # The model named nothing, or ground through its re-choice bound. Both are
                # endings the platform chose, both are already recorded by `resolve_step_tool`,
                # and neither is a crash — so this exits ZERO, on the same reasoning a
                # grant-expiry stop does. Exiting non-zero would make every bound look like a
                # failure to whoever reads allocation states.
                ended = _ended_reason_for_choice(resolution.outcome, resolution.attempts)
                print(
                    f"run {run.correlation_id} ending at step {step}: "
                    f"{resolution.outcome} after {resolution.attempts} attempt(s)",
                    flush=True,
                )
                return 0, executed, skipped, ended

            # `resolution.executed` rather than `resolution.tool`, because a named tool is
            # not a permitted one — the verdict belongs to `invoke_tool` and only the loop
            # that consulted it knows the answer. The only way to reach here without having
            # executed is a suspension, which returned above.
            tool_name = resolution.tool
            print(f"tool {tool_name}: allowed={resolution.executed}", flush=True)
            if tool_name == READ_SUBJECT and resolution.executed:
                researched = True
                if planned:
                    post_plan_reads += 1
            if tool_name == AUTHOR_FILE and resolution.executed:
                _mark_write_active(run)
                payload = getattr(resolution.result, "tool_result", None)
                authored_path = str(payload.get("path") or "") if isinstance(payload, dict) else ""
                print(
                    f"run {run.correlation_id}: authored {authored_path or 'file'}",
                    flush=True,
                )
                checkpoint_run(run, payload=_payload_with_progress({}, run))
                if author is not None and len(author.contents) >= _MAX_AUTHOR_FILES:
                    print(
                        f"run {run.correlation_id}: authored-file budget reached "
                        f"({len(author.contents)})",
                        flush=True,
                    )
                    break

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
        # 020 MOVED THE INVOCATION UP, not out. `resolve_step_tool` calls `invoke_tool` once
        # per attempt — the same call that stood here, with the same arguments, reached
        # through no new path — because the refusal has to come back *into* the choosing loop
        # to be offered to the model (FR-004a). Invoking here as well would have run every
        # permitted choice twice.
        #
        # A REFUSAL NO LONGER FAILS THE ALLOCATION, and that is the clarification's whole
        # substance. Until 020 an unpermitted tool returned 1 and the run died; now the denial
        # goes back to the model as context and it may choose again, bounded. What still ends
        # the run is exhausting that bound, and `resolve_step_tool` has already returned by
        # then. Suspension is handled above for the reason 014 wrote down: a wait that looks
        # like a failure is a wait nobody comes back for.
        if not tool_name:
            key = _step_key(blob_id, step)
            durability.record_intent(
                IntentRecord(
                    run_id=blob_id,
                    idempotency_key=key,
                    step_index=step,
                    tool_name="echo",
                    # `{}` explicitly, never defaulted (040, research R3): this is a
                    # post-040 record that genuinely asks for nothing, and a defaulted None
                    # would put it on the pre-feature side of the NULL-means-legacy line.
                    arguments={},
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

        # THROUGH `checkpoint_run`, not `provider.save`, and the difference is fencing.
        #
        # `checkpoint_run` asserts the lease before writing; a direct save does not. A
        # superseded allocation calling `save` would overwrite the state of the instance that
        # replaced it — which is exactly what FR-009 forbids, and it would be invisible,
        # because the zombie's writes look identical to the winner's. The invoke path already
        # asserts the lease on every tool call, so a direct save here would have left one of
        # the two write paths fenced and the other open.
        #
        # It also builds the blob from the run, which is the single place a checkpoint's shape
        # is decided — including the revival count, which a hand-built blob is free to forget.
        checkpoint_run(run, payload={"step": step})
        executed.append(step)
        if tool_name:
            # Recorded for the read-back this run performs before it ends (021, FR-006).
            ran[step] = tool_name

    return 0, executed, skipped, None


def _ended_reason_for_choice(outcome: Any, attempts: int) -> str:
    """User-safe why a model-driven step loop ended without naming a next tool."""
    name = str(outcome)
    if name == str(ChoiceOutcome.EMPTY):
        return "the model chose not to act"
    if name == str(ChoiceOutcome.EXHAUSTED):
        return f"the model could not name a permitted tool after {attempts} attempt(s)"
    return f"{name} after {attempts} attempt(s)"


def _subject_content_for(trees: Trees, paths: Any) -> dict[str, str]:
    """Subject bytes for paths the agent already wrote — only those, for compose diffs."""
    out: dict[str, str] = {}
    for path in paths:
        try:
            resolved = trees.resolve_in_subject(str(path))
        except Exception:  # noqa: BLE001 — missing/refused paths are empty before
            continue
        if resolved.is_file():
            out[str(path)] = resolved.read_text(errors="replace")
    return out


def _finish_authoring_analyzer(
    *,
    run: Any,
    durability: Any,
    blob_id: str,
    correlation_id: str,
    grant: Any,
    artifact: AuthoredArtifact,
    trees: Trees,
    author_contents: dict[str, str],
    consulted: tuple[str, ...],
    task: str,
    tools: list[str],
    ended_reason: str | None,
    effects: dict[int, str],
    steps: int,
    write_model: str = "",
    judge_chooser: Any = None,
    write_chooser: Any = None,
) -> int:
    """Compose the proposal and leave a non-terminal checkpoint for the proposer — or stop.

    **Must not write COMPLETED** when a proposal is ready: the proposer continues this same
    allocation (RUN_CONTINUE), and a terminal outcome makes it exit with nothing to publish.
    """
    result_body: dict[str, Any] = {
        "started": True,
        "tools": sorted(tools),
        "message": task or None,
        "received_context": [],
    }
    if ended_reason:
        result_body["reason"] = ended_reason
        _fail_current_phase(run, ended_reason)
        durability.save(
            CheckpointBlob(
                blob_id=blob_id,
                payload=_payload_with_progress({RESULT_KEY: result_body}, run),
                correlation_id=correlation_id,
                grant_id=grant.grant_id,
                step_index=max(steps - 1, 0),
                written_by="entrypoint",
                outcome=RunOutcome(state=RunState.STOPPED.value, stop_reason=ended_reason),
            )
        )
        observe_effects(run, observers=run.registry.observers(), executed=effects, run_id=blob_id)
        return 0

    if not author_contents:
        reason = "nothing was authored"
        result_body["reason"] = reason
        _fail_current_phase(run, reason)
        durability.save(
            CheckpointBlob(
                blob_id=blob_id,
                payload=_payload_with_progress({RESULT_KEY: result_body}, run),
                correlation_id=correlation_id,
                grant_id=grant.grant_id,
                step_index=max(steps - 1, 0),
                written_by="entrypoint",
                outcome=RunOutcome(state=RunState.STOPPED.value, stop_reason=reason),
            )
        )
        observe_effects(run, observers=run.registry.observers(), executed=effects, run_id=blob_id)
        print(f"run {correlation_id}: {reason}; no proposer handoff", flush=True)
        return 0

    repository = os.environ.get("RUN_TARGET_REPOSITORY", "").strip()
    if not repository:
        reason = "no target repository on the analyzer task"
        result_body["reason"] = reason
        _fail_current_phase(run, reason)
        durability.save(
            CheckpointBlob(
                blob_id=blob_id,
                payload=_payload_with_progress({RESULT_KEY: result_body}, run),
                correlation_id=correlation_id,
                grant_id=grant.grant_id,
                step_index=max(steps - 1, 0),
                written_by="entrypoint",
                outcome=RunOutcome(state=RunState.STOPPED.value, stop_reason=reason),
            )
        )
        return 1

    _complete_write(run)
    run.propose_progress = advance(_current_progress(run), into=PhaseName.JUDGE)
    durability.save(
        CheckpointBlob(
            blob_id=blob_id,
            payload=_payload_with_progress({RESULT_KEY: result_body}, run),
            correlation_id=correlation_id,
            grant_id=grant.grant_id,
            step_index=max(steps - 1, 0),
            written_by="entrypoint",
            outcome=None,
        )
    )
    print(f"run {correlation_id}: judging authored work", flush=True)
    allowed, judge_reason = quality_judge_may_publish(
        authored_paths=sorted(author_contents),
        task=task,
        write_plan=str(getattr(run, "write_plan", "") or ""),
        files=author_contents,
        write_model=write_model,
        judge_chooser=judge_chooser,
    )
    if not allowed:
        _fail_current_phase(run, judge_reason)
        result_body["reason"] = judge_reason
        durability.save(
            CheckpointBlob(
                blob_id=blob_id,
                payload=_payload_with_progress({RESULT_KEY: result_body}, run),
                correlation_id=correlation_id,
                grant_id=grant.grant_id,
                step_index=max(steps - 1, 0),
                written_by="entrypoint",
                outcome=RunOutcome(state=RunState.STOPPED.value, stop_reason=judge_reason),
            )
        )
        print(f"run {correlation_id}: {judge_reason}; no proposer handoff", flush=True)
        return 0
    run.propose_progress = complete(_current_progress(run), phase=PhaseName.JUDGE)

    write_plan = str(getattr(run, "write_plan", "") or "")
    copy_title, copy_rationale, copy_usage = reviewer_copy(
        chooser=write_chooser,
        task=task,
        write_plan=write_plan,
        files=author_contents,
    )
    print(f"run {correlation_id}: proposal title {copy_title!r}", flush=True)
    proposal = compose(
        artifact=artifact,
        target_repository=repository,
        branch=branch_for(f"{blob_id}:0:{OPEN_PROPOSAL}"),
        task=task or "authored changes",
        authored_content=author_contents,
        subject_content=_subject_content_for(trees, author_contents),
        title=copy_title,
        rationale=copy_rationale,
        usage=copy_usage,
        summary=write_plan,
        correlation_id=correlation_id,
        consulted=consulted,
        base_commit=os.environ.get("RUN_BASE_COMMIT", "").strip(),
    )
    payload = _payload_with_progress(
        {
            RESULT_KEY: result_body,
            PROPOSAL_PAYLOAD_KEY: proposal_payload(proposal),
        },
        run,
    )
    # NON-TERMINAL. The proposer's RUN_CONTINUE path refuses a terminal checkpoint.
    durability.save(
        CheckpointBlob(
            blob_id=blob_id,
            payload=payload,
            correlation_id=correlation_id,
            grant_id=grant.grant_id,
            step_index=max(steps - 1, 0),
            written_by="entrypoint",
            outcome=None,
        )
    )
    print(
        f"run {correlation_id}: composed proposal with {len(proposal.files)} file(s); "
        f"handing off to proposer",
        flush=True,
    )
    observe_effects(run, observers=run.registry.observers(), executed=effects, run_id=blob_id)
    return 0


def _run_task(*, run_id: str, credentials: Any, durability: Any) -> str:
    """What this run was asked to do, as text a model can be given.

    Read from durable state, never from the environment, and 012 established why: a person's
    free text must not enter a jobspec, where it would be visible to anyone with scheduler
    access and outside the tenant-scoped read path. That constraint was about *storage*; 020
    is the first feature where the text is actually consumed, and it points the same way.

    Empty is a real answer and not an error. A run started outside a thread has no message,
    and those runs behave exactly as they did before threads existed — the model is told the
    task is unsupplied and chooses from the permitted set on that basis, which is a worse
    prompt but a governed one.

    Failures are swallowed to the empty string, and this is the one place in this module where
    that is right: the thread store is a *context* source, not an authority or evidence one.
    A run that cannot read its own prompt should choose with less information, not refuse —
    refusing would make a threads-table outage look like a governance failure.
    """
    try:
        resolved = resolve_run_input(
            run_id=run_id,
            store=PostgresThreadStore(credentials=credentials, host=_db_host()),
            durability=durability,
        )
    except Exception:  # noqa: BLE001 — see the docstring; context, not authority
        return ""
    return resolved.message if resolved else ""


def _chooser_for(
    *,
    identity_fabric: Any,
    audit_sink: Any,
    correlation_id: str,
    tenant_id: str,
    agent_definition_id: str,
    run_id: str,
    role: str = CHOICE_ROLE,
) -> tuple[Any, str]:
    """The model this definition binds, and a chooser for it — or refuse before calling out.

    **The ordering is the requirement** (FR-005, FR-006). `resolve_bound_model` reads the
    binding map, parses the matrix, and validates the cell; only then does `build_chooser`
    construct anything. A model the matrix does not qualify must not be *reached*, not merely
    not used, and nothing here can reach one because there is no branch that builds a chooser
    from an unvalidated identifier.

    **Never defaults.** No binding for the role refuses the run — a default model is an
    ungoverned model choice, the same defect as an ungoverned tool choice one level up, and
    ADR-0022 and ADR-0039 exist to prevent exactly it.

    ``role`` defaults to ``CHOICE_ROLE`` (``plan``) for ordinary runs. Authoring analyzer
    steps pass ``WRITE_ROLE`` — ``authoring-agent`` binds ``write``, not ``plan``.

    Raises ``ResolutionRefused``, recorded as `AUTHORITY_REFUSED` first: this is the same
    class of refusal `manufacture` records under that event for `unqualified_cell` and
    `cell_withdrawn`, and a refusal nobody can see is indistinguishable from a run nobody
    attempted.

    **The credential is obtained between those two steps** (027): after the cell is validated and
    before anything is constructed. A fixture cell fetches nothing — there is no vendor to hold
    authority for — which is why every blocking lane in this repository still runs with no model
    credential at all (FR-011). A vendor cell that cannot obtain one refuses the run, recorded the
    same way and for the same reason: proceeding would mean an allocation reaching a vendor the
    platform holds no authority to call.

    This is the run half of *"both paths, one reader"*. The answering path fetches per ask; here an
    allocation **is** one task, so per-allocation and per-task are the same thing and the material
    evaporates when the process does.
    """
    try:
        model = resolve_bound_model(
            identity_fabric,
            agent_definition_id=agent_definition_id,
            role=role,  # type: ignore[arg-type]
        )
    except ResolutionRefused as exc:
        _emit(
            audit_sink,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            event=AuditEventType.AUTHORITY_REFUSED,
            payload={
                "run_id": run_id,
                "reason_code": str(getattr(exc, "reason_code", "") or "authority_refused"),
                "role": role,
            },
        )
        raise

    return (
        _chooser_from_model(
            identity_fabric=identity_fabric,
            audit_sink=audit_sink,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            run_id=run_id,
            model=model,
            role=role,
        ),
        model,
    )


def _chooser_from_model(
    *,
    identity_fabric: Any,
    audit_sink: Any,
    correlation_id: str,
    tenant_id: str,
    run_id: str,
    model: str,
    role: str,
) -> Any:
    """Build a chooser for a model the matrix has already qualified."""
    # The recording, for a cell whose provider is `fixture`. Read here rather than inside
    # `build_chooser` so the environment stays at the edge of the process, and ignored
    # entirely for a live provider — a recording present alongside an `anthropic/...` cell
    # grants nothing, because the branch that consults it is chosen by the *matrix*, not by
    # the presence of the variable.
    recording = os.environ.get("RUN_CHOICE_RECORDING", "").strip()

    secret = ""
    if not model.startswith(f"{FIXTURE_PROVIDER}/"):
        vendor = model.split("/", 1)[0]
        try:
            secret = (
                BrokeredModelCredential(read=identity_fabric.read_versioned).obtain(vendor).secret
            )
        except ResolutionRefused as exc:
            _emit(
                audit_sink,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                event=AuditEventType.AUTHORITY_REFUSED,
                payload={
                    "run_id": run_id,
                    "reason_code": str(getattr(exc, "reason_code", "") or "authority_refused"),
                    "role": role,
                },
            )
            raise

    # Authoring tools expect path/content, not the vault probe args a bare name meant for
    # pre-040 fixture tools. Passing those into `author_file` refuses every attempt and
    # exhausts the re-choice bound with nothing authored.
    bare_args = {} if authoring_role(dict(os.environ)) is not None else _LEGACY_PRE_040_ARGUMENTS

    return build_chooser(
        model,
        recording=recording,
        secret=secret,
        # A BARE NAME IN A RECORDING KEEPS MEANING WHAT IT MEANT (FR-010). Every
        # pre-040 recording named a tool while the platform supplied these, so
        # reading one as an empty request would change what it asks for — and
        # `vault_write` raises without `cas`, so the dispatched suites would fail.
        # Found exactly that way: hermetic rows passed against a handler that
        # accepts anything, and the allocation did not.
        bare_name_arguments=bare_args,
    )


def _distinct_live_judge_model(identity_fabric: Any, *, write_model: str) -> str:
    """A live judge cell whose model is not the writer (ADR-0067). Empty if none."""
    read = getattr(identity_fabric, "read_matrix", None)
    if read is None:
        return ""
    try:
        cells = parse_matrix_record(read())
    except Exception:  # noqa: BLE001 — missing/malformed matrix is "no judge", fail closed later
        return ""
    seen: list[str] = []
    for cell in cells.values():
        if (
            cell.role != "judge"
            or cell.qualified_by != "live"
            or cell.withdrawn
            or cell.model == write_model
            or cell.model.startswith(f"{FIXTURE_PROVIDER}/")
        ):
            continue
        if cell.model not in seen:
            seen.append(cell.model)
    for model in seen:
        if "opus" in model:
            return model
    return seen[0] if seen else ""


def _judge_chooser_for(
    *,
    identity_fabric: Any,
    audit_sink: Any,
    correlation_id: str,
    tenant_id: str,
    agent_definition_id: str,
    run_id: str,
    write_model: str,
) -> tuple[Any | None, str]:
    """A chooser that may judge authored work, never the write model.

    Fixture writers have no live work to judge — return ``(None, "")`` and keep the
    structural gate. A live writer with no distinct judge cell returns the same, and
    the finish path fail-closes rather than publishing unreviewed.
    """
    if not write_model or write_model.startswith(f"{FIXTURE_PROVIDER}/"):
        return None, ""
    judge_model = ""
    try:
        bound = resolve_bound_model(
            identity_fabric,
            agent_definition_id=agent_definition_id,
            role="judge",
        )
    except ResolutionRefused:
        bound = ""
    if bound and bound != write_model and not bound.startswith(f"{FIXTURE_PROVIDER}/"):
        judge_model = bound
    if not judge_model:
        judge_model = _distinct_live_judge_model(identity_fabric, write_model=write_model)
    if not judge_model or judge_model == write_model:
        return None, ""
    return (
        _chooser_from_model(
            identity_fabric=identity_fabric,
            audit_sink=audit_sink,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            run_id=run_id,
            model=judge_model,
            role="judge",
        ),
        judge_model,
    )


def continue_dispatched_run(
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
) -> int:
    """Continue a run a previous task checkpointed — **without counting a revival** (038).

    The third entry mode, and the one 038 needed. The other two do not fit a planned handoff:

    * **start** issues a fresh grant and begins step accounting at zero, which against the same
      `run_id` would discard everything the first task did;
    * **resume** counts `attempt = resume_count + 1` against `RESUME_ATTEMPT_CAP` and stops the
      run terminally past it. That budget exists to stop **flapping**, and spending it on a
      designed-in transition degrades the control silently: nothing goes red, the run simply has
      less margin than the platform believes.

    **Authority is re-manufactured here, and that is the substance rather than a detail.**
    `resume_run` was the only place that happened — *"Fresh authority under the surviving grant,
    from THIS allocation's identity. Nothing is read from the checkpoint here, and nothing should
    be."* Skipping it to avoid the counter would have skipped that too, and Principle IV is
    explicit: *"resume re-authenticates, never replays"*, and *"cached or precedent results never
    carry authority"*.

    The lease is acquired under this task's own holder identity, and `checkpoint_run` asserts it
    before every write — so a task continuing a run it does not hold cannot record anything.
    """
    checkpoint = durability.load(blob_id)
    if checkpoint is None:
        print(f"run {correlation_id}: no checkpoint to continue from", flush=True)
        return 1
    if checkpoint.outcome is not None and RunState(checkpoint.outcome.state).is_terminal():
        # A terminal run is not re-entered. The analysing task must leave the run resumable,
        # which a conformance row asserts — `complete_run` at the end of its step loop would
        # break this handoff silently.
        # Exit zero: the analysing task already recorded the ending. A non-zero here makes
        # Nomad mark the allocation failed and the Build page shows Stopped with no reason
        # of its own — the sibling failed for finishing, not for failing.
        print(f"run {correlation_id}: already terminal, nothing to continue", flush=True)
        return 0

    grant = durability.load_grant(checkpoint.grant_id) if checkpoint.grant_id else None
    if grant is None:
        print(f"run {correlation_id}: no grant to continue under", flush=True)
        return 1

    lease = RunLease(durability, run_id=blob_id, holder_identity=holder_identity)
    lease.acquire()

    # TASK SCOPE FOR THIS HALF, not the grant's original request (038 / ADR-0038).
    #
    # The analyzer manufactures under `RUN_REQUESTED_TOOLS=read_subject,author_file` and that
    # narrow set is what the grant records. The proposer's jobspec sets
    # `RUN_REQUESTED_TOOLS=open_proposal` — Principle IV's "task scope may narrow the ceiling"
    # per task of one run. Re-manufacturing under `grant.requested_scope` would keep the
    # analyzer's tools and leave `open_proposal` `out_of_scope` on every healthy handoff.
    #
    # When the env names tools, they are this task's requested scope. When unset, fall back to
    # the grant (non-authoring continuations, if any, keep prior behaviour).
    tools = frozenset(t for t in os.environ.get("RUN_REQUESTED_TOOLS", "").split(",") if t)
    if tools:
        requested_scope = AuthorityScope(
            tool_names=tools,
            product_actions=frozenset(
                action
                for name in tools
                for action in [_product_action_of(registry, name)]
                if action
            ),
        )
    else:
        requested_scope = grant.requested_scope

    try:
        authority = manufacture_authority(
            subject_user_id=grant.subject_user_id,
            requested_scope=requested_scope,
            identity_fabric=identity_fabric,
            clock=clock,
            agent_definition_id=grant.agent_definition_id,
            correlation_id=correlation_id,
        )
    except AuthorityRefuseError as exc:
        # Stops with the reason, on `resume_run`'s precedent: a cell can be withdrawn and a
        # pack can stop being loaded between the first task and the second, and both must stop
        # with the reason recorded rather than escaping as an untyped failure.
        print(f"run {correlation_id}: authority refused on continuation: {exc}", flush=True)
        return 1

    run = start_governed_run(
        correlation_id=correlation_id,
        subject_user_id=grant.subject_user_id,
        tenant_id=tenant_id,
        agent_definition_id=grant.agent_definition_id,
        requested_scope=requested_scope,
        identity_fabric=identity_fabric,
        registry=registry,
        audit_sink=audit_sink,
        clock=clock,
        manufactured=authority,
    )
    run.run_id = blob_id
    run.durability = durability
    run.lease = lease
    run.grant = grant
    # Step accounting continues where the first task left it. `resume_count` is untouched —
    # asserted by a row, because that untouched zero is the whole point of this mode.
    run.step_index = checkpoint.step_index
    run.resume_count = checkpoint.resume_count
    restored = ProposeProgress.from_payload(
        checkpoint.payload.get(PROGRESS_KEY) if isinstance(checkpoint.payload, dict) else None
    )
    if restored is not None:
        run.propose_progress = restored  # type: ignore[attr-defined]

    # THE PUBLISHING HALF (041). Until now this function re-established the run and
    # checkpointed it, which is everything a continuation needs *except* the act it exists to
    # perform. The proposer's whole job is one governed call, and it happens here — after
    # authority is re-manufactured, so the publish runs under this task's own attestation
    # rather than under anything the checkpoint carried.
    if authoring_role(dict(os.environ)) == PROPOSER:
        published = _publish_the_proposal(run, checkpoint=checkpoint, registry=registry)
        if published != 0:
            return published
        # `_publish_the_proposal` already wrote the terminal payload (PR URL, or a
        # phase failure). Re-saving `checkpoint.payload` here restored the analyzer
        # snapshot, wiped `pr_url`, and left Nomad "complete" looking like
        # "Ended without a pull request."
    else:
        checkpoint_run(run, payload=dict(checkpoint.payload))

    # FR-033: the finished acts' arguments are a customer's file content, and they do not
    # outlive the run. Closed brackets only — 040's own bound, because an open one revives by
    # re-invoking and needs its request.
    if authoring_role(dict(os.environ)) is not None:
        scrubbed = scrub_authoring_requests(durability, run_id=blob_id)
        if scrubbed:
            print(f"run {correlation_id}: scrubbed {scrubbed} authoring request(s)", flush=True)
    return 0


def _publish_the_proposal(run: Any, *, checkpoint: Any, registry: Any) -> int:
    """Register `open_proposal` for this task and invoke it once, through the governed path.

    **Registered here rather than at construction** because the handler needs the proposal the
    analysing task composed, which arrives in the checkpoint — so there is nothing to register
    until the checkpoint has been read.
    """
    try:
        proposal = proposal_from_payload(checkpoint.payload)
    except (KeyError, TypeError, ValueError):
        print(
            f"run {run.correlation_id}: the checkpoint carries no composed proposal; the "
            f"analysing task did not hand one over",
            flush=True,
        )
        run.propose_progress = advance(_current_progress(run), into=PhaseName.PROPOSE)
        _fail_current_phase(run, "the analysing task did not hand over a proposal")
        checkpoint_run(run, payload=_payload_with_progress(dict(checkpoint.payload), run))
        return 1

    # The reader is supplied HERE, by the surface that knows which fabric this deployment
    # runs. `core.authoring.credential` deliberately does not know (product blindness).
    #
    # Role `authoring-publisher`, not `agent-run`: only this JWT role's policy names
    # `harness-authority/data/authoring/vcs-app` (ADR-0062). `agent-run` cannot read the App
    # key, and a dispatch's job id is not in that role's bound claims either — the failure
    # reads as fabric_unreachable with a claim mismatch rather than a missing secret.
    identity = NomadWorkloadIdentity()
    credentials = AuthoringCredentials(
        identity=identity,
        reader=VaultDatabaseCredentials(identity=identity, role="authoring-publisher"),
    )
    installation = os.environ.get("RUN_VCS_INSTALLATION", "").strip()
    if not installation:
        print(f"run {run.correlation_id}: no installation named for publishing", flush=True)
        run.propose_progress = advance(_current_progress(run), into=PhaseName.PROPOSE)
        _fail_current_phase(run, "no installation named for publishing")
        checkpoint_run(run, payload=_payload_with_progress(dict(checkpoint.payload), run))
        return 1

    workspace = Path(os.environ.get("NOMAD_ALLOC_DIR", "/alloc")) / "workspace"
    publisher = ProposalPublisher(
        proposal=proposal,
        workspace=workspace,
        token_source=credentials,
        installation=installation,
    )
    observer = ProposalObserver(
        repository=proposal.target_repository,
        token_source=credentials,
        installation=installation,
        workspace=workspace,
    )
    authoring_registry_for(
        PROPOSER, registry=registry, proposal_handler=publisher, proposal_observer=observer
    )

    run.propose_progress = advance(_current_progress(run), into=PhaseName.PROPOSE)
    checkpoint_run(run, payload=_payload_with_progress(dict(checkpoint.payload), run))

    result = invoke_tool(run, OPEN_PROPOSAL, {})
    if not result.allowed:
        detail = result.reason_code or "denied"
        if result.message and result.message != "tool execution failed":
            detail = f"{detail}: {result.message}"
        print(f"run {run.correlation_id}: publishing refused ({detail})", flush=True)
        _fail_current_phase(run, detail)
        checkpoint_run(run, payload=_payload_with_progress(dict(checkpoint.payload), run))
        return 1
    print(f"run {run.correlation_id}: {result.tool_result}", flush=True)
    # 047 — success payload carries the PR URL for Propose UI / get_run_result.
    tool_result = result.tool_result if isinstance(result.tool_result, dict) else {}
    pr_url = None
    if isinstance(tool_result, dict):
        pr_url = tool_result.get("pr_url") or tool_result.get("url")
    if pr_url:
        run.propose_progress = complete(_current_progress(run), phase=PhaseName.PROPOSE)
        # Same key `surfaces.api.runs.run_result_for` reads — keep the literal here so
        # the entrypoint does not import the API package.
        payload = _payload_with_progress(dict(checkpoint.payload), run)
        payload[RESULT_KEY] = {
            "pr_url": pr_url,
            PROGRESS_KEY: payload.get(PROGRESS_KEY),
            "plan_evidence": getattr(proposal, "evidence", None),
        }
        # Terminal: get_run_result only discloses RESULT_KEY once an outcome exists
        # (or, after the 048 follow-up, when pr_url is already on the payload).
        # Leaving this non-terminal made Nomad's "complete" look like a Build that
        # produced nothing.
        checkpoint_run(
            run,
            payload=payload,
            outcome=RunOutcome(state=RunState.COMPLETED.value),
        )
        return 0
    _fail_current_phase(run, "publish produced no pull request")
    checkpoint_run(run, payload=_payload_with_progress(dict(checkpoint.payload), run))
    return 0


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
    task: str = "",
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
            # The third category, and the one that produces a step with no outcome of its
            # own: a closed result whose allocation died before auditing it. Counted here and
            # named per step by `STEP_REOBSERVED` below.
            "recorded_steps": len(decision.recorded_steps),
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
    recorded = {intent.step_index for intent in decision.recorded_steps}
    resume_from = checkpoint.step_index + 1

    # THE CHOICE THIS STEP ALREADY MADE (FR-008, T029), read from the open intent rather than
    # stored a second time.
    #
    # A pending step is one whose bracket was opened and whose effect re-observation found had
    # NOT landed — so it runs again. `invoke_tool` wrote that intent, and an intent carries
    # `tool_name`: the tool a model named before the disruption. Honouring it is what makes
    # "re-observe, never re-execute" honest under a non-deterministic chooser. Re-asking could
    # return a *different* tool, and the resumed run would then execute something the first
    # allocation never chose while an intent naming the original sat open — two tools, one
    # step, and a trail that reads as observation.
    #
    # No new record for this. The intent is already the durable statement of "we were about
    # to run X" — and, since 040, "with these" (FR-004) — written before the effect for
    # exactly this purpose; a second store holding the same fact would eventually disagree
    # with it.
    #
    # NULL IS NOT EMPTY (040, research R4). An intent whose arguments are None was recorded
    # before the column existed, and its first attempt ran with the legacy constant — so its
    # revival supplies that constant, repeating the act that was actually attempted. `{}` is
    # a post-040 intent that genuinely asked for nothing, and it revives with `{}`.
    already_chosen = {
        intent.step_index: Answer(
            intent.tool_name,
            _LEGACY_PRE_040_ARGUMENTS if intent.arguments is None else intent.arguments,
        )
        for intent in decision.pending_steps
    }

    def skip_reason(step: int) -> str | None:
        """Why this step will not run, or ``None`` to run it.

        The reason is named rather than reduced to a boolean because it goes in the trail,
        and the three are genuinely different claims: a closed result is the step's own
        record that it finished, re-observation is a judgement about an open bracket, and
        the checkpoint mark is a coarser backstop for steps that never bracketed at all.
        """
        if step in pending:
            return None
        # `recorded` is the fix for an exactly-once violation the conformance row caught, and
        # the ordering of these three inputs is the whole of it.
        #
        # A step writes its result and THEN its checkpoint. Killed in between — a window that
        # is a real fraction of every step, since a checkpoint is a lease-checked save — the
        # step is invisible to the other two inputs: its bracket is closed, so re-observation
        # never sees it (`completed`/`pending` are drawn from OPEN intents), and the
        # checkpoint still names the step before it, so `step < resume_from` is false at
        # exactly that index. The resumed run then re-executed an effect that had already
        # happened, which for a non-repeatable tool is the one thing this feature exists to
        # prevent — and it looked identical to a first run, so nothing downstream disagreed.
        #
        # The closed bracket is the stronger record: the result is written by the step at the
        # moment it finished, while the checkpoint is written afterwards and can be lost.
        # `step < resume_from` stays as the coarser backstop for steps that never bracketed.
        if step in recorded:
            return "result_recorded"
        if step in completed:
            return "reobserved_complete"
        if step < resume_from:
            return "below_checkpoint"
        return None

    # Built only when the run will actually consult one. A revived run that invokes no tools
    # reaches no model, so resolving a binding here would refuse revivals of every pre-020
    # fixture for naming no cell — turning a carve-out into an outage.
    chooser: Any = None
    model = ""
    if invoke_tools:
        try:
            chooser, model = _chooser_for(
                identity_fabric=identity_fabric,
                audit_sink=audit_sink,
                correlation_id=correlation_id,
                tenant_id=tenant_id,
                agent_definition_id=grant.agent_definition_id,
                run_id=blob_id,
                role=(WRITE_ROLE if authoring_role(dict(os.environ)) == ANALYZER else CHOICE_ROLE),
            )
        except ResolutionRefused as exc:
            print(f"resume refused: {exc}", file=sys.stderr)
            return 1

    effects: dict[int, str] = {}
    code, executed, skipped, ended_reason = _run_steps(
        run,
        durability=durability,
        blob_id=blob_id,
        total_steps=total_steps,
        tools=tools,
        invoke_tools=invoke_tools,
        skip_reason=skip_reason,
        chooser=chooser,
        model=model,
        task=task,
        already_chosen=already_chosen,
        effects=effects,
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

    result_payload: dict[str, Any] = {"resumed": True, "steps": executed}
    if ended_reason:
        result_payload["reason"] = ended_reason
    durability.save(
        CheckpointBlob(
            blob_id=blob_id,
            payload={**checkpoint.payload, RESULT_KEY: result_payload},
            correlation_id=correlation_id,
            grant_id=grant.grant_id,
            step_index=max(executed) if executed else checkpoint.step_index,
            written_by=holder_identity,
            outcome=RunOutcome(
                state=(RunState.STOPPED.value if ended_reason else RunState.COMPLETED.value),
                stop_reason=ended_reason,
            ),
            resume_count=decision.resume_count,
        )
    )

    # The read-back, on the revived allocation's own attested identity — see the fresh path's
    # comment for why placement is the whole of 021's Constitution Check.
    #
    # **Only the effects THIS allocation ran.** A step it skipped was executed by a previous
    # allocation, which observed its own effects before it ended; re-observing here would be
    # this allocation making a claim about work it did not do, and the trail already holds the
    # answer the run that did it recorded.
    observe_effects(run, observers=observers, executed=effects, run_id=blob_id)
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


def _refuse_unless_write_qualified(
    *, identity_fabric: Any, agent_definition_id: str, correlation_id: str
) -> int:
    """Stop the run unless a qualified `write` cell exists. 0 means qualified.

    **Reuses `resolve_bound_model` rather than adding a resolver.** That function already has
    the ordering FR-012 needs — binding map read, matrix parsed, cell validated, all before
    anything constructs a client — and it already refuses rather than defaulting. A second
    implementation here would be a second answer to "which model may write".

    The refusal is distinguishable from an outage on purpose: `unqualified_cell` sends an
    operator to the matrix, `provider_unavailable` sends them to a vendor's status page.
    """
    try:
        model = resolve_bound_model(
            identity_fabric,
            agent_definition_id=agent_definition_id,
            role=WRITE_ROLE,  # type: ignore[arg-type]
        )
    except ResolutionRefused as exc:
        print(
            f"run {correlation_id}: no qualified `write` cell "
            f"({getattr(exc, 'reason_code', 'unqualified_cell')}); authoring stops rather than "
            f"running under a model nothing qualified",
            flush=True,
        )
        return 1
    except Exception as exc:  # noqa: BLE001 — fail closed on any resolution failure
        print(f"run {correlation_id}: `write` cell could not be resolved: {exc}", flush=True)
        return 1
    print(f"run {correlation_id}: write cell {model}", flush=True)
    return 0


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

    # THE AUTHORING BRANCH (041 / 047). Read before Vault login: authoring-tier tasks use
    # task-bound JWT roles (`authoring-analyzer` / `authoring-publisher`), not `agent-run`.
    # Asking for the wrong role fails as a claim mismatch rather than naming the job.
    authoring = authoring_role(dict(os.environ))
    if authoring == ANALYZER:
        vault_role = "authoring-analyzer"
    elif authoring == PROPOSER:
        vault_role = "authoring-publisher"
    else:
        # Role "agent-run", not "conformance": the Vault role is selected by the job id in the
        # workload identity's claims, and a dispatched run's id is agent-run/dispatch-*.
        vault_role = "agent-run"

    # The allocation's own identity. No token reaches this process any other way.
    credentials = VaultDatabaseCredentials(identity=NomadWorkloadIdentity(), role=vault_role)
    db_host = _db_host()
    audit = PostgresAuditSink(credentials=credentials, host=db_host)
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

    # AFTER `build_registry` and BEFORE the fabric, which is the only correct position: the
    # fabric derives `known_tools` from the registry, so registering later would leave the
    # vocabulary narrower than the registry and reintroduce the refusal one layer down.
    authoring_reg: Any = None
    analyzer_trees: Trees | None = None
    artifact = AuthoredArtifact()
    if authoring == ANALYZER:
        analyzer_trees = trees_for(Path(os.environ.get("NOMAD_ALLOC_DIR", "/alloc")) / "workspace")
        authoring_reg = authoring_registry_for(
            ANALYZER,
            registry=registry,
            trees=analyzer_trees,
            artifact=artifact,
        )
        # THE `write` CELL, RESOLVED BEFORE ANY AUTHORING RUNS (041, FR-012).
        #
        # `resolve_write_cell` landed with 038 and nothing had ever called it — so the matrix
        # governed which model may ASK and which may PLAN, and said nothing about the role that
        # writes. Resolved here, at run start, because a capability that could run unqualified
        # for even one step is the gap 026 found for `ask`: the refusal must arrive before a
        # provider is reached, not after.
        #
        # The chooser below resolves the definition's bound cell for its own role; this is the
        # governance check that the WRITE role is qualified at all, and it stops the run rather
        # than degrading, because "nobody decided" is what an operator needs to see first.
        #
        # Performed after the fabric exists — see `_write_cell_is_qualified` below the toolset
        # construction, which is the earliest point the matrix can be read.

    # The roles the dispatching surface already resolved from this subject's verified
    # claims. Passed rather than re-derived: a second derivation is a second answer to
    # "who is this", and the two would diverge exactly when it mattered.
    roles = [r for r in os.environ.get("RUN_SUBJECT_ROLES", "").split(",") if r]

    fabric = SubjectScopedVaultFabric(
        roles=roles,
        credentials=credentials,
        known_tools=frozenset(registry.tool_names()) | AUTHORING_VOCABULARY,
        known_actions=registry.product_actions(),
    )
    # THE `write` CELL (041, FR-012). Earliest point the matrix is readable, and still before
    # any step runs — 026's rule: a capability that could run unqualified for even one step is
    # the gap, and the refusal must be a governance answer rather than an outage one.
    if authoring == ANALYZER:
        refused = _refuse_unless_write_qualified(
            identity_fabric=fabric,
            agent_definition_id=definition_id,
            correlation_id=correlation_id,
        )
        if refused:
            return refused

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
    # THE CONTINUATION MODE (038). A planned handoff between two tasks of one allocation is
    # NOT a revival, and routing it through the resume path would spend an attempt against
    # RESUME_ATTEMPT_CAP on every healthy run — leaving a genuinely interrupted one with less
    # margin than the platform believes it has, and making the trail read "attempt 2 of 5" for
    # a run that never failed. The cap is a safety bound against flapping; normal operation
    # must not consume it.
    #
    # Checked BEFORE the resume branch so the two are visibly exclusive rather than
    # accidentally ordered, and RUN_RESUME is asserted unset on both authoring tasks by a
    # conformance row — "the proposer resumes" is the phrasing that invites somebody to set it.
    if os.environ.get("RUN_CONTINUE", "").strip() == "1":
        durability = PostgresDurabilityProvider(credentials=credentials, host=db_host)
        return continue_dispatched_run(
            durability=durability,
            audit_sink=audit,
            registry=registry,
            identity_fabric=fabric,
            clock=SystemClock(),
            correlation_id=correlation_id,
            blob_id=blob_id,
            tenant_id=tenant_id,
            holder_identity=holder_identity,
        )

    if os.environ.get("RUN_RESUME", "").strip() == "1":
        durability = PostgresDurabilityProvider(credentials=credentials, host=db_host)
        store = PostgresDependencyStore(credentials=credentials, host=db_host)
        return resume_dispatched_run(
            task=_run_task(
                run_id=blob_id,
                credentials=credentials,
                durability=durability,
            ),
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
    durability = PostgresDurabilityProvider(credentials=credentials, host=db_host)
    durability.save_grant(grant)
    run.grant = grant
    run.run_id = blob_id
    run.durability = durability
    # A FRESH run claims the run too, not only a resumed one.
    #
    # Fencing is a comparison between whoever holds the lease and whoever is writing, so it
    # only protects a run that took the lease in the first place. Before 014 nothing on this
    # path did — `run.lease` stayed None, `checkpoint_run` skipped its assertion, and the
    # instance a resume supersedes could have gone on writing checkpoints and calling tools
    # underneath its successor. The zombie in FR-009's scenario is a FRESH allocation that
    # lost contact, so leaving this side unclaimed left the case the requirement is about.
    run.lease = RunLease(durability, run_id=blob_id, holder_identity=holder_identity)
    run.lease.acquire()

    if authoring == ANALYZER:
        # First live checkpoint the portal can read — intake's 202 progress never reaches
        # GET /runs/{id}/result, which is what the Build strip polls.
        _mark_research_active(run)
        checkpoint_run(run, payload=_payload_with_progress({}, run))

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
            outcome = invoke_tool(run, tool_name, _LEGACY_PRE_040_ARGUMENTS)
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
    effects: dict[int, str] = {}
    model = ""
    chooser: Any = None
    if steps > 0:
        # THE MODEL, RESOLVED BEFORE THE FIRST STEP AND BEFORE ANY PROVIDER CALL (FR-005,
        # FR-006). A definition binding no model for the role, or binding a cell the matrix
        # does not qualify, refuses the run here — with nothing reached and nothing invoked.
        #
        # Only when the run will consult one. `invoke_tools` off is the carve-out (FR-002a):
        # those runs choose nothing, so requiring them to name a qualified cell would refuse
        # every pre-020 durability fixture for a binding it has no use for.
        model = ""
        if invoke_tools:
            try:
                # Authoring analyzer uses the write-bound cell (`authoring-agent` binds
                # `write`, not `plan`). Ordinary runs keep CHOICE_ROLE.
                chooser, model = _chooser_for(
                    identity_fabric=fabric,
                    audit_sink=audit,
                    correlation_id=correlation_id,
                    tenant_id=tenant_id,
                    agent_definition_id=definition_id,
                    run_id=blob_id,
                    role=WRITE_ROLE if authoring == ANALYZER else CHOICE_ROLE,
                )
            except ResolutionRefused as exc:
                print(f"run refused: {exc}", file=sys.stderr)
                return 1

        # Nothing is already done on a fresh dispatch, and saying so as a predicate rather
        # than as a second loop is what keeps the resumed path from having an execution route
        # of its own.
        code, _, _, ended_reason = _run_steps(
            run,
            durability=durability,
            blob_id=blob_id,
            total_steps=steps,
            tools=sorted(tools),
            invoke_tools=invoke_tools,
            skip_reason=lambda _step: None,
            chooser=chooser,
            model=model,
            task=_run_task(run_id=blob_id, credentials=credentials, durability=durability),
            effects=effects,
            require_write_plan=authoring == ANALYZER,
            author=(
                authoring_reg.tools.author
                if authoring == ANALYZER and authoring_reg is not None and authoring_reg.tools
                else None
            ),
            reader=(
                authoring_reg.tools.reader
                if authoring == ANALYZER and authoring_reg is not None and authoring_reg.tools
                else None
            ),
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
                    credentials=credentials, host=db_host
                ).record_suspension,
                grant=grant,
                tenant_id=tenant_id,
                tools=sorted(tools),
                total_steps=steps,
                invoke_tools=invoke_tools,
            )
        if code != 0:
            return code
    else:
        ended_reason = None

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
    thread_store = PostgresThreadStore(credentials=credentials, host=db_host)
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
    # 041 / 047 — authoring analyzer hands a composed proposal to the proposer via a
    # non-terminal checkpoint. Writing COMPLETED here was why every Build ended with
    # "already terminal, nothing to continue" after the model only read the subject.
    if authoring == ANALYZER and analyzer_trees is not None and authoring_reg is not None:
        authored = (
            dict(authoring_reg.tools.author.contents) if authoring_reg.tools is not None else {}
        )
        consulted = authoring_reg.tools.reader.consulted if authoring_reg.tools is not None else ()
        judge_chooser = None
        judge_model = ""
        if model and not model.startswith(f"{FIXTURE_PROVIDER}/"):
            try:
                judge_chooser, judge_model = _judge_chooser_for(
                    identity_fabric=fabric,
                    audit_sink=audit,
                    correlation_id=correlation_id,
                    tenant_id=tenant_id,
                    agent_definition_id=definition_id,
                    run_id=blob_id,
                    write_model=model,
                )
            except ResolutionRefused as exc:
                print(f"run {correlation_id}: judge refused: {exc}", flush=True)
                judge_chooser, judge_model = None, ""
            if judge_model:
                print(f"run {correlation_id}: judge cell {judge_model}", flush=True)
        return _finish_authoring_analyzer(
            run=run,
            durability=durability,
            blob_id=blob_id,
            correlation_id=correlation_id,
            grant=grant,
            artifact=artifact,
            trees=analyzer_trees,
            author_contents=authored,
            consulted=consulted,
            task=(resolved.message if resolved else "") or "",
            tools=sorted(tools),
            ended_reason=ended_reason,
            effects=effects,
            steps=steps,
            write_model=model,
            judge_chooser=judge_chooser,
            write_chooser=chooser,
        )

    result_body: dict[str, Any] = {
        "started": True,
        "tools": sorted(tools),
        # Echoed so a row can assert what the run actually received, rather
        # than asserting that the resolver returned something and hoping the
        # run read it.
        "message": resolved.message if resolved else None,
        "received_context": (
            [{"run_id": rid, "result": body} for rid, body in resolved.context] if resolved else []
        ),
    }
    if ended_reason:
        # Build UI reads this under Stopped / Completed — without it the page keeps saying
        # "Working" after a governed early end (empty choice, exhausted re-choice, stop).
        result_body["reason"] = ended_reason
    durability.save(
        CheckpointBlob(
            blob_id=blob_id,
            payload={RESULT_KEY: result_body},
            correlation_id=correlation_id,
            # THE GRANT's id (research F1). This said `run.authority.credential_id` for nine
            # features — a 15-minute task credential in the column ADR-0026 defined as
            # referencing durable consent, and stored nowhere at all. A resume loading consent
            # by this value would have found nothing and refused every revival, so the store
            # existing and this line being right are one change, not two.
            grant_id=grant.grant_id,
            step_index=max(steps - 1, 0),
            written_by="entrypoint",
            outcome=RunOutcome(
                state=(RunState.STOPPED.value if ended_reason else RunState.COMPLETED.value),
                stop_reason=ended_reason,
            ),
        )
    )

    # THE READ-BACK (021, FR-006), and its placement is the whole of this feature's
    # Constitution Check.
    #
    # `Observer.observe` takes no credential and reads under AMBIENT identity — here that is
    # this allocation's, attested and bounded by the run's ceiling. At report time there is no
    # allocation, so a read-back performed for a reader would run under the API surface's
    # identity and hand them an observation they may hold no authority to make. An agent never
    # exceeds its human; a report must not exceed its reader.
    #
    # AFTER the terminal checkpoint, deliberately. Recording an observation must not change the
    # run's outcome (FR-016c): a run that did its work and then found an effect missing
    # completed and produced a finding, and letting the observation retroactively fail the run
    # would give a reporting mechanism power over what it reports. The checkpoint is already
    # written, so nothing below can alter it.
    observe_effects(run, observers=registry.observers(), executed=effects, run_id=blob_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
