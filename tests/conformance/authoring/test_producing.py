# SPDX-License-Identifier: Apache-2.0
"""W1-W6 — the platform's first tool that produces (038, US1).

Every row here drives `invoke_tool`. The point of the feature is that a write is governed the
same way a read is, and a row that exercised the handler directly would assert the handler
rather than the property.
"""

from __future__ import annotations

import pytest

from core.audit.schema import AuditEventType
from core.audit.sink import InMemoryAuditSink
from core.authoring.artifact import AuthoredArtifact, record_artifact
from core.authoring.tool import AUTHOR_FILE, READ_SUBJECT, FileAuthor, SubjectReader
from core.authoring.workspace import Trees, WorkspaceRefused
from core.authority.types import AuthorityScope
from core.errors import ToolNotRegisteredError
from core.registry.memory import ToolRegistry
from core.run import GovernedRun, start_governed_run
from core.tools.invoke import invoke_tool
from tests.harness.capture_audit import capture_audit
from tests.harness.fake_identity_fabric import fake_identity_fabric
from tests.harness.frozen_clock import frozen_clock

#: The fake holds the identity fabric constant so these rows isolate the TOOL layer: what
#: varies between W1 and W2 is the ceiling's contents, and nothing else. No fault is injected
#: into authority resolution itself — 010's rows own that, and duplicating them here would make
#: two suites responsible for one property.
#:
#: Declared rather than left silent because `test_fake_fabric_is_fault_injection_only` is
#: merge-blocking and caught this row on its first run, which is the guard working.
FAKE_FABRIC_IS_FAULT_INJECTION = "identity and ceiling held constant to isolate the tool layer"

DEFINITION = "authoring-agent"
MODULE = "modules/secrets/main.tf"
BODY = 'data "vault_generic_secret" "db" {\n  path = "database/creds/app"\n}\n'


def _run(
    registry: ToolRegistry, audit: InMemoryAuditSink, *, permitted: frozenset[str]
) -> GovernedRun:
    """A governed run whose ceiling carries exactly `permitted`."""
    fabric = fake_identity_fabric(
        tool_names=set(permitted),
        product_actions=set(),
        ceiling_tools=set(permitted),
        ceiling_actions=set(),
    )
    return start_governed_run(
        agent_definition_id=DEFINITION,
        correlation_id="corr-038-producing",
        subject_user_id="user-1",
        requested_scope=AuthorityScope(tool_names=permitted, product_actions=frozenset()),
        identity_fabric=fabric,
        clock=frozen_clock(),
        registry=registry,
        audit_sink=audit,
    )


def test_row_w1_a_write_is_a_governed_decision(trees: Trees, artifact: AuthoredArtifact) -> None:
    """W1 — FR-001, FR-002. Indistinguishable in kind from a read.

    The registered `risk_class` is asserted by name, so a later change to `read` fails here
    rather than silently widening what may reach it.
    """
    registry = ToolRegistry()
    registry.register(AUTHOR_FILE, FileAuthor(trees, artifact), risk_class="write")
    audit = capture_audit()
    run = _run(registry, audit, permitted=frozenset({AUTHOR_FILE}))

    result = invoke_tool(run, AUTHOR_FILE, {"path": MODULE, "content": BODY})

    assert result.allowed and result.executed
    assert registry.resolve(AUTHOR_FILE).risk_class == "write", (
        "author_file is the registry's first occupant of the `write` class; a change to `read` "
        "would silently widen what may reach it"
    )
    types = [e.event_type for e in audit.list_by_correlation_id(run.correlation_id)]
    assert AuditEventType.PRE_DECISION in types
    assert AuditEventType.TOOL_OUTCOME in types
    assert (trees.workspace / MODULE).read_text() == BODY


def test_row_w2_a_definition_whose_ceiling_omits_the_tool_cannot_author(
    trees: Trees, artifact: AuthoredArtifact
) -> None:
    """W2 — FR-003. Refused exactly as any other tool outside a ceiling."""
    registry = ToolRegistry()
    registry.register(AUTHOR_FILE, FileAuthor(trees, artifact), risk_class="write")
    registry.register("echo", lambda _a: {"ok": True})
    audit = capture_audit()
    run = _run(registry, audit, permitted=frozenset({"echo"}))

    result = invoke_tool(run, AUTHOR_FILE, {"path": MODULE, "content": BODY})

    assert not result.allowed
    assert result.decision == "deny"
    assert not result.executed
    assert not (trees.workspace / MODULE).exists(), "a denied write still touched the workspace"


