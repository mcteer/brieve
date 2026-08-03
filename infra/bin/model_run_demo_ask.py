# SPDX-License-Identifier: Apache-2.0
"""US4's closure, over the wire: the operator who ran the demonstration asks about it.

Before 031 this exact question declined for an operator — correctly, and the person whose run
was refused had to find a compliance analyst. The visibility decision moved `AUTHORITY_DENIED`
and `AUTHORITY_REFUSED` inside the operator's set, and this script is the deployed proof: a
token whose only mapped role is operator, the served API, and an answer that cites the very
refusal record the demonstration's over-scoped run produced.

Two shapes this deployment forces, both measured rather than assumed:

- **The token is Auth0's**, minted by client credentials from `.env`. The enclave's claim
  mapping holds exactly one row — ``permissions: platform:operator → operator`` — so this
  token resolves to the operator role and nothing else, and the tenant claim it carries is
  ``tenant-local``, the same tenant the dispatched runs wrote under. A hand-built JWT would
  prove this script can sign things, not that the platform's login path yields an identity
  the ask surface honours.

- **The request is issued from INSIDE the allocation** through the scheduler, the same way
  `tests/conformance/deployment/conftest.py` reaches every served surface: both surfaces use
  host networking, and on Docker Desktop for macOS the "host" is a virtual machine this shell
  is not inside (verified 2026-07-31 — a shell curl returns nothing while the same request
  from inside the allocation answers).
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
QUESTION = "Which runs were denied?"

#: The deployment lane's measured cold-start budget: the allocation installs its
#: dependencies before serving, so a restarted API is legitimately slow.
READY_BUDGET = 180.0


def env_value(name: str) -> str:
    for line in (REPO / ".env").read_text().splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def operator_token() -> str:
    domain = env_value("AUTH0_DOMAIN")
    request = urllib.request.Request(
        f"https://{domain}/oauth/token",
        data=json.dumps(
            {
                "client_id": env_value("AUTH0_CLIENT_ID"),
                "client_secret": env_value("AUTH0_CLIENT_SECRET"),
                "audience": env_value("AUTH0_API_AUDIENCE"),
                "grant_type": "client_credentials",
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 — fixed scheme
        token = str(json.load(response).get("access_token", ""))
    if not token:
        print("FAIL: Auth0 issued no access token — check the AUTH0_* values in .env")
        raise SystemExit(2)
    return token


def running_api_allocation() -> str:
    status = subprocess.run(
        ["nomad", "job", "status", "api"], capture_output=True, text=True, check=True
    ).stdout
    for line in status.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[5] == "running" and len(parts[0]) == 8:
            return parts[0]
    print("FAIL: the api job has no running allocation — run `infra/bin/portal-up`")
    raise SystemExit(2)


def ask_from_inside(alloc: str, token: str) -> dict[str, object]:
    script = f"""
import json, urllib.request
request = urllib.request.Request(
    "http://127.0.0.1:8081/ask",
    data=json.dumps({{"question": {QUESTION!r}}}).encode(),
    headers={{"Content-Type": "application/json", "Authorization": "Bearer {token}"}},
)
try:
    with urllib.request.urlopen(request, timeout=170) as r:
        print("\\x00" + json.dumps(dict(status=r.status, body=json.load(r))))
except urllib.error.HTTPError as e:
    print("\\x00" + json.dumps(dict(status=e.code, body=json.loads(e.read() or b"{{}}"))))
"""
    result = subprocess.run(
        ["nomad", "alloc", "exec", "-task", "server", alloc, "python3", "-c", script],
        capture_output=True,
        text=True,
        timeout=200.0,
        check=False,
    )
    marker = result.stdout.find("\x00")
    if marker == -1:
        print(f"FAIL: nothing answered from inside the allocation: {result.stderr[-500:]}")
        raise SystemExit(2)
    return json.loads(result.stdout[marker + 1 :].splitlines()[0])


def wait_until_answerable(alloc: str) -> None:
    """A readiness poll, not a retry: wait for the surface to answer, then assert once.

    The restarted allocation reinstalls its dependencies before binding, so the first
    minutes of silence are a young deployment, not a broken one — the deployment lane's
    distinction, applied here.
    """
    probe = (
        "import urllib.request, urllib.error\n"
        "try:\n"
        "    urllib.request.urlopen('http://127.0.0.1:8081/runs', timeout=5)\n"
        "except urllib.error.HTTPError:\n"
        "    print('\\x00up')\n"
        "except Exception:\n"
        "    pass\n"
    )
    deadline = time.monotonic() + READY_BUDGET
    while time.monotonic() < deadline:
        result = subprocess.run(
            ["nomad", "alloc", "exec", "-task", "server", alloc, "python3", "-c", probe],
            capture_output=True,
            text=True,
            timeout=60.0,
            check=False,
        )
        if "\x00up" in result.stdout:
            return
        time.sleep(5.0)
    print(f"FAIL: the api never became answerable within {READY_BUDGET:.0f}s of its restart")
    raise SystemExit(2)


def main() -> int:
    runs = json.loads(Path(sys.argv[1]).read_text())
    citable = set(runs["citable_hashes"])

    alloc = running_api_allocation()
    wait_until_answerable(alloc)
    response = ask_from_inside(alloc, operator_token())
    answer = response["body"]
    assert isinstance(answer, dict)

    print(f"  operator asked: {QUESTION!r}")
    print(f"  HTTP {response['status']}, disposition: {answer.get('disposition')!r}")
    if response["status"] != 200 or answer.get("disposition") != "answered":
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
