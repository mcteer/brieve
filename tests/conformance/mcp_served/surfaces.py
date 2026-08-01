# SPDX-License-Identifier: Apache-2.0
"""Reaching the SERVED MCP surface — the process, not the class.

Every helper here goes over a socket to a running allocation. **Nothing in this directory may
construct `McpTransport`**, which `test_no_row_here_constructs_the_transport` enforces: a row
that did would assert what fifty-six class rows already assert while appearing to assert more,
and that appearance is the whole defect 019 exists to close.

The caller's credential is minted by walking the development provider's real authorization-code
flow with PKCE — not by signing a token here. A row that minted its own would be verifying the
surface against a key the row chose, which proves the row and the surface agree rather than
that the surface verifies anything.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

#: Where the served surface answers, from the developer's machine. Bridge mode with a mapped
#: port is what makes this address real rather than the VM's — measured, see research F1.
SURFACE_URL = os.environ.get("MCP_SURFACE_URL", "http://127.0.0.1:8083/mcp")

#: The development identity provider the lane starts. Real issuer, real JWKS, real flow.
IDP_ISSUER = os.environ.get("DEV_IDP_ISSUER", "http://127.0.0.1:8090")


class SurfaceUnreachable(RuntimeError):
    """Nothing replied. Distinct from a refusal, which is an answer (FR-007)."""


def _nomad(*args: str) -> str:
    """Run a scheduler command. **The address flag goes BEFORE the positionals.**

    `nomad alloc logs <alloc> server -address=X` exits 0 with a usage message and no output —
    it does not error. This session already paid 905 seconds to that exact shape once, in a
    different helper, and the failure it produces here is the worst kind: an empty log that
    reads as "the surface said nothing" when the surface said plenty.
    """
    addr = os.environ.get("NOMAD_ADDR", "http://127.0.0.1:4646")
    head, tail = list(args[:2]), list(args[2:])
    result = subprocess.run(  # noqa: S603 - fixed binary
        ["nomad", *head, f"-address={addr}", *tail],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout


def allocation() -> str | None:
    """The running allocation, or None. Flags go BEFORE positionals for `job allocs`."""
    addr = os.environ.get("NOMAD_ADDR", "http://127.0.0.1:4646")
    result = subprocess.run(  # noqa: S603 - fixed binary
        ["nomad", "job", "allocs", "-json", f"-address={addr}", "mcp-surface"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        allocs = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    running = [a for a in allocs if a.get("ClientStatus") == "running"]
    return str(running[0]["ID"]) if running else None


def allocation_output(alloc: str) -> str:
    """Both streams. The surface's readiness line is on stdout and its failures on stderr,
    and a failure report that showed only one would omit whichever mattered."""
    out = _nomad("alloc", "logs", alloc, "server")
    err = _nomad("alloc", "logs", "-stderr", alloc, "server")
    return f"{out}\n{err}"


# ------------------------------------------------------------------ the caller's credential


def caller_token(*, subject: str = "caller-1", tenant: str = "tenant-local", **claims: Any) -> str:
    """A real bearer token, obtained by walking the provider's real flow.

    PKCE, as a public client — the same exchange the portal performs. The verifier is
    generated here and never leaves; the challenge is its SHA-256, which is what makes the
    code redeemable only by whoever requested it.
    """
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).decode().rstrip("=")
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )

    query = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": "conformance",
            "redirect_uri": "http://127.0.0.1:0/callback",
            "state": secrets.token_urlsafe(8),
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "subject": subject,
            "tenant": tenant,
            **{k: json.dumps(v) if isinstance(v, list) else str(v) for k, v in claims.items()},
        }
    )

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a: Any, **k: Any) -> None:
            return None

    opener = urllib.request.build_opener(_NoRedirect)
    try:
        opener.open(f"{IDP_ISSUER}/authorize?{query}", timeout=10)
        raise SurfaceUnreachable("the provider did not redirect — no authorization code issued")
    except urllib.error.HTTPError as redirect:
        location = redirect.headers.get("Location", "")

    code = urllib.parse.parse_qs(urllib.parse.urlparse(location).query).get("code", [""])[0]
    if not code:
        raise SurfaceUnreachable(f"no authorization code in the redirect: {location!r}")

    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": "http://127.0.0.1:0/callback",
        }
    ).encode()
    with urllib.request.urlopen(  # noqa: S310 - fixed scheme, local provider
        urllib.request.Request(f"{IDP_ISSUER}/token", data=body, method="POST"), timeout=10
    ) as response:
        return str(json.loads(response.read())["access_token"])


# ------------------------------------------------------------------ the client, over a socket


async def _with_session(token: str | None, work: Any) -> Any:
    """Open a real MCP session against the served process and run `work(session)`.

    **The SDK's own client** (SC-001), unmodified, speaking the real protocol. A hand-rolled
    frame on this side would make every row a test of our framing rather than of the surface,
    and the two disagreeing is exactly what a conformance row should catch.
    """
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with streamablehttp_client(SURFACE_URL, headers=headers, timeout=30) as (
        read,
        write,
        _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await work(session)


def list_operations(token: str) -> list[str]:
    """What the surface says it exposes, asked over the protocol rather than read from source."""
    import anyio

    async def work(session: Any) -> list[str]:
        listed = await session.list_tools()
        return sorted(tool.name for tool in listed.tools)

    return list(anyio.run(_with_session, token, work))


def call(tool: str, arguments: dict[str, Any], *, token: str) -> dict[str, Any]:
    """One operation, as the holder of `token`. Returns the payload the surface answered."""
    import anyio

    async def work(session: Any) -> dict[str, Any]:
        # ARGUMENTS AS A CLIENT ACTUALLY SENDS THEM — flat, not wrapped.
        #
        # This read `{"arguments": arguments}` until 022, wrapping its own arguments in a key
        # named `arguments` because that is what the served surface published: every tool was
        # advertised as taking one object property of that name, since `add_tool` derives the
        # schema from the handler signature and the handler took `arguments: dict`.
        #
        # So these rows passed while 13 of 17 operations were uncallable by any conforming
        # client — a harness shaped to agree with the implementation rather than with what a
        # client sends. Found by driving the served process by hand.
        outcome = await session.call_tool(tool, arguments)
        if outcome.structuredContent is not None:
            return dict(outcome.structuredContent)
        text = "".join(block.text for block in outcome.content if hasattr(block, "text"))
        try:
            return dict(json.loads(text))
        except (json.JSONDecodeError, TypeError, ValueError):
            return {"raw": text, "isError": outcome.isError}

    return dict(anyio.run(_with_session, token, work))


def handshake_refused_without_credential() -> int:
    """The status a caller with no credential receives, BEFORE any operation is entered."""
    request = urllib.request.Request(
        SURFACE_URL,
        data=json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "conformance", "version": "0"},
                },
            }
        ).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return int(response.status)
    except urllib.error.HTTPError as refused:
        return int(refused.code)
    except OSError as exc:
        raise SurfaceUnreachable(f"{SURFACE_URL} answered nothing: {exc}") from exc
