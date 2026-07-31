# SPDX-License-Identifier: Apache-2.0
"""Telling a machine's credential from a person's, from the token itself.

The surface used to **declare** what kind of subject a token established, at construction,
and assert it for every token it accepted. That works only while each kind arrives from
its own issuer. Auth0 — and Okta, and Ping, and Entra — serve `client_credentials` and
`authorization_code` from ONE issuer, one JWKS and one audience, so a declaration cannot
tell them apart and everything was recorded as a person.

Two things were wrong with that, and the second is worse than the labelling:

1. The evidence trail attributed a machine's actions to a human being.
2. A surface configured for people **accepted a machine's credential**. A leaked M2M
   client secret was a working operator login, and nothing in the trail would show it as
   anything other than someone signing in.

Pure claims logic with no dependency on how the token arrived, which is why it sits beside
`claims.py` rather than next to the JWT verification.

**There is no universal marker, and this does not pretend otherwise.** RFC 9068 §2.2 says
that for grants with no resource owner — `client_credentials` being the one that matters —
`sub` SHOULD identify the *client application* rather than a person. That is a SHOULD over
a value the authorization server picks, so it is recognisable rather than parseable. What
is checked below is the recognisable shapes, and a provider that marks its machine tokens
some other way will still read as a person: that residual gap is real, is why the check is
named for *evidence* rather than for truth, and is why `WORKLOAD` is never inferred from
the absence of evidence.
"""

from __future__ import annotations

from typing import Any

#: Auth0's own marker. Non-standard, checked anyway because it is unambiguous where it
#: appears, and a check that ignored the clearest available signal in favour of only
#: general ones would be principled at the cost of being wrong more often.
_CLIENT_CREDENTIALS_GRANT = "client-credentials"


def looks_like_a_machine_credential(claims: dict[str, Any]) -> bool:
    """True when the token carries positive evidence that no person was present.

    Positive evidence only. A token this returns ``False`` for is not thereby a person's
    — it is a token this cannot place, which is a different thing and is why the caller
    refuses rather than defaulting when it expected a machine.
    """
    if str(claims.get("gty", "")) == _CLIENT_CREDENTIALS_GRANT:
        return True

    # RFC 9068 §2.2. `azp` is the authorized party — the client the token was issued to.
    # When `sub` names that same client, the subject of the token IS the application, and
    # there is no end user for it to be about.
    party = str(claims.get("azp") or claims.get("client_id") or "").strip()
    subject = str(claims.get("sub") or "").strip()
    if not party or not subject:
        return False
    if subject == party:
        return True
    # Auth0 issues `{client_id}@clients`. The suffix scopes the identifier into a
    # namespace of clients; the part before the separator is still the client itself.
    # Anchored on the party rather than on the suffix, so this recognises the shape
    # without hard-coding one provider's choice of word.
    return subject.startswith(f"{party}@")


__all__ = ["looks_like_a_machine_credential"]