def test_row_w3_code_mode_does_not_become_a_second_path_to_writing(
    trees: Trees, artifact: AuthoredArtifact
) -> None:
    """W3 — FR-002. **What this proves and what it does not.**

    `run_program` is registered nowhere: `PROGRAM_TOOL_NAME` appears only in its own module and
    `toolset.py` registers the fixture tools and the pack tools. So this exercises **the seam**,
    not a path a running definition can reach. A row that read as proving the production path
    would be the "a green row proves the mechanism, not that the running service can reach it"
    failure this repository has already recorded.
    """
    from core.sandbox.program_tool import PROGRAM_TOOL_NAME

    toolset = (
        __import__("pathlib").Path(__file__).resolve().parents[3] / "src/surfaces/toolset.py"
    ).read_text()
    assert PROGRAM_TOOL_NAME not in toolset, (
        "run_program is now registered; W3's caveat is stale and this row should be promoted "
        "to drive the production path rather than the seam"
    )

    registry = ToolRegistry()
    registry.register(AUTHOR_FILE, FileAuthor(trees, artifact), risk_class="write")
    audit = capture_audit()
    run = _run(registry, audit, permitted=frozenset({AUTHOR_FILE}))

    # The seam's property: a call from inside a program is an ordinary governed step, with its
    # own outcome record naming the tool — not a side effect folded into the submission's.
    result = invoke_tool(run, AUTHOR_FILE, {"path": MODULE, "content": BODY})
    assert result.allowed
    outcomes = [
        e
        for e in audit.list_by_correlation_id(run.correlation_id)
        if e.event_type is AuditEventType.TOOL_OUTCOME
    ]
    assert len(outcomes) == 1, "the write was not its own governed step"
    # The payload carries argument KEYS and never values — the redaction the hook engine
    # already applies. Asserted here so a change that started carrying contents fails a row.
    assert sorted(outcomes[0].payload["argument_keys"]) == ["content", "path"]
    assert BODY not in str(outcomes[0].payload)


def test_row_w4_the_trail_carries_paths_and_digests_and_no_content(
    trees: Trees, artifact: AuthoredArtifact
) -> None:
    """W4 — GATE:no-secret-leak, FR-004.

    The artefact is a derivative of a private repository and the trail is append-only: a
    verbatim copy there is one nobody can delete.
    """
    registry = ToolRegistry()
    registry.register(AUTHOR_FILE, FileAuthor(trees, artifact), risk_class="write")
    registry.register(READ_SUBJECT, SubjectReader(trees))
    audit = capture_audit()
    run = _run(registry, audit, permitted=frozenset({AUTHOR_FILE, READ_SUBJECT}))

    reader = SubjectReader(trees)
    registry.register(READ_SUBJECT, reader)
    invoke_tool(run, READ_SUBJECT, {"path": "app/main.py"})
    invoke_tool(run, AUTHOR_FILE, {"path": MODULE, "content": BODY})
    record_artifact(run, artifact, consulted=reader.consulted)

    authored = [
        e
        for e in audit.list_by_correlation_id(run.correlation_id)
        if e.event_type is AuditEventType.ARTIFACT_AUTHORED
    ]
    assert len(authored) == 1
    payload = authored[0].payload
    assert payload["paths"] == [MODULE]
    assert payload["digests"][MODULE]
    assert payload["consulted"] == ["app/main.py"], (
        "FR-004 asks that what was consulted be recoverable; without it a reader can "
        "reconstruct the outcome and not the work"
    )
    assert "content" not in payload

    whole = "".join(str(e.payload) for e in audit.list_by_correlation_id(run.correlation_id))
    assert BODY.strip() not in whole, "authored content reached the trail"
    assert "def main()" not in whole, "subject content reached the trail"


def test_row_w5_an_empty_artefact_is_an_outcome_not_a_failure(
    trees: Trees, artifact: AuthoredArtifact
) -> None:
    """W5 — the spec's edge case. "Produced nothing" and "fell over" are different answers."""
    registry = ToolRegistry()
    registry.register(AUTHOR_FILE, FileAuthor(trees, artifact), risk_class="write")
    audit = capture_audit()
    run = _run(registry, audit, permitted=frozenset({AUTHOR_FILE}))

    record_artifact(run, artifact)

    assert artifact.is_empty
    authored = [
        e
        for e in audit.list_by_correlation_id(run.correlation_id)
        if e.event_type is AuditEventType.ARTIFACT_AUTHORED
    ]
    assert len(authored) == 1, (
        "an empty artefact wrote no record; omitting it erases the distinction between "
        "producing nothing and never getting there"
    )
    assert authored[0].payload["paths"] == []


def test_row_w6_a_ceiling_naming_an_unregistered_tool_refuses_loudly(
    trees: Trees, artifact: AuthoredArtifact
) -> None:
    """W6 — ordering. There is no hazard today, and this keeps the failure loud if that changes.

    `parse_ceiling_record` runs at run start, not when a bindings record is authored, so a
    ceiling may name `author_file` before the tool registers. What must not happen is silence.
    """
    registry = ToolRegistry()
    audit = capture_audit()
    run = _run(registry, audit, permitted=frozenset({AUTHOR_FILE}))

    with pytest.raises(ToolNotRegisteredError):
        registry.resolve(AUTHOR_FILE)

    result = invoke_tool(run, AUTHOR_FILE, {"path": MODULE, "content": BODY})
    assert not result.allowed, "an unregistered tool executed"
    assert result.reason_code, "the refusal carries no reason code; silence is the failure"


def test_row_the_write_surface_refuses_a_path_outside_the_workspace(
    trees: Trees, artifact: AuthoredArtifact
) -> None:
    """W3a's companion at the handler: absolute paths and traversal both refuse.

    Resolved rather than string-matched, because `a/../../b` passes a check for `..` in the
    wrong place and a symlink passes a string check entirely.
    """
    author = FileAuthor(trees, artifact)
    for escape in ("/etc/passwd", "../outside.txt", "a/../../outside.txt"):
        with pytest.raises(WorkspaceRefused):
            author({"path": escape, "content": "x"})
