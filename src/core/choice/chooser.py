# SPDX-License-Identifier: Apache-2.0
"""What a model was asked, what it answered, and which model was asked at all.

**The seam, and it is deliberately not `pydantic_ai.models.Model`** (research F7). A double
satisfying the framework's provider interface would have to imitate its message protocol, so
what the lane proved would be our fake's fidelity to a dependency's internals rather than a
governance property. :class:`Chooser` is one method, and the substitution happens where the
binding resolves a model — which is the only place it can happen without letting the loop be
tested through a path production never takes (research F5).

**No framework import lives here, or may.** Principle I: the core never imports an agent
framework. The provider-backed implementation is `adapters.model_chooser`, on the same
division `core.evals.scoring` draws against `adapters.anthropic_scorer` — protocol in core,
provider in the adapter, and the callers cannot tell which they hold.

**This module never decides permission.** It asks, carries the answer, and records what
happened. Whether a named tool may run is `invoke_tool`'s answer and no one else's, which is
what makes FR-004's "refused by the *existing* enforcement" a fact about the code rather than
a claim about it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from core.audit.schema import AuditEventType
from core.authority.errors import ResolutionRefused
from core.authority.matrix import (
    MODEL_IDENTIFIER,
    Role,
    parse_matrix_record,
    validate_binding_map,
)

#: The role a tool choice is made under (ADR-0039's closed vocabulary).
#:
#: `plan`, and the alternatives are worth naming. `ask` is answering a person; `write` is
#: performing the change, which is what the *chosen tool* then does under its own authority;
#: `judge` and `summarize` are evaluation. Deciding what to do next is planning, and binding
#: it to `write` would mean a definition permitted to choose was thereby permitted to act —
#: two authorizations collapsed into one, which is the failure ADR-0039's third dimension
#: exists to prevent.
CHOICE_ROLE: Role = "plan"


class ChoiceOutcome(StrEnum):
    """What became of one attempt at one step. The closed payload vocabulary of `TOOL_CHOSEN`.

    Six values rather than a boolean, because a reader asking "why did this run stop" needs
    the four terminal ones to be different from each other. A single `refused` covering a
    malformed answer and an over-reach would report a model that misunderstood its task as a
    model that reached past its ceiling.
    """

    #: Named, permitted, executed.
    CHOSEN = "chosen"
    #: Named, and refused by the existing enforcement. Recorded per attempt (FR-004c).
    REFUSED = "refused"
    #: Not a tool name at all. Distinct from REFUSED — see the class docstring.
    MALFORMED = "malformed"
    #: The model named nothing. Terminal, and never defaulted to a tool.
    EMPTY = "empty"
    #: The re-choice bound ran out. Terminal, and recorded rather than left to be inferred
    #: from a run of REFUSED entries that simply stops.
    EXHAUSTED = "exhausted"
    #: No model was asked, because this run invokes no tools (FR-002a/FR-002b).
    NOT_CONSULTED = "not_consulted"


@dataclass(frozen=True)
class Choice:
    """What a model named at a step, and what became of it.

    The data model's first entity. Held in memory only for the duration of the step — the
    trail is where a choice actually lives, and a second store would eventually disagree with
    it. ``permitted`` is not a field here on purpose: it is implied by ``outcome``, and
    carrying it separately would invite something to set it, which is the permission decision
    leaking back into the choosing code.
    """

    step_index: int
    attempt: int
    named: str
    outcome: ChoiceOutcome
    model: str


@dataclass(frozen=True)
class ChoiceRequest:
    """What a chooser is given. The ceiling, never the catalogue.

    ``permitted`` is what the definition allows, so a model is not shown what it may not
    have. That is not enforcement — enforcement is `invoke_tool`'s — it is the difference
    between a model choosing badly and a model being invited to.
    """

    #: What the run was started to do.
    task: str
    #: The tools this definition permits, sorted for a stable prompt.
    permitted: Sequence[str]
    #: Which step is being decided.
    step_index: int
    #: Which attempt at this step, from zero.
    attempt: int
    #: Tools already refused **at this step**, with the reason the core gave. Carried so the
    #: denial teaches rather than only blocks (FR-004a).
    refused: Sequence[tuple[str, str]] = ()


class Chooser(Protocol):
    """Answers "which tool next", or nothing at all.

    Returning the empty string is a real answer and means *nothing to do* — the run ends in a
    recorded terminal state rather than defaulting to a tool. Any other string is passed on
    verbatim; deciding whether it names a real tool, and whether that tool is permitted, is
    not this interface's job.
    """

    def choose(self, request: ChoiceRequest) -> str: ...


class ChooserUnavailable(Exception):
    """The provider could not be reached, or answered in a way that is not usable.

    **Terminal, with no fallback** (FR-007). The tempting behaviour — fall back to a
    deterministic sequence when the provider is down — is this feature's own defect preserved
    as a feature: the platform would revert to a scripted sequence at exactly the moment
    nobody is watching, while every governance row kept passing (research F4).
    """

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


def resolve_bound_model(
    identity_fabric: Any,
    *,
    agent_definition_id: str,
    role: Role = CHOICE_ROLE,
) -> str:
    """The model this definition binds for ``role``, validated before any provider call.

    FR-005 and FR-006, and the ordering is the requirement: a model the matrix does not
    qualify must not be *reached*, not merely not used. So the binding map is read, the matrix
    is parsed, and the cell is validated — all of it before anything constructs a client.

    **Never defaults.** No binding for the role refuses the run. A default model is an
    ungoverned model choice, which is the same defect as an ungoverned tool choice one level
    up, and it is the defect ADR-0022 and ADR-0039 were written to prevent.

    **Deliberately unlike `manufacture._resolve_binding_map`, which goes inert when the fabric
    supplies no matrix.** That inertness is correct where it lives: it keeps every pre-013 run
    working, and a fabric with no matrix is not a fabric whose cells are all unqualified. Here
    the opposite is correct, because reaching this function means a run is about to consult a
    model — and a run consulting a model no record qualified is precisely what FR-006 forbids.
    The two postures do not conflict; a run that invokes no tools never reaches this line.
    """
    read_bindings = getattr(identity_fabric, "resolve_definition_bindings", None)
    read_matrix = getattr(identity_fabric, "read_matrix", None)
    if read_bindings is None or read_matrix is None:
        raise ResolutionRefused(
            f"definition {agent_definition_id!r} cannot resolve a model for role {role!r}: "
            f"this identity fabric supplies no binding map or no matrix, and a run that "
            f"consults a model without one would be choosing a model ungoverned",
            reason_code="no_binding_for_role",
        )

    bindings = read_bindings(agent_definition_id)
    reference = bindings.binding_map.get(role, "")
    if not reference:
        raise ResolutionRefused(
            f"definition {agent_definition_id!r} binds no model for role {role!r}; the run "
            f"is refused rather than defaulted, because a defaulted model is an ungoverned "
            f"model choice",
            reason_code="no_binding_for_role",
        )

    cells = parse_matrix_record(read_matrix())
    # Raises `unqualified_cell` / `cell_withdrawn` / `malformed_record`, each of which is a
    # different problem with a different fix — carried through rather than flattened, exactly
    # as `manufacture` carries them.
    validate_binding_map({role: reference}, cells, agent_definition_id=agent_definition_id)

    model = cells[reference].model
    if not MODEL_IDENTIFIER.match(model):
        # Belt and braces: `_parse_cell` already refuses an identifier that is not
        # provider/model@version. Re-checked here because everything downstream splits on
        # that shape, and a malformed identifier reaching a client would send a request to
        # whatever the string happened to mean.
        raise ResolutionRefused(
            f"cell {reference!r} names model {model!r}, which is not provider/model@version",
            reason_code="malformed_record",
        )
    return model


def record_choice(
    run: Any,
    *,
    step_index: int,
    attempt: int,
    model: str,
    named: str,
    outcome: ChoiceOutcome,
) -> None:
    """Write one `TOOL_CHOSEN` entry onto the run's own trail.

    **Carries the run's correlation id**, so the choice joins the same trail the tool bracket
    it caused joins — prompt → choice → hook decision → tool call → outcome, walkable in both
    directions (Principle IX).

    **Not swallowed.** A choice nobody can see is the record FR-009 exists to create, and a
    run that made one and failed to record it is indistinguishable from a run that was handed
    its tool. The same reasoning `MATRIX_FALLBACK` is written under, one level down.

    **What is absent is load-bearing**: no reasoning, no prompt, no model output beyond the
    name. The model may have read a secret out of a tool result, and an append-only trail is
    the one place that must never be written to (T013).
    """
    run.audit_sink.append_event(
        correlation_id=run.correlation_id,
        tenant_id=run.tenant_id,
        event_type=AuditEventType.TOOL_CHOSEN,
        payload={
            "run_id": run.run_id or run.correlation_id,
            "step_index": step_index,
            "attempt": attempt,
            "model": model,
            "named": named,
            "outcome": str(outcome),
        },
    )


def is_tool_name(named: str, known: Sequence[str] | frozenset[str]) -> bool:
    """Whether ``named`` is a tool at all — measured against the REGISTRY, not the ceiling.

    The distinction FR-004 and the spec's edge cases both turn on, and getting the argument
    wrong here would erase it. A name outside the platform's whole vocabulary is a model that
    misunderstood its task; a *real* tool outside this definition's ceiling is a model that
    understood it and reached past what it may have. They land in different `ChoiceOutcome`
    values because those are different things to whoever reads the trail — and because only
    the second is a governance event.

    So ``known`` is `registry.tool_names()`. Passing the permitted set instead would collapse
    every over-reach into ``malformed`` and, worse, would answer the permission question here
    — in the choosing code, which is the one place the contract says must never answer it.
    """
    return bool(named) and named in set(known)


__all__ = [
    "CHOICE_ROLE",
    "Choice",
    "ChoiceOutcome",
    "ChoiceRequest",
    "Chooser",
    "ChooserUnavailable",
    "is_tool_name",
    "record_choice",
    "resolve_bound_model",
]
