# SPDX-License-Identifier: Apache-2.0
"""US1 — a client attaches and the platform answers.

The first rows in this platform's life that drive the MCP surface as a client would. Fifty-six
rows already exercise `McpTransport`; none of them could reach it.
"""

from __future__ import annotations

import pytest

from surfaces.mcp.operations import operations
from tests.conformance.mcp_served import surfaces

pytestmark = [pytest.mark.enclave, pytest.mark.host_enclave]


def test_a_client_establishes_a_session(caller: str) -> None:
    """FR-001, SC-001: the SDK's own client, unmodified, against the running process."""
    listed = surfaces.list_operations(caller)

    assert listed, (
        "the session established but the surface exposed nothing. A client that connects to "
        "an empty surface has proven the socket and not the platform."
    )


def test_the_operation_set_matches_what_the_transport_declares(caller: str) -> None:
    """FR-008, SC-002 — the SERVED half of parity.

    **Not a second comparison against the API's snapshot.** `tests/conformance/mcp/
    test_surface_parity.py` already compares the transport against
    `specs/008-northbound-api/contracts/operations.snapshot.json` by `(method, path)` pairs,
    and duplicating that here would assert the same thing twice while adding a way for the two
    comparisons to disagree.

    What no row could assert until now is the half that needed a server: **that a client can
    actually reach every operation the transport declares.** A tool that failed to register —
    a bad annotation, an exception during setup, a name the SDK rejected — leaves the class
    parity row perfectly green and the operation unreachable.
    """
    served = set(surfaces.list_operations(caller))
    declared = {op.tool_name for op in operations()}

    assert served == declared, (
        f"what a client can reach differs from what the transport declares.\n"
        f"  declared but unreachable: {sorted(declared - served)}\n"
        f"  reachable but undeclared: {sorted(served - declared)}\n"
        f"The first is an operation that failed to register and would leave every existing "
        f"parity row green while a client could not call it."
    )


def test_a_caller_with_no_credential_is_refused_before_any_operation(running_surface: str) -> None:
    """FR-012: refused at the boundary, not inside.

    The status arrives before a session exists at all, which is what "before the governed
    operation is entered" means in practice — there is no operation yet to enter.
    """
    status = surfaces.handshake_refused_without_credential()

    assert status == 401, (
        f"a caller presenting no credential received {status}. Anything but a refusal here "
        f"means the surface served somebody it never identified — and every downstream "
        f"guarantee would then be about a subject nobody established."
    )
