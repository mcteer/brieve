# SPDX-License-Identifier: Apache-2.0
"""Agent definitions — the public view.

**What a person may see and what a person may start are different questions**, and this
surface answers both while conflating neither. A definition a subject cannot start still
appears, marked: omitting it presents a world in which the agent does not exist, so nobody
thinks to ask for access, and "request access to the thing you cannot see" is not a
workflow.

That is a wider disclosure than this platform makes anywhere else, accepted deliberately
and bounded twice. Never any credential-issuance detail — no ceiling policies, no secret
paths, which are the other jurisdiction (ADR-0050) and nobody's business here. And never
across tenants: within a tenant existence is discoverable, across tenants it is not.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from core.authority.errors import ResolutionRefused
from core.identity.types import AuthenticatedSubject
from surfaces.api.dependencies import DefinitionsDep, SubjectDep


class AgentDefinitionView(BaseModel):
    """One definition as a caller sees it.

    Display fields plus one computed flag. Deliberately absent: `ceiling_policies`,
    `allowed_paths`, and anything else from the credential-issuance jurisdiction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_definition_id: str
    description: str = ""
    owner: str = ""
    may_start: bool
    #: Which products this definition works on — additive, read-only, empty when unknown (034).
    #:
    #: The portal draws a product identity from this, which is the whole reason it exists: the
    #: platform already knows a definition's packs, and the page had no way to say so. It is a
    #: DISPLAY fact and grants nothing; `may_start` above remains the only authority claim here.
    #:
    #: Defaulted so every existing constructor stands, and served from this transport-shared
    #: view so MCP carries it by construction rather than by a second implementation agreeing.
    packs: tuple[str, ...] = ()


class AgentDefinitionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    definitions: list[AgentDefinitionView]


def _may_start(subject_scope: Any, ceiling: Any) -> bool:
    """Whether this subject could start an agent under this ceiling.

    **Intersection non-empty, not subset.** 002 refuses only requests that *exceed* scope,
    so a subject covering part of a ceiling can start that agent with a narrower request.
    Requiring subset would mark startable agents unavailable — the inverse of the
    disclosure decision, and a person told they cannot use something they can.
    """
    overlap = subject_scope.intersect(ceiling)
    return bool(overlap.tool_names or overlap.product_actions)


def definition_views(
    *,
    subject: AuthenticatedSubject,
    fabric: Any,
) -> list[AgentDefinitionView]:
    """Every definition, each marked with whether this subject may start it.

    Transport-independent, so MCP reaches this rather than reimplementing it — and so the
    disclosure rule is written once. A resolution failure refuses rather than returning an
    unmarked or empty list: both read as fail-closed and are wrong answers about a person's
    authority (FR-018).
    """
    from core.authority.vault_fabric import SubjectScopedVaultFabric, VaultIdentityFabric

    # The production assembly hands in a fabric that deliberately refuses to invent roles.
    # The verified subject already carries them — scope to those rather than asking the
    # base fabric to re-derive identity from a user id alone.
    if isinstance(fabric, VaultIdentityFabric) and not isinstance(fabric, SubjectScopedVaultFabric):
        fabric = SubjectScopedVaultFabric(
            roles=subject.roles,
            credentials=fabric._credentials,
            known_tools=fabric._known_tools,
            known_actions=fabric._known_actions,
            entitlement_source=fabric._entitlements,
        )

    scope = fabric.resolve_user_scope(subject.subject_user_id)

    views: list[AgentDefinitionView] = []
    for definition_id in fabric.list_definitions():
        try:
            ceiling = fabric.resolve_ceiling(definition_id)
        except ResolutionRefused:
            # A definition whose ceiling cannot be read is shown as unstartable rather than
            # hidden. Hiding it would be the omission this surface exists to avoid, and
            # claiming it startable would be a promise the platform cannot keep.
            views.append(AgentDefinitionView(agent_definition_id=definition_id, may_start=False))
            continue
        views.append(
            AgentDefinitionView(
                agent_definition_id=definition_id,
                may_start=_may_start(scope, ceiling),
                packs=_packs(fabric, definition_id),
            )
        )
    return views


def _packs(fabric: Any, definition_id: str) -> tuple[str, ...]:
    """Which products this definition works on, or empty when that is not knowable (034).

    **Every way of not knowing is the same answer**, and the shape is deliberate. A fabric
    that has no binding resolver at all (the hermetic harness had none until this landed), a
    resolution that refuses, and a definition that genuinely declares no pack all return `()`.
    The portal draws a product stripe from this, so unknown must mean *no stripe* rather than
    *a wrong stripe* — and it must never mean an exception, because a definition list is not
    the place to discover that a binding record is unreadable.

    Read-only and additive: this tells a reader which product a definition is about. It grants
    nothing, and `may_start` above remains the only authority claim on this view.
    """
    resolve = getattr(fabric, "resolve_definition_bindings", None)
    if resolve is None:
        return ()
    try:
        return tuple(sorted(resolve(definition_id).packs))
    except Exception:  # noqa: BLE001 — see the docstring: unknown is a state, not a failure
        return ()


def build_router() -> APIRouter:
    router = APIRouter(tags=["definitions"])

    @router.get("/agent-definitions", response_model=AgentDefinitionListResponse)
    def list_agent_definitions(
        subject: SubjectDep,
        fabric: DefinitionsDep,
    ) -> AgentDefinitionListResponse:
        """What exists, and which of it this subject may start."""
        try:
            return AgentDefinitionListResponse(
                definitions=definition_views(subject=subject, fabric=fabric)
            )
        except ResolutionRefused as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "definitions unavailable"
            ) from exc

    @router.get("/agent-definitions/{agent_definition_id}", response_model=AgentDefinitionView)
    def get_agent_definition(
        agent_definition_id: str,
        subject: SubjectDep,
        fabric: DefinitionsDep,
    ) -> AgentDefinitionView:
        """One definition's public view."""
        try:
            views = definition_views(subject=subject, fabric=fabric)
        except ResolutionRefused as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "definitions unavailable"
            ) from exc

        for view in views:
            if view.agent_definition_id == agent_definition_id:
                return view
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such agent definition")

    return router
