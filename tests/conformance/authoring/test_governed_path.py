# SPDX-License-Identifier: Apache-2.0
"""A6-A9 — the trio traverses the same pipeline everything else does (041, US2).

FAKE_FABRIC_IS_FAULT_INJECTION = (
    "Authority is resolved through the fake so a row can hold every term fixed but one — the "
    "ceiling, or the task scope — which is what makes 'the same pipeline' and 'the ceiling "
    "still decides' separable claims rather than one claim asserted twice."
)

**What separates these from 038's rows.** 038 asserts the handlers behave: a write goes to the
workspace, an escape refuses, a read is budgeted. All true, and all asserted against handlers
constructed directly. These assert the same properties through **the registry the entrypoint
builds**, which is the path that did not exist — so a regression that unregistered the trio
would fail here while every 038 row stayed green.
"""

from __future__ import annotations

from pathlib import Path

from core.audit.sink import InMemoryAuditSink
from core.authoring.tool import AUTHOR_FILE, OPEN_PROPOSAL, READ_SUBJECT
from core.authority.types import AuthorityScope
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from core.tools.invoke import invoke_tool
from surfaces.dispatch.authoring import ANALYZER, PROPOSER
from tests.harness.authoring_dispatch import build_as_entrypoint
from tests.harness.capture_audit import capture_audit
from tests.harness.fake_identity_fabric import fake_identity_fabric
from tests.harness.frozen_clock import frozen_clock

FAKE_FABRIC_IS_FAULT_INJECTION = (
    "Authority is resolved through the fake so each row can vary exactly one term."
)

DEFINITION = "authoring-agent"
MODULE = "modules/secrets/main.tf"
BODY = 'data "vault_generic_secret" "db" {\n  path = "database/creds/app"\n}\n'


def _run(
    registry: ToolRegistry,
    audit: InMemoryAuditSink,
    *,
    ceiling: set[str],
    requested: set[str] | None = None,
) -> GovernedRun:
    asked = requested if requested is not None else set(ceiling)
    fabric = fake_identity_fabric(
        tool_names=set(ceiling),
        product_actions=set(),
        ceiling_tools=set(ceiling),
        ceiling_actions=set(),
    )
    return start_governed_run(
        agent_definition_id=DEFINITION,
        correlation_id="corr-041-governed",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=frozenset(asked), product_actions=frozenset()),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )


def test_row_a6_an_authored_write_traverses_the_governed_entry(tmp_path: Path) -> None:
    """A6 — same entry, same hooks, same records as any other tool (FR-004, SC-003)."""
    built = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path)
    audit = capture_audit()
    run = _run(built.registry, audit, ceiling={READ_SUBJECT, AUTHOR_FILE})

    result = invoke_tool(run, AUTHOR_FILE, {"path": MODULE, "content": BODY})

    assert result.allowed and result.executed
    assert (built.trees.workspace / MODULE).read_text() == BODY  # type: ignore[union-attr]
    assert run.probe_log, "the hook pipeline must have run; an empty probe log is a bypass"


def test_row_a6_the_write_risk_class_survives_registration(tmp_path: Path) -> None:
    """`author_file` is the registry's first `write`; a change to `read` widens what reaches it."""
    built = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path)
    assert built.registry.resolve(AUTHOR_FILE).risk_class == "write"
    assert built.registry.resolve(READ_SUBJECT).risk_class == "read"


def test_row_a6_the_publishing_tool_is_non_repeatable_with_an_observer(tmp_path: Path) -> None:
    """Opening a proposal twice creates two; the registration is what prevents it."""
    built = build_as_entrypoint(role=PROPOSER, tmp_path=tmp_path)
    registration = built.registry.resolve(OPEN_PROPOSAL)

    assert registration.repeatable is False
    assert registration.observer is not None, (
        "a non-repeatable tool without an observer resolves CANNOT_DETERMINE and parks the run"
    )


def test_row_a7_an_escaping_path_refuses_through_the_registered_tool(tmp_path: Path) -> None:
    """A7 — containment holds on the path a run actually takes (FR-006)."""
    built = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path)
    audit = capture_audit()
    run = _run(built.registry, audit, ceiling={AUTHOR_FILE})

    result = invoke_tool(run, AUTHOR_FILE, {"path": "../escaped.tf", "content": "x"})

    assert not (result.allowed and result.executed)
    assert not (tmp_path / "escaped.tf").exists()


