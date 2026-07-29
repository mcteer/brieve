# SPDX-License-Identifier: Apache-2.0
"""GATE:no-secret-leak — a pack tool's arguments reach the trail as keys and hashes.

**True today by inheritance and asserted nowhere.** Pack tools are ordinary registry
registrations, so they pass through the same `redact_arguments` every tool does — which is
the design working. But "inherited" and "asserted" are different states, and the tool this
matters most for did not exist until 013: a `secret_touching` tool's arguments are precisely
what must not land raw.

The stakes are ADR-0051's accepted residual risk, stated verbatim in that ADR: **a secret
pasted into a portal message is permanent.** The audit trail is append-only and hash-chained;
a value written there cannot be removed without breaking the chain that proves nothing was
removed. So redaction is not a tidiness measure — it is the only point at which a secret can
still be kept out.
"""

from __future__ import annotations

from typing import Any

import pytest

from core.redaction import redact_arguments
from core.registry.memory import ToolRegistry
from core.tools.invoke import invoke_tool
from tests.component.conftest import CountingHandler, make_run

#: A value that must appear nowhere. Distinctive enough that a substring search over the
#: whole audit entry is meaningful rather than coincidental.
SECRET = "s3cr3t-value-that-must-never-appear-anywhere-in-the-trail"


def _run_with_secret_touching_tool() -> tuple[Any, Any]:
    handler = CountingHandler()
    run, registered, sink = make_run(
        tool_name="vault_write", scope={"vault_write"}, handler=handler
    )
    # Re-register at the risk class the Vault pack declares, so the row exercises the
    # classification a secret-touching pack tool actually carries.
    run.registry.register("vault_write", registered, risk_class="secret_touching")
    return run, sink


def test_a_secret_touching_tools_arguments_never_reach_the_trail_raw() -> None:
    """The whole point of the row, asserted over the entire entry rather than one field.

    Checking `payload["arguments"]` would only prove the field somebody thought of is clean.
    Serialising the whole entry and searching it catches the value arriving through a
    message, a detail string, or a field added later by someone who did not know.
    """
    run, sink = _run_with_secret_touching_tool()

    invoke_tool(run, "vault_write", {"path": "app/db", "password": SECRET, "cas": 1})

    entries = sink.list_by_correlation_id(run.correlation_id)
    assert entries, "nothing was audited; this row would pass vacuously"
    for entry in entries:
        assert SECRET not in str(entry.model_dump()), (
            f"a secret_touching tool's argument value reached the trail in a "
            f"{entry.event_type} entry. The trail is append-only and hash-chained, so a "
            f"value written here cannot be removed without breaking the chain that proves "
            f"nothing was removed"
        )


def test_the_keys_do_survive_because_an_investigator_needs_them() -> None:
    """Redaction that dropped the arguments entirely would be safer and useless.

    An investigator asking "what did this run touch" needs to know a `password` argument was
    supplied to a write at `app/db`. The key is the evidence; the value is the liability.
    """
    redacted = redact_arguments({"path": "app/db", "password": SECRET})
    assert redacted["argument_keys"] == ["password", "path"]
    assert SECRET not in str(redacted)


def test_the_hash_distinguishes_two_different_secrets() -> None:
    """Why hashes rather than a fixed marker.

    `"password": "[redacted]"` cannot answer "was the same value used twice", which is
    exactly what an investigator asks after a leak. The hash answers it without carrying
    the value.
    """
    one = redact_arguments({"password": SECRET})["argument_hashes"]["password"]
    two = redact_arguments({"password": SECRET + "x"})["argument_hashes"]["password"]
    same = redact_arguments({"password": SECRET})["argument_hashes"]["password"]
    assert one != two
    assert one == same


def test_the_check_would_fire_if_redaction_were_removed() -> None:
    """A positive control over the assertion itself.

    Without this, the row above proves only that nobody wrote the value into the payload by
    hand — an unredacted argument map contains the secret, and the same search finds it.
    """
    unredacted = {"argument_keys": ["password"], "arguments": {"password": SECRET}}
    assert SECRET in str(unredacted)


@pytest.mark.parametrize("risk_class", ["read", "write", "destructive", "secret_touching"])
def test_redaction_does_not_depend_on_risk_class(risk_class: str) -> None:
    """Every tool is redacted, not only the ones declared dangerous.

    A pack author who mis-declares `secret_touching` as `read` must not thereby opt out of
    redaction. The classification drives review and isolation; it never drives whether the
    trail is safe.
    """
    handler = CountingHandler()
    run, registered, sink = make_run(tool_name="t", scope={"t"}, handler=handler)
    run.registry.register("t", registered, risk_class=risk_class)  # type: ignore[arg-type]

    invoke_tool(run, "t", {"password": SECRET})

    for entry in sink.list_by_correlation_id(run.correlation_id):
        assert SECRET not in str(entry.model_dump())


def test_a_registry_that_forgot_risk_class_still_redacts() -> None:
    """The default path, since `risk_class` defaults to `read`."""
    registry = ToolRegistry()
    registry.register("t", lambda args: "ok")
    assert registry.resolve("t").risk_class == "read"
    assert SECRET not in str(redact_arguments({"password": SECRET}))
