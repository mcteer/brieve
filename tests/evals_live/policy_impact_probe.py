# SPDX-License-Identifier: Apache-2.0
"""PL1 — one impact check against the real Vault, with the answer printed (042, T019).

**The smoke lane's shape, for the same reason it exists.** `tests/evals_live/smoke.py` records
what its absence cost: six full runs of a twenty-eight-minute lane, four of which existed only
to surface a defect visible in a single call with the response printed. This is that call for
the policy instrument.

A conformance row reports pass or fail. What this shows is the **raw capability answer** —
which is what you need when the question is "does Vault mean what the handler assumes", and
the failure modes are things like a glob path answering differently than a literal one, or a
KV v2 `data/` prefix changing the capability set.

    make dev-up
    VAULT_TOKEN=... python tests/evals_live/policy_impact_probe.py

Fails rather than skips without a reachable Vault: an unrunnable probe reporting success is
the shape this estate refuses.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from core.durability.credentials import VaultDatabaseCredentials  # noqa: E402
from surfaces import handlers  # noqa: E402

RUN = "probe-042"

CURRENT = """path "secret/data/payments/*" {
  capabilities = ["read"]
}
"""

PROPOSED = """path "secret/data/payments/*" {
  capabilities = ["read", "create", "update"]
}

path "secret/metadata/payments/*" {
  capabilities = ["list"]
}
"""


class _Token:
    """The operator's token, presented directly rather than exchanged."""

    def jwt(self) -> str:  # pragma: no cover
        raise AssertionError("this probe presents a token, not an identity")


def main() -> int:
    token = os.environ.get("VAULT_TOKEN", "").strip()
    if not token:
        print("VAULT_TOKEN is unset; this probe measures against the real Vault", file=sys.stderr)
        return 2

    client = VaultDatabaseCredentials(
        identity=_Token(),
        vault_addr=os.environ.get("VAULT_ADDR", "https://127.0.0.1:8200"),
    )
    client.login = lambda: token  # type: ignore[method-assign]
    handlers._fabric = lambda: client

    print("--- current policy")
    print(CURRENT)
    print("--- proposed policy")
    print(PROPOSED)

    try:
        impact = handlers.vault_policy_impact(
            {"run_id": RUN, "current_document": CURRENT, "proposed_document": PROPOSED}
        )
    except Exception as exc:  # noqa: BLE001 — the point is to see what went wrong
        print(f"IMPACT FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(f"--- measured by {impact['measured_by']}, truncated={impact['truncated']}")
    for entry in impact["results"]:
        print(f"  {entry['path']}")
        print(f"      current  : {entry['current']}")
        print(f"      proposed : {entry['proposed']}")
        print(f"      granted  : {entry['granted']}")
        print(f"      revoked  : {entry['revoked']}")
        if entry["unanswered"]:
            print("      UNANSWERED — Vault did not report for this path")

    # The claim that matters most, checked rather than asserted in prose.
    surviving = [
        name
        for name in (client.list_path("sys/policies/acl") or [])
        if name.startswith(f"scratch-agent-{RUN}")
    ]
    if surviving:
        print(f"\nSCRATCH SURVIVED: {surviving} — the finally block did not run", file=sys.stderr)
        return 1
    print("\nzero scratch policies survived; the measurement left nothing behind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
