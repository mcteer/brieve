# SPDX-License-Identifier: Apache-2.0
"""T1-T10 — the tier, with a subject in it (038, US4 prerequisite).

Several of these read the jobspec as text rather than driving Nomad. That is deliberate and is
037's precedent: **a tier nothing checks is a comment in a jobspec.** The posture lives in HCL,
so the assertion has to live where the posture does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.credential import analysing_task_holds_no_credential
from core.authoring.request import RequestRefused, resolve_subject_mount
from core.isolation.tier import (
    IsolationTier,
    SubjectMount,
    TierPosture,
    TierRefused,
    assert_tier,
)
from tests.harness.source_reading import code_without_prose

ROOT = Path(__file__).resolve().parents[3]
JOBSPEC = ROOT / "infra" / "jobs" / "authoring-tier.nomad.hcl"


@pytest.fixture(scope="module")
def jobspec() -> str:
    assert JOBSPEC.is_file(), f"the authoring tier has no jobspec at {JOBSPEC}"
    return JOBSPEC.read_text()


def _task_block(body: str, name: str) -> str:
    """The text of one task stanza. Crude by design — a parser would be a second HCL
    implementation, and what these rows need is *which task declares what*.
    """
    start = body.index(f'task "{name}"')
    nxt = body.find('task "', start + 10)
    return body[start:] if nxt == -1 else body[start:nxt]


def test_row_t1_a_read_only_subject_is_hardened_and_a_writable_one_is_not() -> None:
    """T1 — FR-005, FR-005a. By clause, so the refusal names what to fix."""
    assert_tier(IsolationTier.HARDENED, TierPosture("bridge", frozenset(), repo_mounted=False))

    read_only = TierPosture(
        "bridge", frozenset(), repo_mounted=False, subject_mount=SubjectMount("/subject", True)
    )
    assert_tier(IsolationTier.HARDENED, read_only)

    writable = TierPosture(
        "bridge", frozenset(), repo_mounted=False, subject_mount=SubjectMount("/subject", False)
    )
    hardened, why = writable.is_hardened()
    assert not hardened
    assert "writable" in why and "/subject" in why, (
        "the refusal must name the clause and the path; 'isolation failed' tells an operator "
        "nothing about what to fix, and a tier that fails opaquely is one people route around"
    )
    with pytest.raises(TierRefused, match="writable"):
        assert_tier(IsolationTier.HARDENED, writable)


def test_row_t2_037s_refusal_is_unchanged() -> None:
    """T2 — regression. The tier gained a clause; it lost nothing.

    A feature that extends an isolation check is exactly where one gets accidentally relaxed.
    """
    posture = TierPosture("bridge", frozenset(), repo_mounted=True)
    hardened, why = posture.is_hardened()
    assert not hardened
    assert why == "the repository is mounted; the delta must be delivered as input"


def test_row_t4_the_analyzer_declares_an_empty_static_egress_allowlist(jobspec: str) -> None:
    """T4 — FR-005a, research R13. Scoped to egress deliberately.

    The mount source in the same file is necessarily per-dispatch (T5), so a row claiming
    whole-posture staticness would assert something the design does not have.
    """
    analyzer = _task_block(jobspec, "analyzer")
    assert 'HARNESS_EGRESS_ALLOWLIST = ""' in analyzer, (
        "the analyzer inherited a non-empty allowlist; it reads a mount and fetches nothing, so "
        "any allowlisted host is a route out for a redirected agent holding a private codebase"
    )
    assert "NOMAD_META" not in analyzer.split("HARNESS_EGRESS_ALLOWLIST")[1].split("\n")[0], (
        "the allowlist is computed per run; FR-005a requires it be static configuration"
    )


def test_row_t5_the_subject_mount_source_is_validated_and_the_row_checks_a_path(
    tmp_path: Path,
) -> None:
    """T5 — FR-005a, research R25. A declared boolean cannot see a per-dispatch path.

    A dispatch naming the platform's own tree satisfies `bridge`, `readonly = true` and
    `repo_mounted = False` while mounting exactly what the tier exists to keep out.
    """
    platform = tmp_path / "platform"
    (platform / "src").mkdir(parents=True)
    subject = tmp_path / "customer-repo"
    subject.mkdir()

    mount = resolve_subject_mount(str(subject), platform_tree=platform)
    assert mount.read_only
    assert mount.source == str(subject.resolve())

    for named in (platform, platform / "src"):
        with pytest.raises(RequestRefused) as exc:
            resolve_subject_mount(str(named), platform_tree=platform)
        assert exc.value.reason_code == "subject_is_platform_tree"


def test_row_t3_the_analysing_task_holds_no_credential_that_could_publish(jobspec: str) -> None:
    """T3 — FR-015, ADR-0062. Structural: the absence is the control.

    **Task scope, not a second ceiling.** One run resolves one `agent_definition_id` and
    therefore one ceiling, so the two-definition form an earlier draft used was unbuildable
    against a one-run job. Principle IV's *user ∩ ceiling ∩ task scope ∩ policy* is what
    survives, and it is already enforced at the authority hook.
    """
    analyzer = _task_block(jobspec, "analyzer")
    proposer = _task_block(jobspec, "proposer")

    # Analyzer has a JWT for audit/DB (047), but Vault role authoring-analyzer must never
    # carry the App-key policy — authoring.tf binds authoring-publisher to proposer only.
    assert "identity {" in analyzer, (
        "the analyzer needs a workload identity to open the audit sink; publishing is blocked "
        "by Vault role split, not by omitting the JWT entirely"
    )
    assert "identity {" in proposer
    authoring_tf = (ROOT / "infra" / "modules" / "trust-fabric" / "authoring.tf").read_text()
    assert 'role_name       = "authoring-analyzer"' in authoring_tf
    assert 'nomad_task   = "proposer"' in authoring_tf
    analyzer_role = authoring_tf.split(
        'resource "vault_jwt_auth_backend_role" "authoring_analyzer"'
    )[1].split("resource ")[0]
    assert "authoring_publisher" not in analyzer_role
    assert "vcs-app" not in analyzer_role

    assert 'RUN_REQUESTED_TOOLS = "read_subject,author_file"' in analyzer
    assert 'RUN_REQUESTED_TOOLS = "open_proposal"' in proposer
    assert "open_proposal" not in analyzer.split("RUN_REQUESTED_TOOLS")[1].split("\n")[0]

    clean, why = analysing_task_holds_no_credential({"HARNESS_AUTHORING_ROLE": "analyzer"})
    assert clean, why
    dirty, why = analysing_task_holds_no_credential({"GITHUB_TOKEN": "x"})
    assert not dirty and "GITHUB_TOKEN" in why

    # App-key read on the publish path must use authoring-publisher — agent-run neither
    # carries the policy nor matches this job's workload identity claims.
    entrypoint = (ROOT / "src" / "surfaces" / "dispatch" / "entrypoint.py").read_text()
    publish = entrypoint[entrypoint.index("def _publish_the_proposal(") :]
    publish = publish[: publish.index("\ndef ", 4)]
    assert 'role="authoring-publisher"' in publish
    assert 'role="agent-run"' not in publish


def test_row_t6_every_module_is_assigned_to_a_task(jobspec: str) -> None:
    """T6 — research R28. The publishing task could not do the work it was first given.

    Composition diffs *against the subject* and the containment scan matches *subject files*;
    the proposer has no subject mount, which is its defining property. The split was reasoned
    about as authority — who holds the credential — and never as capability.
    """
    from core.authoring import __doc__ as package_doc

    assert package_doc is not None
    assert "analyzer" in package_doc and "proposer" in package_doc
    assert "containment" in package_doc, "the module→task assignment is not recorded"

    proposer = _task_block(jobspec, "proposer")
    # Platform `/repo` may be mounted so the entrypoint can run; the *subject* must not.
    assert "/subject" not in proposer
    assert "NOMAD_META_subject_path" not in proposer, (
        "the proposer mounts the subject; it must never hold it"
    )


def test_row_t8_run_resume_is_unset_on_both_tasks(jobspec: str) -> None:
    """T8 — the entrypoint branches on RUN_RESUME=1, and this handoff must not take that path.

    "The proposer resumes" is the phrasing that invites somebody to set it.
    """
    assert 'RUN_RESUME = "1"' not in jobspec
    assert 'RUN_RESUME="1"' not in jobspec
    assert 'RUN_CONTINUE = "1"' in _task_block(jobspec, "proposer")


def test_row_t10_the_lifecycle_ordering_is_asserted_because_the_lease_will_not_catch_it(
    jobspec: str,
) -> None:
    """T10 — research R27, corrected.

    `holder_identity` derives from NOMAD_ALLOC_ID, which is **per-allocation** — so the two
    tasks are the SAME lease holder. Run concurrently they would both pass `assert_held` and
    race on the checkpoint, each overwriting the other's step index, rather than fencing each
    other. An earlier draft justified sequencing by lease fencing; measurement contradicts it.

    Sequencing is still correct — the handoff needs it and T6's capability split assumes it —
    but the lease provides **no mutual exclusion between the tasks**, so this row is the control.
    """
    analyzer = _task_block(jobspec, "analyzer")
    assert "lifecycle {" in analyzer, "nothing sequences the two tasks"
    lifecycle = analyzer[analyzer.index("lifecycle {") :].split("}")[0]
    assert 'hook    = "prestart"' in lifecycle or 'hook = "prestart"' in lifecycle
    assert "sidecar = false" in lifecycle, (
        "a sidecar runs alongside rather than to completion, which is the concurrent "
        "arrangement the lease will not catch"
    )

    entrypoint = (ROOT / "src" / "surfaces" / "dispatch" / "entrypoint.py").read_text()
    assert 'os.environ.get("NOMAD_ALLOC_ID"' in entrypoint, (
        "holder_identity no longer derives from the allocation id; if it is now per-task the "
        "lease DOES fence these two, and this row's reasoning must be revisited rather than "
        "left asserting a premise that has changed"
    )


def test_row_the_jobspec_is_dispatchable_by_the_dispatcher_that_exists(jobspec: str) -> None:
    """Research R33 — `NomadDispatcher` takes a `job_id` but carries the agent-run meta keys."""
    assert "parameterized {" in jobspec
    for key in ("correlation_id", "tenant_id", "agent_definition_id", "run_id", "subject_path"):
        assert f'"{key}"' in jobspec, f"meta_required omits {key}; the dispatcher carries it"


def test_row_the_two_jobspecs_name_each_other_as_siblings(jobspec: str) -> None:
    """They differ in exactly two ways and both matter. Drift between them is the failure."""
    analysis = (ROOT / "infra" / "jobs" / "analysis-tier.nomad.hcl").read_text()
    assert "authoring-tier.nomad.hcl" in analysis
    assert "analysis-tier.nomad.hcl" in jobspec


def test_row_t9_the_continuation_mode_exists_and_does_all_four_things() -> None:
    """T9 — research R37. **The mode is new**, and T7's design assumed one existed.

    The entrypoint had exactly two entries: **start** (issues a grant, accounting from zero) and
    **resume** (`RUN_RESUME=1`, counts a revival). Start would discard everything the first task
    did; resume burns the budget T7 exists to protect.
    """
    raw = (ROOT / "src" / "surfaces" / "dispatch" / "entrypoint.py").read_text()
    assert 'os.environ.get("RUN_CONTINUE", "").strip() == "1"' in raw

    # **Prose stripped before matching.** This module necessarily contains a great deal of prose
    # ABOUT revival counting, and the first run of this row matched its own docstring — the
    # sixth time this repository has had a check match a comment instead of code.
    entrypoint = code_without_prose(raw)
    body = entrypoint[entrypoint.index("def continue_dispatched_run(") :]
    body = body[: body.index("def resume_dispatched_run(")]

    # 1. loads the blob, 2. loads the grant, 3. manufactures fresh authority,
    # 4. does not increment resume_count.
    assert "durability.load(blob_id)" in body
    assert "durability.load_grant(checkpoint.grant_id)" in body
    assert "manufacture_authority(" in body, (
        "the continuation does not re-authenticate. `resume_run` was the only place authority "
        "was re-manufactured, so skipping it to avoid the revival counter skips that too — and "
        "Principle IV requires resume re-authenticates, never replays"
    )
    assert "run.resume_count = checkpoint.resume_count" in body
    assert "resume_count + 1" not in body and "resume_run(" not in body, (
        "the continuation counts a revival; a planned handoff must not spend a budget that "
        "exists to stop flapping runs"
    )
    # 5. THIS task's RUN_REQUESTED_TOOLS, not grant.requested_scope alone — otherwise the
    # proposer's open_proposal stays out_of_scope under the analyzer's grant (041 handoff).
    assert "os.environ.get('RUN_REQUESTED_TOOLS'" in body, (
        "continuation must re-scope from the proposer's RUN_REQUESTED_TOOLS; manufacturing "
        "under grant.requested_scope alone keeps the analyzer's tools and denies publish"
    )

    # And it refuses a terminal run rather than silently doing nothing.
    assert "is_terminal()" in body
    # After a successful publish it must not restore the analyzer snapshot
    # (that wipe is "Ended without a pull request" with a live GitHub PR).
    assert "if published != 0:" in body
    success = body.split("if published != 0:", 1)[1].split("else:", 1)[0]
    assert "payload=dict(checkpoint.payload)" not in success


def test_row_t7_the_analyzer_leaves_the_run_non_terminal() -> None:
    """T7's dependency, asserted rather than assumed.

    `complete_run` is called from **nowhere** in `src/`, so a finished step loop happens to
    leave a run resumable — which this handoff needs. Adding it at the end of the loop later
    would break the handoff silently, and `resume.py` refuses a terminal outcome.
    """
    src = ROOT / "src"
    callers = [
        p.relative_to(ROOT)
        for p in src.rglob("*.py")
        if "complete_run(" in p.read_text() and "def complete_run(" not in p.read_text()
    ]
    assert not callers, (
        f"{callers} call complete_run; the analysing task must leave the run non-terminal or "
        f"the proposer cannot continue it, and a terminal outcome is refused rather than "
        f"noticed"
    )
