#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Seed the development claim mapping when the trust store has none.

The dev identity provider mints ``permissions=["platform:operator"]`` by default. Without
a matching record in the trust store, sign-in succeeds and every API call answers
``403 unmapped_claim`` — which looks like the platform is broken.

Idempotent: exits 0 when the mapping is already present. Intended for development estates
only; production mappings are approved through the Control Group (ADR-0016).
"""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = "harness-authority/data/claim-mappings"
METADATA_PATH = "harness-authority/metadata/claim-mappings"
RECORD = {
    "claim_name": "permissions",
    "claim_value": "platform:operator",
    "role": "operator",
    "requested_by": "enclave-bootstrap",
}


def _mapping_key(claim_name: str, claim_value: str, role: str) -> str:
    """Stable record name — same algorithm as `core.identity.mappings_store.mapping_key`."""
    digest = hashlib.sha256("\x00".join((claim_name, claim_value, role)).encode()).hexdigest()[:16]
    return f"{role.lower()}-{digest}"


def _env(key: str) -> str:
    env = ROOT / ".env"
    if not env.is_file():
        return os.environ.get(key, "")
    for line in env.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"')
    return os.environ.get(key, "")


def _request(
    addr: str,
    path: str,
    *,
    token: str,
    cacert: str,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object]]:
    ctx = ssl.create_default_context(cafile=cacert) if cacert else None
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(  # noqa: S310
        f"{addr.rstrip('/')}/v1/{path}",
        data=data,
        headers={"X-Vault-Token": token, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:  # noqa: S310
            body = response.read()
            parsed: dict[str, object] = json.loads(body) if body else {}
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            err: dict[str, object] = json.loads(body) if body else {}
            return exc.code, err
        except json.JSONDecodeError:
            return exc.code, {"raw": body.decode(errors="replace")}


def main() -> int:
    addr = _env("VAULT_ADDR") or "http://127.0.0.1:8200"
    token = os.environ.get("VAULT_TOKEN") or _env("VAULT_ROOT_TOKEN")
    cacert = _env("VAULT_CACERT")
    if not token:
        print("seed-dev-claim-mapping: no Vault token available", file=sys.stderr)
        return 1

    mapping_key = _mapping_key(RECORD["claim_name"], RECORD["claim_value"], RECORD["role"])

    status, body = _request(addr, METADATA_PATH, token=token, cacert=cacert, method="LIST")
    if status == 200:
        keys = body.get("data", {})
        if isinstance(keys, dict):
            listed = keys.get("keys", [])
            if isinstance(listed, list) and mapping_key in listed:
                print("ok dev claim mapping already present")
                return 0

    status, body = _request(
        addr,
        f"{DATA_PATH}/{mapping_key}",
        token=token,
        cacert=cacert,
        method="POST",
        payload={"data": RECORD},
    )
    if status not in (200, 204):
        print(f"seed-dev-claim-mapping: vault answered {status}: {body}", file=sys.stderr)
        return 1
    print("ok seeded dev claim mapping (permissions:platform:operator -> operator)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
