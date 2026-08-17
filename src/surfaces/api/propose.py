# SPDX-License-Identifier: Apache-2.0
"""Propose intake — repository URL + task → authoring-tier dispatch (047).

**Not a thread turn.** Threads select an agent definition; Propose builds an
``AuthoringRequest``, acquires the subject outside the hardened tier, and dispatches
``authoring-tier`` with ``subject_path``.
"""

from __future__ import annotations

import os
import secrets
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from core.authoring.owned import owned_repositories_from_env, packs_declaring_authoring
from core.authoring.progress import PROGRESS_KEY, PhaseName, advance, initial_progress
from core.authoring.repository_id import (
    extract_propose_from_message,
    normalize_repository_url,
)
from core.authoring.request import AuthoringRequest, RequestRefused
from core.identity.types import AuthenticatedSubject
from core.threads.records import RunInput
from core.threads.store import ThreadStore
from surfaces.api.dependencies import SubjectDep, ThreadStoreDep
from surfaces.dispatch.authoring_dispatch import prepare_authoring_run
from surfaces.dispatch.nomad import AUTHORING_JOB_ID, DispatchError
from surfaces.dispatch.types import RunHandle

AUTHORING_DEFINITION_ID = "authoring-agent"
AUTHORING_TOOLS = frozenset({"read_subject", "author_file", "open_proposal"})


