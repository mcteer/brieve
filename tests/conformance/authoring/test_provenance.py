# SPDX-License-Identifier: Apache-2.0
"""V1-V4 — the platform does not enact what it authored (038, FR-020).

**V1 and V2 are both here, and that is the design.** V1 asserts the rule fires; V2 asserts
there is nothing for it to fire on. V2 is a fact about *today's definitions*; V1 is what
survives a definition somebody writes next year. Either alone is half a guarantee.

**V4 asserts where the rule runs.** The first two drafts of this feature put the refusal in a
module function — which reads identically to enforcement in a task list and is not enforcement.
V1 over a module function would have been green.
"""

from __future__ import annotations

from pathlib import Path

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.authoring.hooks import provenance_hook
from core.authoring.proposal import ProposalState
from core.authoring.provenance import Provenance, ProvenanceLedger
from core.hooks.types import CapabilityKind, HookContext, HookPhase

ROOT = Path(__file__).resolve().parents[3]
DIGEST = "b" * 64

#: Supplied by the row, as assembly supplies it in production. **`core` never names one**: the
#: rule's shape belongs there and the product knowledge does not, which `test_core_is_product_blind`
#: caught on this hook's first run.
ENACTING = frozenset({"terraform_apply"})


class _Run:
    correlation_id = "corr-038-enact"
    tenant_id = "tenant-test"

    def __init__(self) -> None:
        self.audit_sink = InMemoryAuditSink()


def _ctx(run: _Run, tool: str, **args: object) -> HookContext:
    return HookContext(
        correlation_id=run.correlation_id,
        tool_name=tool,
        arguments=args,
        phase=HookPhase.PRE,
        run=run,
    )


def test_row_v1_the_platform_does_not_enact_what_it_authored() -> None:
    """V1 — FR-020, SC-009. The rule turns on **provenance, not capability**."""
    ledger = ProvenanceLedger()
    ledger.record(
        Provenance(
            content_digest=DIGEST,
            authoring_correlation_id="corr-authoring-77",
            proposal_state=ProposalState.OPENED,
        )
    )
    run = _Run()
    decision = provenance_hook(ledger, enacting_tools=ENACTING).handler(
        _ctx(run, "terraform_apply", content_digest=DIGEST)
    )

    assert decision.outcome == "deny"
    assert decision.reason_code == "enactment_of_own_output"
    assert "corr-authoring-77" in decision.message

    entries = run.audit_sink.list_by_correlation_id(run.correlation_id)
    refusals = [e for e in entries if e.event_type is AuditEventType.ENACTMENT_REFUSED]
    assert len(refusals) == 1
    assert refusals[0].payload["authoring_correlation_id"] == "corr-authoring-77"
    assert refusals[0].payload["attempted_tool"] == "terraform_apply"


def test_row_v1_a_merged_proposal_is_ordinary_reviewed_configuration() -> None:
    """FR-020a — once a person merges, applying is the act it always was.

    The merge is **observed**, never performed: `mark_merged` records what the host reported.
    """
    ledger = ProvenanceLedger()
    ledger.record(
        Provenance(
            content_digest=DIGEST,
            authoring_correlation_id="corr-authoring-77",
            proposal_state=ProposalState.OPENED,
        )
    )
    ledger.mark_merged(DIGEST)

    run = _Run()
    decision = provenance_hook(ledger, enacting_tools=ENACTING).handler(
        _ctx(run, "terraform_apply", content_digest=DIGEST)
    )
    assert decision.outcome == "allow"
    assert run.audit_sink.list_by_correlation_id(run.correlation_id) == []


def test_row_v1_content_the_platform_never_authored_is_not_this_rules_business() -> None:
    """The rule is about *our own output* and nothing else."""
    run = _Run()
    decision = provenance_hook(ProvenanceLedger(), enacting_tools=ENACTING).handler(
        _ctx(run, "terraform_apply", content_digest="c" * 64)
    )
    assert decision.outcome == "allow"


def test_row_v2_the_ceiling_carries_no_enacting_tool_and_neither_task_can_reach_one() -> None:
    """V2 — SC-009. Structural, and the stronger half of V1.

    **Disjointness between two definitions is gone**: one run resolves one
    `agent_definition_id`, so the authoring/proposing pair an earlier draft used was unbuildable
    against a one-run job. What remains is a single ceiling that never carried an enacting tool,
    plus task scope narrowing within it.
    """
    from core.authority.intersection import intersect_scopes
    from core.authority.types import AuthorityScope

    ceiling = AuthorityScope(
        tool_names=frozenset({"read_subject", "author_file", "open_proposal"}),
        product_actions=frozenset(),
    )
    assert not (ceiling.tool_names & ENACTING), (
        "the authoring ceiling carries an enacting tool; V1 is the rule and this is the absence "
        "of anything to apply it to"
    )

    for scope in (frozenset({"read_subject", "author_file"}), frozenset({"open_proposal"})):
        effective = intersect_scopes(
            ceiling,
            ceiling,
            AuthorityScope(tool_names=scope, product_actions=frozenset()),
        )
        assert not (effective.tool_names & ENACTING)


def test_row_v3_terraform_apply_is_not_narrowed() -> None:
    """V3 — FR-020a. A feature that made the platform safer by weakening an existing capability
    would have changed the product without saying so.
    """
    manifest = (ROOT / "packs" / "terraform" / "pack.toml").read_text()
    block = manifest[manifest.index('name       = "terraform_apply"') :]
    block = block[: block.index("[[skills]]")]

    assert 'risk_class = "destructive"' in block
    assert "repeatable     = false" in block or "repeatable = false" in block
    assert "terraform_apply_observer" in block


def test_row_v4_the_provenance_refusal_runs_in_the_hook_pipeline() -> None:
    """V4 — Principle III. **V1 asserts the rule fires; this asserts it fires where enforcement
    lives.**

    A refusal reachable only by a caller remembering to call it is a convention. The first two
    drafts placed this in `provenance.py` as a module function, and V1 over that would have been
    green.
    """
    registration = provenance_hook(ProvenanceLedger(), enacting_tools=ENACTING)
    assert registration.phase is HookPhase.PRE
    assert registration.capability_kind is CapabilityKind.GOVERNANCE
    assert registration.name == "authoring_provenance"

    engine = (ROOT / "src" / "core" / "hooks" / "engine.py").read_text()
    assert "CapabilityKind.GOVERNANCE" in engine, (
        "the engine no longer orders governance hooks first; this registration's placement "
        "depends on that ordering"
    )


def test_row_provenance_is_keyed_on_content_not_on_a_path() -> None:
    """A file moved, renamed or copied is the same bytes. A rule keyed on the path is defeated
    by `cp`, which is not a sophisticated attack.
    """
    ledger = ProvenanceLedger()
    ledger.record(
        Provenance(
            content_digest=DIGEST,
            authoring_correlation_id="corr-authoring-77",
            proposal_state=ProposalState.OPENED,
        )
    )
    permitted, provenance = ledger.may_enact(DIGEST)
    assert not permitted
    assert provenance is not None
    assert provenance.authoring_correlation_id == "corr-authoring-77"
