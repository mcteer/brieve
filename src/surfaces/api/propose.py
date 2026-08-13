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
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from core.authoring.owned import owned_repositories_from_env, packs_declaring_authoring
from core.authoring.progress import PROGRESS_KEY, PhaseName, advance, initial_progress
from core.authoring.repository_id import normalize_repository_url
from core.authoring.request import AuthoringRequest, RequestRefused
from core.identity.types import AuthenticatedSubject
from surfaces.api.dependencies import SubjectDep
from surfaces.dispatch.authoring_dispatch import prepare_authoring_run
from surfaces.dispatch.nomad import AUTHORING_JOB_ID
from surfaces.dispatch.types import RunHandle

AUTHORING_DEFINITION_ID = "authoring-agent"
AUTHORING_TOOLS = frozenset({"read_subject", "author_file", "open_proposal"})


class ProposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository: str = Field(min_length=1)
    task: str = Field(min_length=1)
    correlation_id: str | None = None


class ProposeAccepted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    correlation_id: str
    propose_progress: dict[str, Any]


def _mint() -> str:
    return f"propose-{secrets.token_hex(8)}"


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
) -> ProposeAccepted:
    """Validate, acquire, dispatch — or raise ``RequestRefused`` / ``DispatchError``."""
    repo = normalize_repository_url(body.repository)
    task = body.task.strip()
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

    into = acquire_into or Path(tempfile.mkdtemp(prefix="propose-"))
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

    progress = advance(initial_progress(), into=PhaseName.RESEARCH)
    handle: RunHandle = dispatcher.dispatch(
        correlation_id=correlation_id,
        subject_user_id=subject.subject_user_id,
        tenant_id=subject.tenant_id,
        agent_definition_id=AUTHORING_DEFINITION_ID,
        requested_tools=AUTHORING_TOOLS,
        subject_roles=frozenset(subject.roles),
        packs=frozenset({request.pack}),
        invoke_tools=True,
        job_id=AUTHORING_JOB_ID,
        meta={
            "subject_path": prepared.meta["subject_path"],
            "packs": request.pack,
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
    def propose(subject: SubjectDep, body: ProposeRequest) -> ProposeAccepted:
        if dispatcher is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "propose dispatcher unavailable"
            )
        try:
            return propose_for(
                subject=subject,
                body=body,
                dispatcher=dispatcher,
                owned_repositories=owned_repositories,
                platform_tree=platform_tree,
            )
        except RequestRefused as refused:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN
                if refused.reason_code == "repository_not_owned"
                else status.HTTP_400_BAD_REQUEST,
                str(refused),
            ) from refused
        except Exception as exc:  # noqa: BLE001 — surface must not 500 with internals
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "propose could not be started"
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
