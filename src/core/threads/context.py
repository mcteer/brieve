# SPDX-License-Identifier: Apache-2.0
"""Resolving a run's input: the message, and prior results as the bytes they were stored as.

**The one place context is turned into content**, so "byte-identical" (SC-002) is a
property of construction rather than of care. Everything that carries context forward calls
this — the allocation's entrypoint in production, the rows in the hermetic lane — and none
of them re-implements the resolution, because two implementations of "the same bytes" is
how the two stop being the same bytes.

**Why the stored serialization rather than the parsed object.** A result is JSON in a
checkpoint payload. Handing a later run the *parsed* object would make the comparison
`==` on dictionaries, which passes a reserialization that reorders keys today — and passes
a reserialization that drops a key tomorrow, because nothing was ever comparing what was
written. Serializing here, once, with sorted keys, gives a string a row can compare
exactly and a defect cannot hide inside.

**Reading, not copying.** `run_inputs` holds run *ids*; the bytes come from the durability
record at resolution time. Five results copied into the input row could be a megabyte and
would be a second copy of something already recorded — which is the two-records-of-one-fact
problem this platform keeps declining to create.
"""

from __future__ import annotations

import json
from typing import Any

from core.threads.records import ResolvedInput
from core.threads.store import ThreadStore

#: The reserved key a run's result lives under in its terminal checkpoint payload.
#:
#: Duplicated from `surfaces.api.runs` rather than imported: `core` importing a surface is
#: the layering reversal this package refuses everywhere else. The value is asserted equal
#: by a row, so the duplication cannot drift silently.
RESULT_KEY = "__run_result__"


def serialize_result(result: Any) -> str:
    """The canonical form of a recorded result.

    `sort_keys` and fixed separators so the same result always produces the same bytes —
    without that, two runs recording equal results could carry forward different strings
    and a byte-comparison would fail on a difference that means nothing.
    """
    return json.dumps(result, sort_keys=True, separators=(",", ":"), default=str)


def resolve_run_input(
    *,
    run_id: str,
    store: ThreadStore,
    durability: Any,
) -> ResolvedInput | None:
    """A run's message and its carried context, or ``None`` if it has no input.

    ``None`` means this run was started outside a thread — through `start_run` on any
    transport — and it is not an error: those runs behave exactly as they did before this
    feature existed.

    A context entry whose result cannot be read is **omitted**, not faked. The turn already
    recorded which runs it intended to carry (`context_run_ids`) and which it dropped, so
    an investigator can see the difference between "the platform chose not to carry this"
    and "the platform could not read it". Substituting a placeholder would make a run's
    input claim something no record supports.
    """
    stored = store.get_run_input(run_id=run_id)
    if stored is None:
        return None

    context: list[tuple[str, str]] = []
    for prior_id in stored.context_run_ids:
        blob = _load(durability, prior_id)
        if blob is None:
            continue
        payload = blob.payload or {}
        if RESULT_KEY not in payload:
            continue
        context.append((prior_id, serialize_result(payload[RESULT_KEY])))

    return ResolvedInput(message=stored.message, context=tuple(context))


def _load(durability: Any, run_id: str) -> Any:
    if durability is None:
        return None
    try:
        return durability.load(run_id)
    except Exception:  # noqa: BLE001 — an unreadable prior result narrows context, never fails
        return None


__all__ = ["RESULT_KEY", "resolve_run_input", "serialize_result"]
