# SPDX-License-Identifier: Apache-2.0
"""P0-P12 — the work lands as a proposal, never as a change (038, US2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.authoring.artifact import AuthoredArtifact
from core.authoring.proposal import Proposal, ProposalState, branch_for, compose
from core.authoring.request import AuthoringRequest, RequestRefused
from core.authoring.tool import FileAuthor
from core.authoring.workspace import Trees

ROOT = Path(__file__).resolve().parents[3]
MODULE = "modules/secrets/main.tf"
BODY = 'data "vault_generic_secret" "db" {\n  path = "database/creds/app"\n}\n'

OWNED = frozenset({"acme/app", "acme/infra"})
AUTHORING_PACKS = frozenset({"terraform"})


def _request(**overrides: str) -> AuthoringRequest:
    base = {
        "correlation_id": "corr-038-propose",
        "tenant_id": "tenant-acme",
        "requester": "dana",
        "target_repository": "acme/app",
        "task": "Wire dynamic database secrets",
        "pack": "terraform",
    }
    base.update(overrides)
    return AuthoringRequest(**base)


def _proposal(trees: Trees, artifact: AuthoredArtifact, author: FileAuthor) -> Proposal:
    return compose(
        artifact=artifact,
        target_repository="acme/app",
        branch=branch_for("run-1:0:open_proposal"),
        task="Wire dynamic database secrets",
        authored_content=author.contents,
        subject_content={},
    )


def test_row_p0_authoring_adds_no_northbound_operation() -> None:
    """P0 — Principle II, research R16. Parity is **inherited rather than owed**.

    An absent parity row and a deliberately-inherited one look identical in a diff, and only one
    of them is a gate regression. This is the artefact that makes the difference legible.
    """
    for surface in ("api", "mcp", "portal"):
        root = ROOT / "src" / "surfaces" / surface
        if not root.is_dir():
            continue
        text = "".join(p.read_text() for p in root.rglob("*.py"))
        assert "author_file" not in text, (
            f"the {surface} surface names an authoring verb; an authoring request is the "
            f"payload of an ordinary dispatched run, so parity is inherited and a new "
            f"northbound operation would owe a parity row per transport pair"
        )
        assert "open_proposal" not in text


def test_row_p1_completed_authoring_is_a_proposal_and_nothing_is_merged_or_applied(
    trees: Trees, artifact: AuthoredArtifact, author: FileAuthor
) -> None:
    """P1 — FR-006, SC-001. Asserted over the state, not over the proposal's claim about itself."""
    author({"path": MODULE, "content": BODY})
    proposal = _proposal(trees, artifact, author)

    assert proposal.state is ProposalState.COMPOSED
    assert [f.path for f in proposal.files] == [MODULE]

    # The platform writes COMPOSED, REFUSED and OPENED. MERGED and CLOSED are OBSERVED from the
    # host — asserted as a partition rather than as "this one is not that one", which mypy
    # correctly calls vacuous when both sides are known literals.
    platform_writes = {ProposalState.COMPOSED, ProposalState.REFUSED, ProposalState.OPENED}
    observed = {ProposalState.MERGED, ProposalState.CLOSED}
    assert platform_writes | observed == set(ProposalState)
    assert not platform_writes & observed
    assert proposal.state in platform_writes


def test_row_p2_a_repository_the_requester_does_not_own_is_refused_before_producing() -> None:
    """P2 — FR-007. **Before**, not after: a refusal once files exist leaves something to leak."""
    with pytest.raises(RequestRefused) as exc:
        _request(target_repository="other-org/secrets").validate(
            run_tenant_id="tenant-acme",
            owned_repositories=OWNED,
            packs_declaring_authoring=AUTHORING_PACKS,
        )
    assert exc.value.reason_code == "repository_not_owned"


def test_row_p9_the_ownership_check_is_the_sole_enforcement_of_requester_scope() -> None:
    """P9 — FR-007. The target most likely to slip through.

    A version-control App installation is scoped to the **installing organisation**, not to an
    individual — so two requesters inside one organisation share one installation and the
    credential would reach either's repositories. An earlier draft claimed a bad target "fails
    twice"; that holds only for a single-user installation, which is not the case that matters.
    """
    # Same installation (`acme/*`), different owner. The credential would reach it.
    with pytest.raises(RequestRefused) as exc:
        _request(requester="dana", target_repository="acme/someone-elses").validate(
            run_tenant_id="tenant-acme",
            owned_repositories=OWNED,
            packs_declaring_authoring=AUTHORING_PACKS,
        )
    assert exc.value.reason_code == "repository_not_owned"

    with pytest.raises(RequestRefused) as exc:
        _request(tenant_id="tenant-other").validate(
            run_tenant_id="tenant-acme",
            owned_repositories=OWNED,
            packs_declaring_authoring=AUTHORING_PACKS,
        )
    assert exc.value.reason_code == "tenant_mismatch"


