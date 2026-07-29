# SPDX-License-Identifier: Apache-2.0
"""What a thread, a turn, and a run's input are.

Frozen dataclasses rather than Pydantic models: these are internal records passed between
core and the surfaces that read them, and the surfaces already own their own request and
response models. A shared model would make a wire shape and a storage shape the same
object, which is how a storage change becomes a breaking API change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

#: The largest message the platform will accept, in bytes of UTF-8.
#:
#: Stated rather than emergent (FR-009a). A bound that fell out of a column width or a
#: downstream context limit would change silently when that limit did, and a person would
#: discover it by having a message refused that worked yesterday. Over this, the message is
#: refused **whole** — never truncated, because a truncated consent record consents to
#: something the person did not say.
MAX_MESSAGE_BYTES = 8192

#: How many earlier results a later turn carries forward.
#:
#: The other half of FR-009a. Five is a judgement, not a discovery: enough that a
#: conversation holds its shape, small enough that a person can be shown what fell out
#: without the list becoming its own reading task.
CONTEXT_TURNS = 5

#: How many acts a person may take in the rate window, and how long the window is.
#:
#: Counted across **turns and thread creations together** — a created thread is a
#: turn-shaped act whose body is one insert, and a window counting only turns would read
#: zero while someone created ten thousand empty threads.
RATE_LIMIT_ACTS = 30
RATE_LIMIT_WINDOW_SECONDS = 300


class TurnDisposition(StrEnum):
    """What became of a message the platform accepted.

    All three are *accepted* — the platform considered the message and answered. A message
    that never got that far (rate-limited, oversized) has no turn at all; it has a
    `TURN_REFUSED` event and a refusal to the caller.
    """

    #: A run started. `run_id` names it.
    DISPATCHED = "dispatched"
    #: Nothing could be dispatched — no agent selected, or none available to this person.
    #: The platform does not do this; it is not about who is asking.
    DECLINED = "declined"
    #: An agent was selected that this person may not start. About who is asking.
    REFUSED = "refused"


@dataclass(frozen=True)
class ThreadRecord:
    """A conversation's spine. Owned by one subject in one tenant, deletable by them."""

    thread_id: str
    correlation_id: str
    subject_user_id: str
    tenant_id: str
    created_at: datetime
    #: Null until the first accepted turn, whose leading fragment becomes it — once.
    #: There is no rename operation, so this cannot drift from what actually happened.
    title: str | None = None


@dataclass(frozen=True)
class TurnRecord:
    """One accepted exchange, as the view remembers it.

    `tenant_id` and `subject_user_id` are denormalized from the thread deliberately: the
    rate window counts a *person's* acts across every thread they have, and a query that
    joined through a single thread would bound each thread separately.
    """

    turn_id: str
    thread_id: str
    tenant_id: str
    subject_user_id: str
    seq: int
    message: str
    disposition: TurnDisposition
    created_at: datetime
    reason: str | None = None
    run_id: str | None = None
    agent_definition_id: str | None = None
    #: The runs whose results this turn carried forward, newest first.
    context_run_ids: tuple[str, ...] = ()
    #: The runs that fell outside the bound. Recorded so the bound's effect is inspectable
    #: after the fact, and rendered so a person knows the platform forgot something
    #: (FR-009b) rather than reading a worse answer as a worse platform.
    context_dropped: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunInput:
    """What a dispatched run reads at start: the message, and what to carry forward.

    **References, not copies.** Five results verbatim could be a megabyte; five run ids are
    nothing, and resolving them at run start reads the recorded bytes rather than a copy
    that travelled. That is also what makes "byte-identical" (SC-002) true by construction
    rather than by care.
    """

    run_id: str
    message: str
    created_at: datetime
    context_run_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedInput:
    """A run's input with its context resolved to the bytes each result was stored as.

    `context` is ordered as `RunInput.context_run_ids` was — newest first — and each entry
    is the **stored serialization**, not a reparsed object. Comparison on parsed objects
    would pass a reserialization that changed key order today and content tomorrow.
    """

    message: str
    context: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def title_from(message: str, *, limit: int = 60) -> str:
    """A thread's title, taken once from its first accepted message.

    Whitespace-collapsed and cut at a word boundary where one is near enough to the limit.
    Display only — nothing reads it back, and no operation changes it.
    """
    collapsed = " ".join(message.split())
    if len(collapsed) <= limit:
        return collapsed
    cut = collapsed[:limit]
    space = cut.rfind(" ")
    if space >= limit // 2:
        cut = cut[:space]
    return cut.rstrip() + "…"


def message_size_bytes(message: str) -> int:
    """UTF-8 bytes, which is what the bound is stated in.

    Characters would make the bound depend on the alphabet — the same sentence refused in
    one language and accepted in another.
    """
    return len(message.encode("utf-8"))


__all__ = [
    "CONTEXT_TURNS",
    "MAX_MESSAGE_BYTES",
    "RATE_LIMIT_ACTS",
    "RATE_LIMIT_WINDOW_SECONDS",
    "ResolvedInput",
    "RunInput",
    "ThreadRecord",
    "TurnDisposition",
    "TurnRecord",
    "message_size_bytes",
    "title_from",
]
