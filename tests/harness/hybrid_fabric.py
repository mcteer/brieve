# SPDX-License-Identifier: Apache-2.0
"""Scaffolding: one resolution real, the rest faked. **Deleted at T046a.**

`manufacture_authority` resolves user scope, agent ceiling, and policy from a *single*
fabric object. That makes the four user stories non-independent by construction — no story
could be proven until all of them were done — unless something composes the terms. This
composes them.

**Why it lives in `tests/` and could not live anywhere else.** It imports the fake, and a
module under `src/` importing from `tests/` is FR-015's violation committed by the very
feature that asserts FR-015. The asymmetry is not an inconvenience; it is what makes the
arrangement legitimate. Production code has one fabric, which is real.

**Why it has an expiry rather than a future.** FR-014 says the fake survives for fault
injection only, and a hybrid row is not injecting a fault — it is exercising a real term
with the others stubbed. So it cannot be marked per FR-014 without putting a false
statement in the file, and it cannot stay unmarked without dodging the check that enforces
SC-001. The resolution is that hybrid rows carry their own transitional marker and this
module stops existing at the migration sweep. Scaffolding that survives its purpose
becomes the next feature's precedent, and this one is written to be removed.
"""

from __future__ import annotations

from typing import Any

from core.authority.types import AuthorityScope

#: The marker every row using this must carry, so the sweep can find them all.
#:
#: A comment rather than a decorator on purpose: it has to be greppable from outside the
#: process, by a check that reads files rather than imports them, because by the time an
#: import succeeds the module it is looking for is meant to be gone.
HYBRID_MARKER = "# HYBRID"


class HybridIdentityFabric:
    """Delegate named resolutions to a real fabric; fall back to the fake for the rest.

    Deliberately not clever. Each resolution is spelled out rather than routed through
    ``__getattr__``, because a dynamic proxy would silently forward a method added to the
    protocol later — and "silently forwarded to the fake" is exactly the outcome this
    whole feature exists to eliminate.
    """

    def __init__(self, *, real: Any, fake: Any, real_terms: frozenset[str]) -> None:
        unknown = real_terms - {"user_scope", "ceiling", "policy", "entitlements"}
        if unknown:
            # A typo here would silently route a term to the fake while the row's name
            # claimed it was real — a green test asserting nothing, which is worse than a
            # red one.
            raise ValueError(f"unknown hybrid term(s): {sorted(unknown)}")
        self._real = real
        self._fake = fake
        self._real_terms = real_terms

    def _source(self, term: str) -> Any:
        return self._real if term in self._real_terms else self._fake

    def resolve_user_scope(self, subject_user_id: str) -> AuthorityScope:
        return self._source("user_scope").resolve_user_scope(subject_user_id)  # type: ignore[no-any-return]

    def resolve_ceiling(self, agent_definition_id: str) -> AuthorityScope:
        return self._source("ceiling").resolve_ceiling(agent_definition_id)  # type: ignore[no-any-return]

    def resolve_policy(self, agent_definition_id: str) -> AuthorityScope | None:
        return self._source("policy").resolve_policy(agent_definition_id)  # type: ignore[no-any-return]

    def resolve_product_entitlements(self, subject_user_id: str, product: str) -> frozenset[str]:
        return self._source("entitlements").resolve_product_entitlements(  # type: ignore[no-any-return]
            subject_user_id, product
        )


__all__ = ["HYBRID_MARKER", "HybridIdentityFabric"]
