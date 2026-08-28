# SPDX-License-Identifier: Apache-2.0
"""Borrowing a real run's authority, for rows that must attempt a real break-in (054, T011a).

**Why this is not `bounding_records.run_authority()`.** 018 mints a run-shaped token from the
run's policy names with `auth/token/create`. That token has **no identity entity**, and 054's
grant is templated on the entity — so it would be refused everything, including its own
workspace, and the refusal rows would go green while asserting nothing. E4 is the row that
catches that, and this module is what lets E4 pass honestly.

**Three cheaper routes are closed** (054 research R7), all measured rather than assumed:

1. `auth/token/create` — no entity, as above.
2. Reading a dispatched allocation's JWT from outside: Nomad answers *"Reading secret file
   prohibited"*. The scheduler behaving correctly; not to be worked around.
3. Borrowing an existing job's identity: `agent_run_job_id_patterns` is listed explicitly
   rather than globbed, so nothing else matches the role.

**So the enclave runs a probe that does nothing but hold an attested identity**
(`infra/jobs/run-probe.nomad.hcl`), admitted to the `agent-run` role by a pattern set in the
dev and conformance environments and absent from the module default. Production's bound claims
are untouched.

**The credential never leaves the allocation.** The attempt runs *inside*, through
`nomad alloc exec`, and only verdicts come back. A helper that returned the token would put a
run's authority in the test process's environment, which is what ADR-0058 refuses one layer up.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

#: The job whose only purpose is to hold a run-shaped identity a row can borrow.
PROBE_JOB = "harness-run-probe"


class ProbeUnavailable(RuntimeError):
    """The probe is not running, so a row cannot attempt anything under run authority.

    Raised rather than skipped: a row that quietly passes when it could not make its attempt
    is the failure 054 exists to prevent, wearing the suite's own clothes.
    """


@dataclass(frozen=True)
class Attempt:
    """What a run's authority got when it tried one thing."""

    action: str
    path: str
    status: int


def probe_allocation() -> str:
    """The running probe's allocation id, or raise."""
    if shutil.which("nomad") is None:
        raise ProbeUnavailable("the nomad CLI is not on PATH; these rows drive the scheduler")
    out = subprocess.run(  # noqa: S603
        ["nomad", "job", "status", "-json", PROBE_JOB],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
    )
    if out.returncode != 0:
        raise ProbeUnavailable(
            f"{PROBE_JOB} is not registered. `make dev-up` places it; it is admitted to the "
            "agent-run role in dev and conformance only."
        )
    allocs = subprocess.run(  # noqa: S603
        ["nomad", "job", "allocs", "-json", PROBE_JOB],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=30,
    )
    running = [
        a["ID"] for a in json.loads(allocs.stdout or "[]") if a.get("ClientStatus") == "running"
    ]
    if not running:
        raise ProbeUnavailable(f"{PROBE_JOB} has no running allocation to borrow authority from")
    return str(running[0])


#: Run inside the allocation. Logs in exactly as a dispatched run does, then reports verdicts.
#:
#: Everything it needs is already in the allocation: its own JWT, the control-plane CA, and the
#: allocation id that names its workspace. Nothing is passed in but the foreign path to try.
_ATTEMPT = r"""
import json, os, ssl, sys, urllib.request, urllib.error
ctx = ssl.create_default_context(cafile="/repo/.enclave/ca.pem")
ADDR = "https://127.0.0.1:8200"
jwt = open(os.environ["NOMAD_SECRETS_DIR"] + "/nomad_vault.jwt").read().strip()

def call(path, token=None, method="GET", body=None):
    req = urllib.request.Request(ADDR + "/v1/" + path, method=method,
        data=json.dumps(body).encode() if body else None)
    if token:
        req.add_header("X-Vault-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code

status = call("auth/nomad/login", method="POST", body={"role": "agent-run", "jwt": jwt})
if status != 200:
    print(json.dumps({"error": "login failed", "status": status}))
    sys.exit(0)

req = urllib.request.Request(ADDR + "/v1/auth/nomad/login", method="POST",
    data=json.dumps({"role": "agent-run", "jwt": jwt}).encode())
with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
    token = json.loads(r.read())["auth"]["client_token"]

alloc = os.environ["NOMAD_ALLOC_ID"]
own = "sys/policies/acl/scratch-agent-" + alloc + "-current"
foreign = "sys/policies/acl/" + sys.argv[1]
doc = {"policy": 'path "secret/data/x" { capabilities = ["read"] }'}

out = [
    {"action": "write", "path": "own", "status": call(own, token, "PUT", doc)},
    {"action": "read", "path": "own", "status": call(own, token)},
    {"action": "read", "path": "foreign", "status": call(foreign, token)},
    {"action": "write", "path": "foreign", "status": call(foreign, token, "PUT", doc)},
    {"action": "delete", "path": "foreign", "status": call(foreign, token, "DELETE")},
]
call(own, token, "DELETE")
print(json.dumps(out))
"""


def attempt_under_run_authority(foreign_policy: str) -> list[Attempt]:
    """Log in as a run inside the probe, try its own workspace and a foreign one.

    `foreign_policy` is a policy NAME in the measurement namespace belonging to another run;
    the caller seeds and removes it with administrator authority.
    """
    alloc = probe_allocation()
    out = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "nomad",
            "alloc",
            "exec",
            "-task",
            "idle",
            alloc,
            "python3",
            "-c",
            _ATTEMPT,
            foreign_policy,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    body = (out.stdout or "").strip().splitlines()
    if not body:
        raise ProbeUnavailable(f"the probe returned nothing: {out.stderr.strip()[:200]}")
    parsed = json.loads(body[-1])
    if isinstance(parsed, dict) and "error" in parsed:
        raise ProbeUnavailable(f"the probe could not log in as a run: {parsed}")
    return [Attempt(a["action"], a["path"], a["status"]) for a in parsed]