def test_row_a8_a_subject_read_is_governed_and_enumerable(tmp_path: Path) -> None:
    """A8 — the lens attaches, the read is recorded, and `consulted` is ordered (FR-005)."""
    built = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path)
    subject = built.trees.subject  # type: ignore[union-attr]
    (subject / "a.tf").write_text("alpha\n")
    (subject / "b.tf").write_text("beta\n")
    audit = capture_audit()
    run = _run(built.registry, audit, ceiling={READ_SUBJECT})

    first = invoke_tool(run, READ_SUBJECT, {"path": "a.tf"})
    second = invoke_tool(run, READ_SUBJECT, {"path": "b.tf"})

    assert first.allowed and second.allowed
    assert built.tools is not None
    assert built.tools.reader.consulted == ("a.tf", "b.tf"), (
        "what was consulted must be recoverable in read order, which is what FR-004's "
        "provenance rests on"
    )


def test_row_a8_an_over_budget_read_discloses_rather_than_truncating(tmp_path: Path) -> None:
    """Half a file read as though whole is the silent partial the budget exists to prevent."""
    from core.authoring.artifact import AuthoredArtifact
    from core.authoring.workspace import Trees
    from core.registry.memory import ToolRegistry as Registry
    from surfaces.dispatch.authoring import authoring_registry_for

    subject = tmp_path / "s"
    subject.mkdir()
    (subject / "big.tf").write_text("x" * 4096)
    workspace = tmp_path / "w"
    workspace.mkdir()

    registry = Registry()
    registration = authoring_registry_for(
        ANALYZER,
        registry=registry,
        trees=Trees(subject=subject.resolve(), workspace=workspace.resolve()),
        artifact=AuthoredArtifact(),
    )
    audit = capture_audit()
    run = _run(registry, audit, ceiling={READ_SUBJECT, AUTHOR_FILE})

    # The budget lives on the handler; drive it below the file's size.
    assert registration.tools is not None
    registration.tools.reader._budget = 16
    result = invoke_tool(run, READ_SUBJECT, {"path": "big.tf"})

    assert result.allowed, "an over-budget read discloses; it does not error"
    assert result.tool_result["over_budget"] is True
    assert result.tool_result["content"] == ""
    assert registration.tools.reader.truncated is True


def test_row_a9_task_scope_refuses_what_the_ceiling_permits(tmp_path: Path) -> None:
    """A9 — a REGISTERED tool the ceiling allows and this run did not ask for.

    Deliberately not `open_proposal`: the analysing task never registers it, so that refusal
    arrives one layer earlier as `unregistered` and would prove the wrong thing. The property
    under test is task scope narrowing a ceiling, which needs a tool the task can resolve.
    """
    built = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path)
    audit = capture_audit()
    run = _run(
        built.registry,
        audit,
        ceiling={READ_SUBJECT, AUTHOR_FILE},
        requested={READ_SUBJECT},
    )

    result = invoke_tool(run, AUTHOR_FILE, {"path": MODULE, "content": BODY})

    assert not result.allowed
    denials = [e for e in audit.all_entries() if e.payload.get("excluded_by")]
    assert denials and denials[-1].payload["excluded_by"] == "outside_task_scope", (
        "the refusal must name the task scope; 'somewhere said no' sends an operator to the "
        "ceiling record, which is not where the answer is"
    )
    assert not (built.trees.workspace / MODULE).exists()  # type: ignore[union-attr]


def test_row_a9_the_analysing_task_cannot_even_resolve_the_publishing_tool(tmp_path: Path) -> None:
    """Task scope twice over: registration is the first refusal, the ceiling the second.

    Asserted separately from A9's authority refusal because the two are different mechanisms,
    and a change that removed either would leave the other passing.
    """
    analyzer = build_as_entrypoint(role=ANALYZER, tmp_path=tmp_path)
    assert OPEN_PROPOSAL not in analyzer.vocabulary


def test_row_a9_the_publishing_task_cannot_author(tmp_path: Path) -> None:
    """The other direction, which is the one that keeps the credential away from the content."""
    proposer = build_as_entrypoint(role=PROPOSER, tmp_path=tmp_path)
    assert AUTHOR_FILE not in proposer.vocabulary
    assert READ_SUBJECT not in proposer.vocabulary
