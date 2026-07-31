# SPDX-License-Identifier: Apache-2.0
"""The token a grant becomes, and the signature Vault will honour (016, ADR-0056).

**No key material lives here.** The signing key is a Vault transit key and never leaves it;
this module assembles a JWT's signing input, asks Vault to sign it, and pastes the answer on
the end. The issuing service holds a Vault token obtained from its own attested workload
identity — the same credential every other component here holds — and nothing durable.

That is what makes ADR-0056's "no second standing credential" true rather than mitigated: a
service holding a private key would be a standing credential by any honest reading, and
Principle IV permits exactly one, already spent on the TFE broker.

**The wire format is Vault's, not ours.** `vault:path_access` is a type Vault defines and
evaluates; `jti` is mandatory because Vault's schema says so, not because we chose it. Where
this module looks opinionated it is usually transcribing.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Any

#: Identifies the issuer to Vault, matched literally against the resource-server profile's
#: `issuer_id`. A URL by convention and an identifier in fact — nothing resolves it.
DEFAULT_ISSUER = "https://harness.internal/task-authority"

#: The key id echoed in the JOSE header, matching the profile's registered `public_keys`.
DEFAULT_KEY_ID = "grant-issuer-1"

#: Where the signing key lives.
DEFAULT_SIGN_PATH = "task-authority/sign/grant-issuer"

#: Vault validates `aud` against the profile's `audiences`.
AUDIENCE = "vault"


class GrantTokenError(RuntimeError):
    """The grant could not be signed. Never swallowed — an unsigned grant is no grant."""


def build_signing_input(
    *,
    subject: str,
    authorization_details: list[dict[str, Any]],
    issued_at: datetime,
    expires_at: datetime,
    issuer: str = DEFAULT_ISSUER,
    key_id: str = DEFAULT_KEY_ID,
    jti: str | None = None,
) -> str:
    """The `header.payload` a signature is computed over.

    Separate from signing so the claim set can be asserted without a Vault round trip, and so
    a caller that already holds a signature can reassemble the token deterministically.

    ``jti`` is **mandatory** in the emitted claims. Vault rejects a token without one as a
    schema failure — and, unhelpfully, reports that only in its own server log while the
    caller sees a bare `403`. Generated here rather than accepted as optional, because the
    failure it prevents is among the hardest in this feature to diagnose.
    """
    header = _b64({"alg": "ES256", "typ": "JWT", "kid": key_id})
    claims: dict[str, Any] = {
        "iss": issuer,
        "aud": AUDIENCE,
        "sub": subject,
        "jti": jti or uuid.uuid4().hex,
        "iat": int(issued_at.timestamp()),
        # A little earlier than `iat`, because Vault compares against its own clock and a
        # token minted at the same instant it is presented can otherwise be "not yet valid".
        "nbf": int(issued_at.timestamp()) - 5,
        "exp": int(expires_at.timestamp()),
        "authorization_details": authorization_details,
    }
    return f"{header}.{_b64(claims)}"


def sign_grant_token(
    *,
    signing_input: str,
    vault_write: Any,
    sign_path: str = DEFAULT_SIGN_PATH,
) -> str:
    """Ask Vault to sign, and assemble the token.

    ``vault_write`` is a callable taking ``(path, payload)`` and returning Vault's response —
    injected rather than constructed so this module holds no client, no address, and no
    credential.

    ``marshaling_algorithm="jws"`` is not a preference. Transit marshals ECDSA signatures as
    ASN.1 by default, which JWS cannot read, and the `jws` form is documented as valid only
    for ECDSA P-256 — which is why the key is P-256 and the algorithm is ES256.
    """
    try:
        response = vault_write(
            sign_path,
            {
                "input": base64.b64encode(signing_input.encode()).decode(),
                "hash_algorithm": "sha2-256",
                "marshaling_algorithm": "jws",
            },
        )
        signature = str(response["data"]["signature"])
    except Exception as exc:  # noqa: BLE001 — the caller decides; an unsigned grant is fatal
        raise GrantTokenError(f"the grant could not be signed: {exc}") from exc

    # Vault answers `vault:v<n>:<signature>`. The version prefix is Vault's key-rotation
    # bookkeeping and means nothing to JWS, so only the last segment travels.
    return f"{signing_input}.{signature.split(':')[-1]}"


def _b64(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=False).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


__all__ = [
    "AUDIENCE",
    "DEFAULT_ISSUER",
    "DEFAULT_KEY_ID",
    "DEFAULT_SIGN_PATH",
    "GrantTokenError",
    "build_signing_input",
    "sign_grant_token",
]
