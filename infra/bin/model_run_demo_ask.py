# SPDX-License-Identifier: Apache-2.0
"""US4's closure, over the wire: the operator who ran the demonstration asks about it.

Before 031 this exact question declined for an operator — correctly, and the person whose run
was refused had to find a compliance analyst. The visibility decision moved `AUTHORITY_DENIED`
and `AUTHORITY_REFUSED` inside the operator's set, and this script is the deployed proof: an
operator token, a served surface, and an answer that cites the very refusal record the
demonstration's over-scoped run produced.

**Which served surface, and why — a measurement, not a preference.** The first wire attempt
went to the northbound API with an Auth0 client-credentials token, and the API refused it:
``subject_kind_mismatch``. That refusal is a feature this platform built deliberately — a
machine's credential must never work where a person's is expected, or a leaked client secret
is an operator login — and it means the Auth0-configured API is askable only by an actual
browser sign-in. The served MCP surface is the platform's supported non-interactive path: it
runs against the quarantined development provider (`DEV_IDP=1 mcp-surface-up`), whose
authorization-code flow this script walks for real — PKCE, redirect, exchange — through the
same `tests/conformance/mcp_served/surfaces.py` harness the conformance lane uses. Same core
ask path, same visibility narrowing, a token shaped like a person's because it came from the
flow a person's comes from.

The claims asked for are exactly one role's worth: ``permissions=["platform:operator"]``,
tenant ``tenant-local`` — the tenant the dispatched runs wrote under.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

QUESTION = "Which runs were denied?"

#: The freshly submitted allocation installs its dependencies before serving — the same
#: measured cold-start the deployment lane budgets for its surfaces.
READY_BUDGET = 240.0


def wait_for_surface(mcp) -> str:  # noqa: ANN001 — the harness module, passed to avoid a re-import
    """ONE loop that resolves the allocation and probes the protocol (the api taught this:
    placement and answering are separate waits, and they interleave with restarts)."""
    token = mcp.caller_token(
        subject="demo-operator", tenant="tenant-local", permissions=["platform:operator"]
    )
    deadline = time.monotonic() + READY_BUDGET
    while time.monotonic() < deadline:
        if mcp.allocation() is not None:
            try:
                if "ask" in mcp.list_operations(token):
                    return token
            except Exception:  # noqa: BLE001 — not-yet-serving looks like many exception types
                pass
        time.sleep(5.0)
    print(f"FAIL: the served MCP surface never answered within {READY_BUDGET:.0f}s of submit")
    raise SystemExit(2)


def main() -> int:
    from tests.conformance.mcp_served import surfaces as mcp

    runs = json.loads(Path(sys.argv[1]).read_text())
    citable = set(runs["citable_hashes"])

    token = wait_for_surface(mcp)
    answer = mcp.call("ask", {"question": QUESTION}, token=token)

    print(f"  operator asked: {QUESTION!r}")
    print(f"  disposition: {answer.get('disposition')!r}")
    if answer.get("disposition") != "answered":
        print(f"FAIL: the operator's question did not answer: {json.dumps(answer)[:600]}")
        return 2

    cited = {
        str(reference)
        for claim in answer.get("claims", [])
        for reference in claim.get("references", [])
    }
    overlap = cited & citable
    for claim in answer.get("claims", []):
        print(f"  claim: {claim.get('statement')!r}")
    if not overlap:
        print(
            f"FAIL: the answer cites {sorted(h[:16] for h in cited)} but none of the "
            f"demonstration's refusal records {sorted(h[:16] for h in citable)} — the loop "
            f"is not closed"
        )
        return 2
    cited_hash = next(iter(overlap))
    print(
        f"  SC-003: the answer rests on the refusal the demonstration produced ({cited_hash[:16]}…)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