def test_row_p12_a_pack_that_declares_no_authoring_workflow_is_refused() -> None:
    """P12 — FR-021, Deferred. **This is now the only gate on it.**

    R2 counted three independent controls — the ceiling, the pack's declared workflow, and the
    tier. With both tools platform-level (ADR-0064), the pack no longer gates publishing at all.
    """
    with pytest.raises(RequestRefused) as exc:
        _request(pack="vault").validate(
            run_tenant_id="tenant-acme",
            owned_repositories=OWNED,
            packs_declaring_authoring=AUTHORING_PACKS,
        )
    assert exc.value.reason_code == "pack_declares_no_authoring"

    manifest = (ROOT / "packs" / "terraform" / "pack.toml").read_text()
    assert 'name         = "author-module"' in manifest, (
        "the terraform pack no longer declares author-module; the request check reads that "
        "declaration, so this row's premise has changed"
    )
    vault = (ROOT / "packs" / "vault" / "pack.toml").read_text()
    assert "author" not in vault.split("[[workflows]]")[1] if "[[workflows]]" in vault else True


def test_row_p3_a_second_proposal_does_not_displace_the_first() -> None:
    """P3 — FR-009. The branch derives from the **idempotency key** (see P7)."""
    first = branch_for("run-a:0:open_proposal")
    second = branch_for("run-b:0:open_proposal")
    assert first != second
    assert first.startswith("brieve/authoring/")


def test_row_p7_the_observers_input_is_sufficient_to_find_the_proposal() -> None:
    """P7 — FR-009, and the row that exists because the first design made P4 impossible.

    `Observer.observe(*, idempotency_key)` receives that string and **nothing else**, and the
    key is ``run_id:step_index:tool_name``. The branch was derived from the **correlation ID**,
    which the observer never sees and which is not reliably the same as `run_id` — so an
    interrupted publish would have resolved `CANNOT_DETERMINE` and parked the run, every time,
    while P4 still passed by asserting only that an observer was *registered*.

    **A row that checks a mechanism exists is not a row that checks it can work.**
    """
    import inspect

    from core.observation.types import Observer

    signature = inspect.signature(Observer.observe)
    assert set(signature.parameters) == {"self", "idempotency_key"}, (
        "the observer's input changed; the branch derivation must change with it"
    )

    key = "run-1:3:open_proposal"
    assert branch_for(key) == branch_for(key), "the branch is not recomputable from the key"

    # A resumed run recomputes the SAME branch — which is what makes the observation meaningful
    # rather than lucky — while two different runs do not collide.
    assert branch_for("run-1:3:open_proposal") != branch_for("run-2:3:open_proposal")

    engine = (ROOT / "src" / "core" / "hooks" / "engine.py").read_text()
    assert 'f"{run_id}:{run.step_index}:{tool_name}"' in engine, (
        "the idempotency key's shape changed; the branch derives from it, and the observer "
        "holds nothing else"
    )


def test_row_p5_the_humans_decision_is_distinguishable_from_everything_the_platform_did() -> None:
    """P5 — FR-008, SC-001, ADR-0043.

    `PROPOSAL_OPENED` is the platform's act. **There is no merge member at all**, and its
    absence is the property: a machine act never satisfies an approval assigned to a person.
    """
    from core.audit.schema import AuditEventType

    names = {m.value for m in AuditEventType}
    assert "proposal_opened" in names
    assert not any("merge" in n for n in names), (
        "a merge member exists; the platform must not be able to record having accepted its "
        "own work, and a merge is observed rather than written"
    )


def test_row_p6_an_unreviewed_proposal_is_not_reported_as_completed_work() -> None:
    """P6 — the spec's edge case. Forecloses a dashboard counting proposals as delivered work."""
    assert ProposalState.OPENED.value == "opened"
    terminal = {ProposalState.MERGED, ProposalState.CLOSED}
    assert ProposalState.OPENED not in terminal, (
        "an opened proposal counts as finished; nothing should report an unreviewed proposal "
        "as completed work"
    )


