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

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel
from pydantic_ai.exceptions import UnexpectedModelBehavior

from adapters.pydantic_ai.agent import build_governed_agent
from core.choice.chooser import (
    Answer,
    ChoiceRequest,
    Chooser,
    ChooserUnavailable,
    MalformedAnswer,
)
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
    "You choose the next tool for a governed agent run, and state what to do with it. "
    "Answer with EXACTLY ONE tool name from the permitted list, plus the arguments the tool "
    "should run with — an empty arguments object is correct for a tool that takes none. "
    "If no tool should be called, set the tool to NONE. "
    "A tool outside the permitted list will be refused and you will be asked again, so "
    "naming one wastes an attempt rather than widening what you may do."
)

#: What the model says when it wants no tool. Mapped to the empty answer, which the platform
#: reads as terminal.
_NONE = "NONE"

#: Brief schemas for authoring tools (047). The chooser shows the ceiling, never a catalogue;
#: without these two lines a live write model sees only bare names and often answers NONE.
_AUTHORING_RESEARCH_HINT = (
    "Tool arguments: "
    'read_subject needs {"path": "<path relative to the mounted subject>"}; '
    'author_file needs {"path": "<path>", "content": "<full file body>"}. '
    "For a request to create or change files, begin with read_subject "
    "(e.g. README.md) rather than NONE. author_file is refused until the platform "
    "has recorded a write plan from what you read — keep reading until you have "
    "enough, then author_file will be permitted."
)
_AUTHORING_WRITE_PREFERRED_HINT = (
    "Tool arguments: "
    'read_subject needs {"path": "<path relative to the mounted subject>"}; '
    'author_file needs {"path": "<path>", "content": "<full file body>"}. '
    "The write plan is recorded. Prefer author_file with full file bodies. "
    "Read only if a specific path in the plan is still unknown."
)
_AUTHORING_WRITE_ONLY_HINT = (
    "Tool arguments: "
    'author_file needs {"path": "<path>", "content": "<full file body>"}. '
    "The write plan is recorded. Call author_file now. Do not answer NONE. "
    "Do not invent a second research pass."
)

_AUTHORING_TOOLS = frozenset({"read_subject", "author_file"})
_READ_SUBJECT = "read_subject"
_AUTHOR_FILE = "author_file"


def _authoring_hint(permitted: tuple[str, ...] | list[str]) -> str:
    names = set(permitted)
    if _AUTHOR_FILE in names and _READ_SUBJECT not in names:
        return _AUTHORING_WRITE_ONLY_HINT
    if _AUTHOR_FILE in names and _READ_SUBJECT in names:
        return _AUTHORING_WRITE_PREFERRED_HINT
    return _AUTHORING_RESEARCH_HINT


class _WritePlanDraft(BaseModel):
    """Structured write plan — paths and intent, never file bodies."""

    summary: str = ""
    files: list[str] = []


class _QualityJudgment(BaseModel):
    """Judge verdict on authored work. ``allow`` false is a publish deny."""

    allow: bool
    reason: str = ""


class _ToolCall(BaseModel):
    """The structured answer the framework validates (040, research R1).

    Lives in the adapter rather than in core, because core imports no framework and the
    framework wants a schema it can hand a model. Converted to `core.choice.Answer` at the
    seam, so the callers cannot tell which side produced it — the same division the
    `Chooser` protocol itself draws.
    """

    tool: str
    arguments: dict[str, Any] = {}


def _prompt(request: ChoiceRequest) -> str:
    lines = [
        f"Task: {request.task or '(none supplied)'}",
        f"Permitted tools: {', '.join(request.permitted) or '(none)'}",
        f"Step: {request.step_index}",
    ]
    if _AUTHORING_TOOLS.intersection(request.permitted):
        lines.append(_authoring_hint(request.permitted))
    if request.refused:
        # FR-004a: the denial becomes context, so it teaches rather than only blocks. The
        # reason code travels with it — "authority_insufficient" and "unregistered_tool" call
        # for different second choices, and a bare "refused" would make them the same event.
        lines.append("Already refused at this step:")
        lines.extend(f"  - {name}: {reason}" for name, reason in request.refused)
    return "\n".join(lines)


