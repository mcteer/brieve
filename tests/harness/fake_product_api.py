# SPDX-License-Identifier: Apache-2.0
"""Fake product API — records wields; federate/broker modes for tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeProductApi:
    mode: str = "broker"
    wields: list[dict[str, str]] = field(default_factory=list)

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


def fake_product_api(*, mode: str = "broker") -> FakeProductApi:
    return FakeProductApi(mode=mode)
