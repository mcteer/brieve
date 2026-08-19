# SPDX-License-Identifier: Apache-2.0
"""P1/P2 — Propose intake ownership and task requirements (047)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from core.authoring.request import RequestRefused
from core.identity.types import AuthenticatedSubject, SubjectKind
from core.run import RunState
from core.threads.store import InMemoryThreadStore
from surfaces.api.propose import ProposeRequest, propose_for
from surfaces.dispatch.types import RunHandle


@dataclass
class _Done:
    returncode: int
    stdout: str


def _ok_clone(args: list[str], *, timeout: float) -> _Done:
    _ = timeout
    # prepare_authoring_run calls clone then rev-parse
    if args and args[0] == "clone":
        dest = Path(args[-1])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "README.md").write_text("demo\n", encoding="utf-8")
        return _Done(0, "")
    if "rev-parse" in args:
        return _Done(0, "abc123\n")
    return _Done(0, "")


class _FakeDispatcher:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def dispatch(self, **kwargs: Any) -> RunHandle:
        self.calls.append(kwargs)
        return RunHandle(
            run_id=str(kwargs.get("run_id") or kwargs["correlation_id"]),
            correlation_id=str(kwargs["correlation_id"]),
            state=RunState.ACTIVE,
        )


def _subject() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_user_id="operator",
        tenant_id="tenant-a",
        roles=frozenset({"operator"}),
        subject_kind=SubjectKind.HUMAN,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


def test_p2_unowned_repository_refuses_before_dispatch(tmp_path: Path) -> None:
    dispatcher = _FakeDispatcher()
    with pytest.raises(RequestRefused) as refused:
        propose_for(
            subject=_subject(),
            body=ProposeRequest(
                repository="https://github.com/other/not-yours",
                task="add terraform",
            ),
            dispatcher=dispatcher,
            owned_repositories=frozenset({"mcteer/brieve-demo"}),
            platform_tree=tmp_path / "platform",
            acquire_into=tmp_path / "acq",
            clone_runner=_ok_clone,
        )
    assert refused.value.reason_code == "repository_not_owned"
    assert dispatcher.calls == []


def test_p1_owned_repository_dispatches_authoring_tier(tmp_path: Path) -> None:
    (tmp_path / "platform").mkdir()
    dispatcher = _FakeDispatcher()
    store = InMemoryThreadStore()
    accepted = propose_for(
        subject=_subject(),
        body=ProposeRequest(
            repository="https://github.com/mcteer/brieve-demo",
            task="add terraform for the app",
        ),
        dispatcher=dispatcher,
        owned_repositories=frozenset({"mcteer/brieve-demo"}),
        platform_tree=tmp_path / "platform",
        acquire_into=tmp_path / "acq",
        clone_runner=_ok_clone,
        thread_store=store,
    )
    assert accepted.run_id
    assert dispatcher.calls
    call = dispatcher.calls[0]
    assert call["job_id"] == "authoring-tier"
    assert "subject_path" in (call.get("meta") or {})
    assert call["agent_definition_id"] == "authoring-agent"
    recorded = store.get_run_input(run_id=accepted.run_id)
    assert recorded is not None
    assert "add terraform for the app" in recorded.message
    assert "mcteer/brieve-demo" in recorded.message


def test_empty_task_refused(tmp_path: Path) -> None:
    with pytest.raises(RequestRefused):
        propose_for(
            subject=_subject(),
            body=ProposeRequest(repository="mcteer/brieve-demo", task="   "),
            dispatcher=_FakeDispatcher(),
            owned_repositories=frozenset({"mcteer/brieve-demo"}),
            platform_tree=tmp_path / "platform",
            acquire_into=tmp_path / "acq",
            clone_runner=_ok_clone,
        )


def test_chat_message_dispatches_authoring_tier(tmp_path: Path) -> None:
    (tmp_path / "platform").mkdir()
    dispatcher = _FakeDispatcher()
    store = InMemoryThreadStore()
    message = (
        "I need you to create a terraform template that will provision "
        "the appropriate infrastructure in AWS for this application: "
        "https://github.com/mcteer/brieve-demo"
    )
    accepted = propose_for(
        subject=_subject(),
        body=ProposeRequest(message=message),
        dispatcher=dispatcher,
        owned_repositories=frozenset({"mcteer/brieve-demo"}),
        platform_tree=tmp_path / "platform",
        acquire_into=tmp_path / "acq",
        clone_runner=_ok_clone,
        thread_store=store,
    )
    assert accepted.run_id
    assert dispatcher.calls
    assert dispatcher.calls[0]["job_id"] == "authoring-tier"
    recorded = store.get_run_input(run_id=accepted.run_id)
    assert recorded is not None
    assert recorded.message == message


def test_message_without_url_refused(tmp_path: Path) -> None:
    with pytest.raises(RequestRefused) as refused:
        propose_for(
            subject=_subject(),
            body=ProposeRequest(message="please add terraform somewhere"),
            dispatcher=_FakeDispatcher(),
            owned_repositories=frozenset({"mcteer/brieve-demo"}),
            platform_tree=tmp_path / "platform",
            acquire_into=tmp_path / "acq",
            clone_runner=_ok_clone,
        )
    assert refused.value.reason_code == "repository_required"


def test_proposer_marks_the_run_complete_when_a_pr_url_is_written() -> None:
    """A PR on RESULT_KEY with no terminal outcome is invisible to get_run_result.

    The page then treats Nomad's completed allocation as 'ended without a pull request'.
    """
    source = (
        Path(__file__).resolve().parents[3] / "src" / "surfaces" / "dispatch" / "entrypoint.py"
    ).read_text(encoding="utf-8")
    assert "payload[RESULT_KEY] = {" in source
    assert '"pr_url": pr_url' in source
    publish = source.split("047 — success payload", 1)[1].split("def resume_dispatched_run", 1)[0]
    assert "RunState.COMPLETED.value" in publish
    assert "checkpoint_run(" in publish


def test_proposer_does_not_restore_the_analyzer_payload_after_publish() -> None:
    """After open_proposal writes pr_url, continue used to re-save checkpoint.payload.

    That snapshot is the analyzer handoff (no URL). Nomad then reports complete, and
    the Build page says 'Ended without a pull request' while GitHub has the PR.
    """
    source = (
        Path(__file__).resolve().parents[3] / "src" / "surfaces" / "dispatch" / "entrypoint.py"
    ).read_text(encoding="utf-8")
    body = source.split("def continue_dispatched_run(", 1)[1].split(
        "def _publish_the_proposal(", 1
    )[0]
    assert "if published != 0:" in body
    success_arm = body.split("if published != 0:", 1)[1]
    # The success path must not re-save the analyzer snapshot. The else of this
    # proposer arm is the non-proposer continuation, which may still checkpoint.
    before_else = success_arm.split("else:", 1)[0]
    assert "payload=dict(checkpoint.payload)" not in before_else


def test_api_job_copies_packs_so_propose_can_read_authoring_declarations() -> None:
    """Build refused every pack, including terraform, when the API allocation had no packs/.

    ``packs_declaring_authoring()`` reads ``pack.toml`` from the tree next to ``src/``. In
    the allocation that is ``/repo/packs``. The job copied ``src`` and ``corpus`` and not
    ``packs``, so the set was empty and every Build failed ``pack_declares_no_authoring`` —
    including the terraform pack that has declared ``author-module`` since 038.

    Packs ship in the tree. The copy is unconditional: ``|| true`` would hide a missing
    tree the same way the missing copy hid itself.
    """
    spec = Path(__file__).resolve().parents[3] / "infra" / "jobs" / "api.nomad.hcl"
    text = spec.read_text(encoding="utf-8")
    assert "cp -a /src/packs /repo/" in text, (
        f"{spec} does not copy packs into the allocation; Build will refuse every pack as "
        "undeclared regardless of what pack.toml says"
    )
    assert "cp -a /src/packs /repo/ 2>/dev/null || true" not in text, (
        f"{spec} copies packs optionally; a missing tree would start the API and refuse "
        "every Build instead of failing the allocation"
    )
