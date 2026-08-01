# SPDX-License-Identifier: Apache-2.0
"""US2 — the call is governed, and a refusal is the core's.

**The trap here is the one 018 hit**, in a different costume. There, a control plane answered
`403` identically for *forbidden* and *absent*, so a row reading denial as proof would pass
with one letter wrong in its path. Here, a protocol layer refusing on its own produces an
outcome a client cannot tell from the core refusing — same status, same shape, no difference
visible from the outside.

So these rows distinguish *where* the answer came from, not merely that one arrived.
"""

from __future__ import annotations

import pytest

from surfaces.mcp.operations import operations
from tests.conformance.mcp_served import surfaces

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]

#: What only the governed core produces. `McpResult` carries the status the API would have
#: returned, and the protocol layer has no way to synthesise one — it holds no verdicts.
CORE_SHAPE = {"ok", "status"}

#: The only statuses `served.py` may answer without consulting the core: no acceptable
#: credential, a session claimed by somebody else, and a request malformed before any
#: operation could be entered. Everything else must arrive through `McpResult`.
FRAMING_STATUSES = {400, 401, 403}


def test_an_operation_is_governed(caller: str) -> None:
    """FR-005: the call goes through the governed core, not around it.

    Evidenced by the answer's shape. A payload carrying `ok` and `status` came back through
    `McpResult`, which only the transport produces; the protocol layer in `served.py` holds no
    business logic and could not invent one.
    """
    answered = surfaces.call("list_threads", {}, token=caller)

    assert CORE_SHAPE <= set(answered), (
        f"the answer does not carry the core's verdict: {answered}. A payload without "
        f"`ok`/`status` did not come back through `McpResult`, which means something other "
        f"than the governed core answered this call."
    )


def test_a_refusal_comes_from_the_core(caller: str) -> None:
    """FR-006, SC-005 — and the row this feature's design notes called out by name.

    A caller whose claims map to a role may still be refused by the core for what they asked
    to do. That refusal must be **the core's**: it carries the verdict `McpResult` was built
    with, rather than a status the protocol layer chose.

    The discriminator is the payload's provenance, not its status code. A protocol-layer
    refusal in `served.py` answers with `reason` and no `status` from any verdict — see
    `test_the_protocol_layer_authors_no_verdicts`, which forbids it from doing otherwise.
    """
    # A definition nobody registered. The core decides this, not the framing.
    answered = surfaces.call(
        "get_agent_definition", {"agent_definition_id": "no-such-definition"}, token=caller
    )

    assert CORE_SHAPE <= set(answered), f"a refusal arrived without the core's verdict: {answered}"
    assert answered["ok"] is False, f"expected a refusal, got {answered}"

    # **Not a guess at which code.** An earlier version of this row demanded 403 or 404 and
    # failed on the 503 the core actually issues, because resolution refuses before the
    # definition's absence is reached. Asserting a specific code would have been asserting
    # what this row believed about the core rather than that the core answered.
    #
    # What matters is that the status is one only the CORE issues. The framing's own answers
    # are exactly three — see the structural row below — so a status outside that set cannot
    # have come from `served.py`.
    assert answered["status"] not in FRAMING_STATUSES, (
        f"the refusal carries {answered['status']}, which is a status the protocol layer can "
        f"issue on its own — so this row cannot tell whether the core was consulted at all."
    )


def test_the_protocol_layer_authors_no_verdicts() -> None:
    """FR-006 as a structural rule, because the runtime evidence above cannot see everything.

    The protocol layer may REPORT the core's decision and must never MAKE one. Its own
    answers are confined to the two things the core cannot see — a caller with no acceptable
    credential, and a request malformed before any operation could be entered.
    """
    source = (surfaces.ROOT / "src/surfaces/mcp/served.py").read_text()

    # `result.status` FORWARDS the core's verdict; it does not author one. Exempting it is
    # the difference between "the framing may not decide" and "the framing may not speak",
    # and an earlier version of this row conflated them — flagging `result_payload`, whose
    # entire job is to carry the core's answer outward.
    offending = [
        line.strip()
        for line in source.splitlines()
        if '"status":' in line
        and "result.status" not in line
        and not any(code in line for code in ("400", "401", "403"))
    ]

    assert not offending, (
        "the protocol layer synthesises a status the core did not issue:\n"
        + "\n".join(f"  {line}" for line in offending)
        + "\n\nOnly 401 (no acceptable credential), 403 (this session belongs to someone "
        "else) and 400 (malformed before any operation) are the framing's to answer. Every "
        "other verdict must come back through `McpResult`."
    )


def test_four_failures_are_distinguishable(caller: str) -> None:
    """FR-007: refused, unknown operation, malformed request, and transport failure.

    Four responses a client must be able to tell apart, because they call for four different
    actions. Collapsing them would make every denial look like a broken platform, let a
    genuine outage read as a policy decision, and tell a caller which operations exist by
    which error they received.
    """
    served = surfaces.call("list_threads", {}, token=caller)
    unknown = surfaces.call("no_such_operation", {}, token=caller)
    malformed = surfaces.call("get_run", {}, token=caller)

    assert served.get("ok") is True, f"the control case did not succeed: {served}"

    assert unknown.get("isError") is True and "Unknown tool" in unknown.get("raw", ""), (
        f"an unknown operation did not report as unknown: {unknown}"
    )

    assert malformed.get("status") == 400 and malformed.get("missing"), (
        f"malformed input was not refused at the boundary naming what was wrong: {malformed}. "
        f"Before this was handled the transport raised `KeyError('run_id')` and the client "
        f"saw \"Error executing tool get_run: 'run_id'\" — indistinguishable from a fault."
    )

    assert unknown.get("raw") != malformed.get("reason"), (
        "unknown and malformed answered identically, which tells a caller which operations "
        "exist by which error they get back"
    )


def test_every_declared_operation_is_callable(caller: str) -> None:
    """The coverage half: each declared operation answers *something* the core produced.

    Not that each succeeds — most need state a fresh enclave does not have. That an operation
    answers with a verdict at all is what distinguishes a registered tool from one that
    raises on entry, which listing alone cannot tell.
    """
    unreachable: dict[str, str] = {}

    for operation in operations():
        answered = surfaces.call(operation.tool_name, {}, token=caller)
        if not (CORE_SHAPE <= set(answered) or answered.get("status") == 400):
            unreachable[operation.tool_name] = str(answered)[:120]

    assert not unreachable, "operations that answered with no verdict:\n" + "\n".join(
        f"  {name}: {why}" for name, why in unreachable.items()
    )
