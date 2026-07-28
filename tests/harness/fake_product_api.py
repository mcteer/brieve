# SPDX-License-Identifier: Apache-2.0
"""Fake product API — records wields; federate/broker modes for tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeProductApi:
    mode: str = "broker"
    wields: list[dict[str, str]] = field(default_factory=list)

    #: What each user may do inside this product, as the product itself would answer.
    #:
    #: 010 made the *seam* real while leaving the product faked, which is the line the
    #: constitution draws: a managed product's authorization system is outside this
    #: platform's boundary, and the interface that asks it is not.
    entitlements: dict[str, frozenset[str]] = field(default_factory=dict)

    #: Whether the product can be asked at all. `True` models an outage, and the
    #: distinction matters more than it looks: unanswerable is neither empty nor full, and
    #: a source that returned empty on failure would deny with a reason nobody decided.
    unreachable: bool = False

    @property
    def call_count(self) -> int:
        return len(self.wields)

    @property
    def executions(self) -> int:
        return len(self.wields)

    def wield(
        self,
        *,
        subject_user_id: str,
        action: str,
        credential_id: str | None = None,
    ) -> dict[str, str]:
        record = {
            "subject_user_id": subject_user_id,
            "action": action,
            "credential_id": credential_id or "",
            "mode": self.mode,
        }
        self.wields.append(record)
        return {"ok": "true", **record}

    def entitlements_for(self, subject_user_id: str, product: str) -> frozenset[str]:
        """Answer as a real product would — or refuse, as an unreachable one does."""
        from core.authority.errors import ResolutionRefused

        if self.unreachable:
            raise ResolutionRefused(
                f"product {product!r} could not be asked what {subject_user_id!r} may do",
                reason_code="entitlement_unavailable",
            )
        return self.entitlements.get(subject_user_id, frozenset())


def fake_product_api(*, mode: str = "broker") -> FakeProductApi:
    return FakeProductApi(mode=mode)
