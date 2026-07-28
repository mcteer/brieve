# SPDX-License-Identifier: Apache-2.0
"""Reading a harness-domain ceiling record into an :class:`AuthorityScope`.

**There is no translation here, and that is the point.** An earlier draft of this feature
assumed a compiled trust-fabric policy had to be converted into the core's scope algebra,
and asked how to do it losslessly. The premise was wrong: a ceiling policy governs which
*secrets* a token may read, and an `AuthorityScope` governs which *tools* an agent may
call. They are disjoint jurisdictions (ADR-0044), so there was never anything to convert —
the harness ceiling is authored in the core's own vocabulary and read as written.

What remains is validation, and every rule below refuses rather than repairing. A parser
that repaired would be deciding authority, and the whole point of reading a ceiling from
the trust fabric is that authority is decided where an operator can see it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Final

from core.authority.errors import ResolutionRefused
from core.authority.types import AuthorityScope

#: The record shape this platform understands.
#:
#: Bumped when the record's meaning changes, never for additive fields a reader can ignore
#: — because a version bump makes every older reader refuse, and refusing is expensive
#: enough that it should mean something.
SUPPORTED_SCHEMA_VERSION: Final[int] = 1


def parse_ceiling_record(
    record: Mapping[str, Any],
    *,
    known_tools: Iterable[str],
    known_actions: Iterable[str],
) -> AuthorityScope:
    """Validate a ceiling or role-binding record and return the scope it declares.

    ``known_tools`` and ``known_actions`` are what the platform can actually do. A ceiling
    naming something outside them is a configuration error, and the only safe response is
    to say so — see :func:`_reject_unknown`.
    """
    version = record.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        # Absent and newer land in the same place deliberately. A record with no version is
        # either older than versioning or hand-written, and both are cases where guessing
        # is how a ceiling gets misread.
        raise ResolutionRefused(
            f"ceiling record declares schema_version {version!r}; "
            f"this platform understands {SUPPORTED_SCHEMA_VERSION}",
            reason_code="unsupported_schema_version",
        )

    tools = frozenset(str(name) for name in record.get("tool_names") or ())
    actions = frozenset(str(name) for name in record.get("product_actions") or ())

    _reject_unknown(tools, frozenset(known_tools), kind="tool")
    _reject_unknown(actions, frozenset(known_actions), kind="product action")

    return AuthorityScope(tool_names=tools, product_actions=actions)


def _reject_unknown(declared: frozenset[str], known: frozenset[str], *, kind: str) -> None:
    """Refuse a ceiling naming something the platform does not have, and name it.

    **Dropping the unknown entry is the tempting alternative and it is the dangerous one.**
    It produces a valid, narrower scope and no error — a change to authority that leaves no
    trace, breaking a working agent for a reason nobody can find. Refusing is louder and
    correct: the operator wrote something that does not exist, and only they can fix it.

    Naming the entry is not decoration. A refusal that says only "unknown entry" tells an
    operator their configuration is wrong without telling them which line.
    """
    unknown = sorted(declared - known)
    if unknown:
        raise ResolutionRefused(
            f"ceiling names {kind}(s) this platform does not know: {', '.join(unknown)}",
            reason_code="unknown_ceiling_entry",
        )


__all__ = ["SUPPORTED_SCHEMA_VERSION", "parse_ceiling_record"]
