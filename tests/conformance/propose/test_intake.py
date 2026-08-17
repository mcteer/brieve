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
