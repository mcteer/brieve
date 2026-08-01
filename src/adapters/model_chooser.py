# SPDX-License-Identifier: Apache-2.0
"""The first production caller of ``build_governed_agent``, ten features after it was written.

`adapters/pydantic_ai/agent.py` has taken a model since 004 and installs governance outermost
so nothing downstream can produce an ungoverned execution. Every conformance row about
interception, ordering, and refusal passed against it. **No production caller ever passed it a
model** — a dispatched run picked its tool with ``tools[step % len(tools)]`` — so the whole
governance chassis was intercepting a decision nobody made. This module is the caller.

**In `adapters`, not `core`, and research F8 records the measurement.** Principle I: the core
never imports an agent framework. ``build_governed_agent`` imports `pydantic_ai` at module
scope, so calling it from `src/core/` would pull the framework into core's import graph —
which `tests/unit/test_core_import.py` exists to prevent and which a deferred import does not
escape. This is the division `core.evals.scoring` already draws against
`adapters/anthropic_scorer.py`: the protocol lives in core, the provider implementation lives
here, and the callers cannot tell which they hold.

**The agent is built with no toolset, and that is not a shortcut.** A choice is a *name*; the
loop then puts that name through `invoke_tool`, which is the same governed entry a scripted
name went through. Letting the agent execute the tool itself would create a second route into
a capability (FR-003 forbids exactly that), and worse, it would move the step bracket inside
the framework — where a resumed run could not honour a choice already made without re-asking
the model, which is re-execution wearing observation's clothes.
"""

from __future__ import annotations

from typing import Any

from adapters.pydantic_ai.agent import build_governed_agent
from core.choice.chooser import ChoiceRequest, Chooser, ChooserUnavailable
from core.choice.recorded import RecordedChooser

#: The provider segment that resolves to a recording rather than a vendor (see
#: `core.choice.recorded`). Named here because this is the module that dispatches on it.
FIXTURE_PROVIDER = "fixture"


def to_model_string(model: str) -> str:
    """``anthropic/claude-opus@5`` → ``anthropic:claude-opus-5``.

    The same decomposition `anthropic_scorer` performs for the SDK, written twice rather than
    shared because the two targets differ: the SDK takes a bare ``claude-opus-5`` while
    `pydantic-ai` wants the provider prefixed. A shared helper returning one of them would put
    a branch on "which caller is this" between the pinned identifier and the thing actually
    called, which is the one join the matrix exists to keep tight.
    """
    provider, _, model_at_version = model.partition("/")
    model_name, _, version = model_at_version.partition("@")
    return f"{provider}:{model_name}-{version}" if version else f"{provider}:{model_name}"


#: What the model is asked. Terse on purpose — a prompt is context budget, and this one is
#: sent once per step per attempt.
#:
#: **It shows the ceiling, never the catalogue.** A model is not told about tools it may not
#: have. That is not enforcement, which is `invoke_tool`'s alone; it is the difference between
#: a model choosing badly and a model being invited to.
_SYSTEM = (
    "You choose the next tool for a governed agent run. Answer with EXACTLY ONE tool name "
    "from the permitted list and nothing else — no punctuation, no explanation, no quotes. "
    "If no tool should be called, answer with the single word NONE. "
    "A tool outside the permitted list will be refused and you will be asked again, so "
    "naming one wastes an attempt rather than widening what you may do."
)

#: What the model says when it wants no tool. Mapped to the empty string, which the platform
#: reads as a terminal answer.
_NONE = "NONE"


def _prompt(request: ChoiceRequest) -> str:
    lines = [
        f"Task: {request.task or '(none supplied)'}",
        f"Permitted tools: {', '.join(request.permitted) or '(none)'}",
        f"Step: {request.step_index}",
    ]
    if request.refused:
        # FR-004a: the denial becomes context, so it teaches rather than only blocks. The
        # reason code travels with it — "authority_insufficient" and "unregistered_tool" call
        # for different second choices, and a bare "refused" would make them the same event.
        lines.append("Already refused at this step:")
        lines.extend(f"  - {name}: {reason}" for name, reason in request.refused)
    return "\n".join(lines)


class ModelChooser:
    """Asks a real model, through the governed agent, for one tool name."""

    def __init__(self, model: str) -> None:
        #: The pinned identifier from the matrix, kept verbatim so what is recorded is what
        #: was called. `to_model_string` derives the client's form; it never replaces this.
        self.model = model
        self._agent: Any | None = None

    def _build(self) -> Any:
        if self._agent is None:
            try:
                # UNCHANGED, and that is the point. Governance is prepended here and also
                # declares position='outermost', so were this agent ever given a toolset, no
                # capability downstream could produce an ungoverned execution.
                self._agent = build_governed_agent(
                    to_model_string(self.model),
                    system_prompt=_SYSTEM,
                    output_type=str,
                )
            except Exception as exc:
                # FR-007 begins here: a provider that cannot even be constructed is a provider
                # failure, and it must reach the caller as one. Converting it to "no choice"
                # would end runs quietly, and falling back to a sequence is the defect this
                # whole feature exists to remove.
                raise ChooserUnavailable(
                    f"could not build an agent for model {self.model!r}: {type(exc).__name__}",
                    reason_code="provider_unavailable",
                ) from exc
        return self._agent

    def choose(self, request: ChoiceRequest) -> str:
        agent = self._build()
        try:
            result = agent.run_sync(_prompt(request), deps=None)
        except Exception as exc:
            # **Terminal, with no fallback** (FR-007, research F4). The tempting behaviour —
            # revert to a deterministic sequence when the provider is down — would silently
            # restore a scripted run at exactly the moment nobody is watching, while every
            # governance row kept passing. That is this feature's own defect preserved as a
            # feature, so there is no branch here that produces a tool name.
            raise ChooserUnavailable(
                f"provider call failed for model {self.model!r}: {type(exc).__name__}",
                reason_code="provider_unavailable",
            ) from exc

        answer = str(getattr(result, "output", "") or "").strip()
        if answer.upper() == _NONE:
            return ""
        # Returned verbatim otherwise. Whether it names a real tool is
        # `core.choice.is_tool_name`'s question and whether that tool is permitted is
        # `invoke_tool`'s; a normalisation step here would be the choosing code quietly
        # deciding one of them.
        return answer


def build_chooser(model: str, *, recording: str = "") -> Chooser:
    """A chooser for the identifier the binding map resolved. **The injection point.**

    Research F5: the stand-in goes *here*, at the binding, and never at the loop. A double
    injected at the loop would let the loop be tested without the code path that consults a
    model, which is precisely the shape this feature exists to end. Injected here, the lane and
    production run the identical resolution — read the binding map, validate the cell against
    the matrix, resolve an identifier, build a chooser for it — and differ only in which
    provider sits behind the identifier.
    """
    provider, _, _ = model.partition("/")
    if provider == FIXTURE_PROVIDER:
        from core.choice.recorded import parse_recording

        # An absent recording is a defined behaviour rather than a misconfiguration — the
        # fixture model then names the first permitted tool. `RecordedChooser`'s docstring
        # carries the argument; the short version is that requiring a script per run would
        # have meant carrying one through the suspended-run index and the sweeper's resume
        # dispatch, which is a control-plane column for a test affordance.
        return RecordedChooser(parse_recording(recording))
    return ModelChooser(model)


__all__ = ["FIXTURE_PROVIDER", "ModelChooser", "build_chooser", "to_model_string"]