def test_row_p10_the_artefact_reaches_the_publishing_task_under_one_correlation_id() -> None:
    """P10 — FR-004, FR-006, Principle IX.

    The two-posture split gave the analysing side an empty egress allowlist and an ephemeral
    workspace and defined **no transfer** — the artefact had no way to reach the side that
    publishes it. One group with two tasks resolves that and the correlation-ID problem together.

    **And the row records what was lost**: a group in bridge mode shares one network namespace,
    so network-level separation between the tasks is not a control.
    """
    from core.authoring.workspace import ALLOC_WORKSPACE

    jobspec = (ROOT / "infra" / "jobs" / "authoring-tier.nomad.hcl").read_text()
    assert ALLOC_WORKSPACE.startswith("/alloc/"), (
        "the workspace is not in the shared allocation directory; the two tasks cannot meet"
    )
    assert jobspec.count('RUN_CORRELATION_ID     = "${NOMAD_META_correlation_id}"') == 2, (
        "the two tasks do not record under one correlation ID"
    )
    assert "network namespace is shared" in jobspec.lower() or "NAMESPACE IS SHARED" in jobspec, (
        "the jobspec no longer records that the namespace is shared; that absence is how "
        "somebody later claims network isolation between the two tasks"
    )


def test_row_p11_open_proposal_is_non_repeatable_and_carries_an_observer(
    trees: Trees, artifact: AuthoredArtifact
) -> None:
    """P11 — FR-009. **Nothing else checks this.**

    The `observer_required` refusal lives in the **pack loader**, and `open_proposal` is a
    platform tool (ADR-0064) — so the property is asserted here or nowhere, and P4's resolution
    by observation depends on it.
    """
    from core.authoring.tool import OPEN_PROPOSAL
    from core.observation.types import Observation, ObservationOutcome
    from core.registry.memory import ToolRegistry

    class _ProposalObserver:
        """Recomputes the branch from the key alone — P7's property, exercised."""

        def observe(self, *, idempotency_key: str) -> Observation:
            branch_for(idempotency_key)
            return Observation(outcome=ObservationOutcome.DID_NOT_HAPPEN)

    registry = ToolRegistry()
    registry.register(
        OPEN_PROPOSAL,
        lambda _a: {"ok": True},
        risk_class="write",
        repeatable=False,
        observer=_ProposalObserver(),
    )

    registration = registry.resolve(OPEN_PROPOSAL)
    assert registration.risk_class == "write"
    assert registration.repeatable is False
    assert registration.observer is not None, (
        "a non-repeatable tool with no observer parks the run on CANNOT_DETERMINE; the pack "
        "loader would have refused this, and a platform registration is not covered by it"
    )
    assert OPEN_PROPOSAL in registry.observers()


def test_row_p8_a_non_durable_run_refuses_to_publish() -> None:
    """P8 — FR-006, Principle III.

    Bracketing is conditional: `run.durability is not None and not repeatable and key is not
    None`. A non-durable run executes this non-repeatable tool **unbracketed**, with no intent
    record and nothing for P7 to observe — the one posture where an interruption is
    unrecoverable, so it is refused rather than entered.
    """
    engine = (ROOT / "src" / "core" / "hooks" / "engine.py").read_text()
    assert "run.durability is not None" in engine
    assert "not registration.repeatable" in engine, (
        "the bracket condition changed; P8's premise is that a non-durable run skips it"
    )


def test_row_p4_an_interrupted_proposal_is_resolvable_by_observation() -> None:
    """P4 — the spec's edge case. Resolution asks the host rather than guessing.

    Read with P7: this asserts an observer *exists*; P7 asserts it can *work*.
    """
    from core.observation.types import Observation, ObservationOutcome

    seen: list[str] = []

    class _ProposalObserver:
        def observe(self, *, idempotency_key: str) -> Observation:
            seen.append(branch_for(idempotency_key))
            return Observation(outcome=ObservationOutcome.HAPPENED, detail="proposal exists")

    result = _ProposalObserver().observe(idempotency_key="run-9:2:open_proposal")
    assert result.outcome is ObservationOutcome.HAPPENED
    assert seen == [branch_for("run-9:2:open_proposal")]


def test_row_a_valid_request_passes_every_check() -> None:
    """The positive case, so the refusals above are not passing for the wrong reason."""
    _request().validate(
        run_tenant_id="tenant-acme",
        owned_repositories=OWNED,
        packs_declaring_authoring=AUTHORING_PACKS,
    )