class ProposeRequest(BaseModel):
    """Chat bubble or structured fields — portal sends ``message`` only (047)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    message: str | None = None
    repository: str | None = None
    task: str | None = None
    correlation_id: str | None = None


class ProposeAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    correlation_id: str
    propose_progress: dict[str, Any]


def _mint() -> str:
    return f"propose-{secrets.token_hex(8)}"


def _repository_and_task(body: ProposeRequest) -> tuple[str, str]:
    if body.message and body.message.strip():
        return extract_propose_from_message(body.message)
    if body.repository and body.task:
        return body.repository, body.task
    raise RequestRefused(
        "send a message that includes a GitHub repository URL and what should change",
        reason_code="task_required",
    )


def propose_for(
    *,
    subject: AuthenticatedSubject,
    body: ProposeRequest,
    dispatcher: Any,
    owned_repositories: frozenset[str] | None = None,
    platform_tree: Path | None = None,
    acquire_into: Path | None = None,
    clone_token: str | None = None,
    clone_runner: Any = None,
    thread_store: ThreadStore | None = None,
) -> ProposeAccepted:
    """Validate, acquire, dispatch — or raise ``RequestRefused`` / ``DispatchError``.

    ``thread_store`` holds the run's task text under ``run_id`` (same path thread turns use).
    The analyzer's chooser reads it via ``resolve_run_input`` — without this write the model
    sees ``Task: (none supplied)`` and ends the run with ``empty``.
    """
    repo_raw, task = _repository_and_task(body)
    repo = normalize_repository_url(repo_raw)
    task = task.strip()
    if not task:
        raise RequestRefused("a task is required", reason_code="task_required")

    owned = owned_repositories if owned_repositories is not None else owned_repositories_from_env()
    correlation_id = (body.correlation_id or "").strip() or _mint()
    request = AuthoringRequest(
        correlation_id=correlation_id,
        tenant_id=subject.tenant_id,
        requester=subject.subject_user_id,
        target_repository=repo,
        task=task,
        pack="terraform",
    )

    # Checkouts must land where Nomad can bind-mount them into authoring-tier. Container-local
    # /tmp is invisible to the scheduler; PROPOSE_ACQUIRE_ROOT is that shared host path (or a
    # bind of it). PROPOSE_SUBJECT_HOST_ROOT rewrites the path Nomad sees when the API's view
    # of the directory differs from the client's (Docker bind target vs host source).
    if acquire_into is None:
        acquire_root = Path(os.environ.get("PROPOSE_ACQUIRE_ROOT", tempfile.gettempdir()))
        acquire_root.mkdir(parents=True, exist_ok=True)
        into = Path(tempfile.mkdtemp(prefix="propose-", dir=str(acquire_root)))
    else:
        into = acquire_into
    platform = platform_tree or Path(os.environ.get("PROPOSE_PLATFORM_TREE", "/repo"))

    prepared = prepare_authoring_run(
        request,
        run_tenant_id=subject.tenant_id,
        owned_repositories=owned,
        packs_declaring_authoring=packs_declaring_authoring(),
        into=into,
        platform_tree=platform,
        token=clone_token,
        runner=clone_runner,
    )

    subject_path = prepared.meta["subject_path"]
    host_root = os.environ.get("PROPOSE_SUBJECT_HOST_ROOT", "").strip()
    container_root = os.environ.get("PROPOSE_ACQUIRE_ROOT", "").strip()
    if host_root and container_root:
        container = str(Path(container_root).resolve())
        host = str(Path(host_root))
        resolved = str(Path(subject_path).resolve())
        if resolved == container or resolved.startswith(container + os.sep):
            subject_path = host + resolved[len(container) :]

    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    # The person's words for the chooser — not jobspec meta (012: free text must not enter
    # Nomad). Same store thread turns use; run_id equals correlation_id for Propose.
    if thread_store is None:
        raise RequestRefused(
            "Build could not record its task; refusing rather than dispatching a run the "
            "model cannot see",
            reason_code="task_unrecordable",
        )
    message = (body.message or "").strip() or f"Repository: {repo}\n\n{task}"
    thread_store.put_run_input(
        RunInput(
            run_id=correlation_id,
            message=message,
            context_run_ids=(),
            created_at=datetime.now(UTC),
        )
    )
    # Steps + invoke_tools: the analyzer consults the write-cell model per step. steps=0 with
    # invoke_tools would take the "invoke every tool once with empty args" path and die on
    # author_file before any research happens.
    handle: RunHandle = dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id=subject.subject_user_id,
        tenant_id=subject.tenant_id,
        agent_definition_id=AUTHORING_DEFINITION_ID,
        requested_tools=AUTHORING_TOOLS,
        subject_roles=frozenset(subject.roles),
        packs=frozenset({request.pack}),
        invoke_tools=True,
        steps=20,
        job_id=AUTHORING_JOB_ID,
        meta={
            "subject_path": subject_path,
            "packs": request.pack,
            "target_repository": prepared.meta["target_repository"],
            "base_commit": prepared.meta["base_commit"],
        },
    )
    return ProposeAccepted(
        run_id=handle.run_id,
        correlation_id=handle.correlation_id,
        propose_progress=progress.to_payload(),
    )


def build_router(
    *,
    dispatcher: Any,
    owned_repositories: frozenset[str] | None = None,
    platform_tree: Path | None = None,
) -> APIRouter:
    router = APIRouter(tags=["propose"])

    @router.post("/propose", response_model=ProposeAccepted, status_code=status.HTTP_202_ACCEPTED)
    def propose(
        subject: SubjectDep, body: ProposeRequest, store: ThreadStoreDep
    ) -> ProposeAccepted:
        if dispatcher is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Build could not be started")
        try:
            return propose_for(
                subject=subject,
                body=body,
                dispatcher=dispatcher,
                owned_repositories=owned_repositories,
                platform_tree=platform_tree,
                thread_store=store,
            )
        except RequestRefused as refused:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN
                if refused.reason_code == "repository_not_owned"
                else status.HTTP_400_BAD_REQUEST,
                str(refused),
            ) from refused
        except DispatchError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Build could not be started"
            ) from exc
        except Exception as exc:  # noqa: BLE001 — surface must not 500 with internals
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Build could not be started"
            ) from exc

    return router


__all__ = [
    "AUTHORING_DEFINITION_ID",
    "AUTHORING_TOOLS",
    "PROGRESS_KEY",
    "ProposeAccepted",
    "ProposeRequest",
    "build_router",
    "propose_for",
]
