# SPDX-License-Identifier: Apache-2.0
"""Where a record of an ask lands.

**A third placement, because neither of 022's applies.** That feature settled two: a *read* of a
run or thread record goes to ``record-access:{tenant}``, and an *act* on a run or thread goes to
that object's own stream. An ask is neither — it consults a corpus, not the platform's own records,
and it has no run and no thread to belong to.

An earlier draft of this feature's data model named no stream at all, which made the requirement
unimplementable: an ``AuditEntry`` cannot be constructed without a ``correlation_id`` and a
``tenant_id``.
"""

from __future__ import annotations

from typing import Final

#: One stream per tenant, stable across asks.
#:
#: Stable rather than per-ask, for the reason `EVIDENCE_STREAM_PREFIX` already records: a fresh
#: correlation id each time would make every record a chain of one — linked to nothing and
#: removable without trace, which defeats the reason a record of who asked exists at all.
ASK_STREAM_PREFIX: Final[str] = "ask"


def ask_stream_for(tenant_id: str) -> str:
    return f"{ASK_STREAM_PREFIX}:{tenant_id}"


__all__ = ["ASK_STREAM_PREFIX", "ask_stream_for"]