class ModelChooser:
    """Asks a real model, through the governed agent, for one tool name."""

    def __init__(self, model: str, *, secret: str = "") -> None:
        #: The pinned identifier from the matrix, kept verbatim so what is recorded is what
        #: was called. `to_model_string` derives the client's form; it never replaces this.
        self.model = model
        #: The vendor credential, brokered for **this allocation** and passed explicitly (027).
        #:
        #: Empty means "let the client resolve it from its environment", which is the eval
        #: lane's path and is exempt (FR-013). A dispatched allocation always supplies one, so
        #: the credential a run calls with is the one the trust store held when it started —
        #: never an ambient variable that would outlive scrutiny and be readable by anything
        #: else in the allocation.
        #:
        #: An allocation IS one task, so this object's lifetime is the task's lifetime and the
        #: material evaporates with it. That is the whole posture; there is nothing else keeping
        #: it short-lived.
        self._secret = secret
        self._agent: Any | None = None

    def _model_for_client(self) -> Any:
        """The pinned identifier as the client wants it, carrying explicit credentials (027).

        With no secret this is the string form and the client resolves a key from its
        environment — unchanged, and the eval lane's path.

        With one, an explicit provider object is constructed so the key travels as an argument
        rather than as process state. **The import is deferred and vendor-specific by
        necessity**: naming a provider's credential parameter is the one place a vendor's own
        vocabulary cannot be avoided, and it is confined to this function so nothing above it
        has to know. A second vendor adds a branch here and nowhere else.
        """
        as_string = to_model_string(self.model)
        if not self._secret:
            return as_string

        vendor, _, name = as_string.partition(":")
        if vendor == "anthropic":
            from pydantic_ai.models.anthropic import AnthropicModel
            from pydantic_ai.providers.anthropic import AnthropicProvider

            return AnthropicModel(name, provider=AnthropicProvider(api_key=self._secret))

        # A vendor this function does not know must NOT silently fall through to the string
        # form: that would resolve a key from the environment, which is the exact fallback 027
        # exists to remove. It fails as a provider problem, naming what is missing.
        raise ChooserUnavailable(
            f"no explicit-credential provider is wired for vendor {vendor!r}; refusing rather "
            f"than falling back to an ambient credential",
            reason_code="provider_unavailable",
        )

    def _build(self) -> Any:
        if self._agent is None:
            try:
                # UNCHANGED, and that is the point. Governance is prepended here and also
                # declares position='outermost', so were this agent ever given a toolset, no
                # capability downstream could produce an ungoverned execution.
                self._agent = build_governed_agent(
                    self._model_for_client(),
                    system_prompt=_SYSTEM,
                    output_type=_ToolCall,
                )
            except ChooserUnavailable:
                raise
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

    def choose(self, request: ChoiceRequest) -> Answer:
        agent = self._build()
        try:
            result = agent.run_sync(_prompt(request), deps=None)
        except UnexpectedModelBehavior as exc:
            # The model answered, and the answer does not validate as a tool call — a
            # MALFORMED answer, not a provider outage (040, research R12). Re-asked within
            # the bound rather than ending the run: a model that must now emit a structured
            # object can emit an invalid one, and being told tends to fix it. The framework
            # has already retried internally; what reaches here is its final word. The shape
            # travels, the content does not.
            raise MalformedAnswer(
                f"the model's answer did not validate as a tool call: {type(exc).__name__}"
            ) from exc
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

        output = getattr(result, "output", None)
        if not isinstance(output, _ToolCall):
            raise MalformedAnswer(
                f"the framework returned {type(output).__name__} where a tool call was asked for"
            )
        name = output.tool.strip()
        if name.upper() == _NONE:
            return Answer("")
        # Returned verbatim otherwise. Whether it names a real tool is
        # `core.choice.is_tool_name`'s question and whether that tool is permitted is
        # `invoke_tool`'s; a normalisation step here would be the choosing code quietly
        # deciding one of them. The arguments travel untouched for the same reason — the
        # platform carries the request to the capability, which enforces its own rules
        # (040, clarification Q1).
        return Answer(name, output.arguments)

    def draft_write_plan(self, *, task: str, consulted: tuple[str, ...]) -> str:
        """What the analyzer will write, after Research. Not a product plan oracle."""
        prompt = (
            f"Task: {task or '(none supplied)'}\n"
            f"Subject paths already read: {', '.join(consulted) or '(none)'}\n"
            "Outline the files you will create or change and what each will do. "
            "Do not write file bodies. Do not include secrets."
        )
        try:
            agent = build_governed_agent(
                self._model_for_client(),
                system_prompt=(
                    "You plan a file-level change for a governed authoring run. "
                    "Answer with a short summary and the paths you will write. "
                    "No file contents. No secrets."
                ),
                output_type=_WritePlanDraft,
            )
            result = agent.run_sync(prompt, deps=None)
        except Exception as exc:
            raise ChooserUnavailable(
                f"could not draft a write plan for model {self.model!r}: {type(exc).__name__}",
                reason_code="provider_unavailable",
            ) from exc
        output = getattr(result, "output", None)
        if not isinstance(output, _WritePlanDraft):
            raise MalformedAnswer("the model's write plan did not validate")
        summary = (output.summary or "").strip()
        paths = [p.strip() for p in output.files if str(p).strip()]
        if paths:
            listed = ", ".join(paths[:12])
            return f"{summary} Files: {listed}".strip() if summary else f"Files: {listed}"
        return summary or "Write the files required by the task."

    def judge_authored_work(
        self,
        *,
        task: str,
        write_plan: str,
        files: dict[str, str],
    ) -> tuple[bool, str]:
        """Quality and accuracy of what was written, against the task. Fail closed."""
        excerpts: list[str] = []
        for path, body in list(files.items())[:8]:
            text = body if len(body) <= 8000 else body[:8000] + "\n…"
            excerpts.append(f"### {path}\n```\n{text}\n```")
        prompt = (
            f"Task: {task or '(none supplied)'}\n"
            f"Author's plan: {write_plan or '(none recorded)'}\n"
            "Authored files:\n"
            f"{chr(10).join(excerpts) or '(none)'}\n"
            "Decide whether this work is accurate and sufficient for the task. "
            "Deny if it is wrong, incomplete, unrelated to the request, or unsafe. "
            "allow=true only if a reviewer should receive this as a pull request."
        )
        try:
            agent = build_governed_agent(
                self._model_for_client(),
                system_prompt=(
                    "You judge authored files for a governed Build. "
                    "You do not write files. You do not invent a pull request. "
                    "allow must be false unless the work matches the task and is sound. "
                    "reason is user-safe: no secrets, no raw credentials."
                ),
                output_type=_QualityJudgment,
            )
            result = agent.run_sync(prompt, deps=None)
        except Exception as exc:
            raise ChooserUnavailable(
                f"could not judge authored work for model {self.model!r}: {type(exc).__name__}",
                reason_code="provider_unavailable",
            ) from exc
        output = getattr(result, "output", None)
        if not isinstance(output, _QualityJudgment):
            raise MalformedAnswer("the model's judgment did not validate")
        reason = (output.reason or "").strip() or ("ok" if output.allow else "judge denied publish")
        return bool(output.allow), reason[:240]


def build_chooser(
    model: str,
    *,
    recording: str = "",
    secret: str = "",
    bare_name_arguments: Mapping[str, Any] | None = None,
) -> Chooser:
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
        # A FIXTURE MODEL FETCHES NOTHING. There is no vendor to hold authority for, so a
        # deployment running only fixture cells needs no model credential at all — which is what
        # every blocking lane in this repository is (FR-011).
        # `bare_name_arguments` is what a bare name in a recording has always meant
        # (040, FR-010). It reaches only the RECORDED chooser: a real model states its
        # own arguments, and topping those up from a fixture constant would be the
        # platform putting words in a model's mouth.
        return RecordedChooser(parse_recording(recording), bare_name_arguments=bare_name_arguments)
    return ModelChooser(model, secret=secret)


__all__ = ["FIXTURE_PROVIDER", "ModelChooser", "build_chooser", "to_model_string"]
