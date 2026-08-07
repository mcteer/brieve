# SPDX-License-Identifier: Apache-2.0
"""What an authoring run's registry holds, and which task holds it (041, FR-001/003).

**038 built the tier and registered none of it.** `register_authoring_tools` and
`register_proposal_tool` had zero callers anywhere — not in `src/`, not in `tests/` — so a
ceiling naming `author_file` refused `unknown_ceiling_entry`, because the vocabulary a ceiling
may name is *derived from what registered*. This module is the caller they never had.

**Importable rather than inline, and that is a row's requirement rather than a preference.**
The rows proving reachability must construct the registry with this branch on and with it off,
in one process — there is no pre-041 tree to run against (040's M3 named this trap: in a single
checkout there is no "before" to execute). A private block inside `main()` offers nothing to
call twice.

**Registration stays per run.** Both analyzer handlers hold run-scoped state — the workspace
they may write to, and the artefact they accumulate — so a module-level table would either
share a workspace between runs or need a lookup amounting to the same thing with more steps.
That does not weaken the opt-in property: registration makes a name *resolvable*, and the
**ceiling** still decides whether this run may reach it. A definition whose ceiling omits
`author_file` has no authoring even though the registry knows the name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.authoring.artifact import AuthoredArtifact
from core.authoring.tool import (
    AUTHOR_FILE,
    OPEN_PROPOSAL,
    READ_SUBJECT,
    AuthoringTools,
    register_authoring_tools,
    register_proposal_tool,
)
from core.authoring.workspace import Trees
from core.registry.memory import ToolRegistry

#: The env var the jobspec already sets and the entrypoint never read until 041.
AUTHORING_ROLE_ENV = "HARNESS_AUTHORING_ROLE"

#: The analysing half: reads the mounted subject, writes into its workspace, publishes nothing.
ANALYZER = "analyzer"

#: The publishing half: holds the credential, never mounts the subject, authors nothing.
PROPOSER = "proposer"

#: Where the jobspec mounts the subject, read-only. Fixed rather than configurable: the mount
#: target is a property of the tier's jobspec, and a run that could name its own would be a run
#: that could name the platform's tree.
SUBJECT_MOUNT = Path("/subject")


@dataclass(frozen=True)
class AuthoringRegistration:
    """What was registered for this task, and the handles a caller needs afterwards.

    ``tools`` is None for the proposer: it registers no analyzer handlers, and returning an
    empty stand-in would let a caller read `consulted` off the publishing task and get an
    answer that means nothing.
    """

    role: str
    registered: frozenset[str]
    tools: AuthoringTools | None = None


def authoring_role(env: dict[str, str]) -> str | None:
    """The role this task runs as, or None when it is not an authoring task at all.

    Read from the environment rather than inferred from which tools a ceiling grants. The
    jobspec **declares** it, and an inference would turn a coincidence into a role — the same
    mistake D1's comment refuses for resumes.
    """
    role = (env.get(AUTHORING_ROLE_ENV) or "").strip().lower()
    return role if role in (ANALYZER, PROPOSER) else None


def authoring_registry_for(
    role: str,
    *,
    registry: ToolRegistry,
    trees: Trees | None = None,
    artifact: AuthoredArtifact | None = None,
    proposal_handler: Any = None,
    proposal_observer: Any = None,
) -> AuthoringRegistration:
    """Register the tools this authoring task may resolve, and only those.

    **Task scope is expressed by what is registered here, not only by the ceiling.** The
    analyzer never registers `open_proposal`; the proposer never registers the analyzer pair.
    That is the same separation the jobspec makes with `RUN_REQUESTED_TOOLS`, made twice on
    purpose — a task that forgot its scope declaration still cannot resolve the other half.

    Raises:
        ValueError: an analyzer without trees, or a proposer without a handler. Refusing here
            rather than registering a half-built tool: a registered name whose handler is None
            fails at call time, which is after the ceiling has already said yes.
    """
    if role == ANALYZER:
        if trees is None or artifact is None:
            raise ValueError(
                "an analyzer registration needs this run's trees and artefact; both handlers "
                "hold run-scoped state and there is no correct default for either"
            )
        tools = register_authoring_tools(registry, trees=trees, artifact=artifact)
        return AuthoringRegistration(
            role=ANALYZER,
            registered=frozenset({READ_SUBJECT, AUTHOR_FILE}),
            tools=tools,
        )
    if role == PROPOSER:
        if proposal_handler is None or proposal_observer is None:
            raise ValueError(
                "a proposer registration needs a publish handler and its observer; "
                "`open_proposal` is non-repeatable, and one without an observer resolves "
                "CANNOT_DETERMINE and parks the run"
            )
        register_proposal_tool(registry, handler=proposal_handler, observer=proposal_observer)
        return AuthoringRegistration(role=PROPOSER, registered=frozenset({OPEN_PROPOSAL}))
    raise ValueError(f"unknown authoring role {role!r}; expected {ANALYZER!r} or {PROPOSER!r}")


def trees_for(workspace: Path, *, subject: Path = SUBJECT_MOUNT) -> Trees:
    """This run's subject and workspace, resolved together.

    Held as a pair because every containment property in the tier is a statement about the
    *relationship* between the two, and two loose paths are two things a caller can get out of
    step.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    return Trees(subject=subject.resolve(), workspace=workspace.resolve())


__all__ = [
    "ANALYZER",
    "AUTHORING_ROLE_ENV",
    "PROPOSER",
    "SUBJECT_MOUNT",
    "AuthoringRegistration",
    "authoring_registry_for",
    "authoring_role",
    "trees_for",
]
