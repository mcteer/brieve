# SPDX-License-Identifier: Apache-2.0
"""Reaching a deployed surface, and the waits that bound it.

**Requests are issued from INSIDE the allocation**, through the scheduler, never from this
shell. Both served surfaces use host networking, so on a Linux runner the host *is* the
runner and a shell reaches `127.0.0.1:8081`; on Docker Desktop for macOS the "host" is a
virtual machine the developer's shell is not inside. Verified on 2026-07-31: `curl` from the
shell returned nothing while the same request from inside the allocation returned
`401 absent_identity`. A row that curled from the shell would pass in CI and fail locally for
a reason having nothing to do with the tree, which breaks FR-008 and Principle VII's
identical-suite requirement.

**There is exactly one wait loop in this package, and it is here.** FR-014 forbids retrying a
failed assertion, and a readiness poll is textually indistinguishable from an assertion
retry — so the distinction is structural: a retry is a **loop containing an assertion**,
and `test_no_retry_and_no_skip.py` checks that no other module has one. Loops over data are
fine anywhere; loops over an attempt are not.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass

import pytest

from tests.conformance.deployment import surfaces

NOMAD_ADDR = "http://127.0.0.1:4646"

#: How long each process may take to reach a working state.
#:
#: **Measured, not guessed.** Each allocation installs its dependencies before serving, so a
#: cold cache is slow and legitimately so. These are set well above the observed cold start
#: on this repository's runner; a wait set from a guess fails on the first cold cache and
#: reads as a broken surface, which is the misdiagnosis FR-004 exists to prevent.
WAITS = {"api": 180.0, "portal": 180.0}
DEFAULT_WAIT = 180.0

#: What an unknown job waits. A surface the scheduler has never heard of will not appear
#: however long anyone waits, and the break rows assert exactly that — so they fail fast
#: instead of burning a cold-start budget on a certainty.
UNKNOWN_JOB_WAIT = 5.0

#: Anything that looks like a bearer token or a Vault token in captured output. Allocation
#: output is exactly where a credential surfaces, and FR-004 requires printing it.
_REDACTIONS = (
    ("eyJ", "<redacted-jwt>"),
    ("hvs.", "<redacted-vault-token>"),
    ("hvb.", "<redacted-vault-token>"),
)


class SurfaceUnreachable(AssertionError):
    """The surface never reached a working state. Never a skip (FR-006)."""


@dataclass(frozen=True)
class Response:
    status: int
    body: str
    headers: dict[str, str]

    def header(self, name: str) -> str:
        """Case-insensitive lookup. HTTP header names are case-insensitive; a dict is not.

        uvicorn sends `location`, the RFC writes `Location`, and a row that asked for the
        second found nothing and reported "redirected with no Location" against a redirect
        that carried one. Asserting against a correct deployment and losing is how a gate
        stops being believed.
        """
        wanted = name.lower()
        return next((value for key, value in self.headers.items() if key.lower() == wanted), "")


def redact(text: str) -> str:
    """Blank anything token-shaped, per word, before it reaches the report."""
    out = []
    for word in text.split():
        for prefix, mask in _REDACTIONS:
            if prefix in word:
                word = mask
                break
        out.append(word)
    return " ".join(out)


def _nomad(
    *subcommand: str,
    args: tuple[str, ...] = (),
    flags: tuple[str, ...] = (),
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Run a Nomad command with the address flag where Nomad actually accepts it.

    **After the full subcommand, before any positional.** Both other placements fail, and
    neither fails loudly:

        nomad job -address=X status api   -> usage error; the flag hits a command group
        nomad job status api -address=X   -> "takes either no arguments or one", AND EXITS 0

    The second is why this signature separates subcommand words from positionals rather than
    taking one flat list. It is also why the parse is the check: a usage error here returns
    zero, so `returncode == 0` proves nothing and code that trusted it read garbage as an
    empty result.

    Cost of getting this wrong, measured: every allocation lookup answered "no allocation was
    ever placed" against surfaces that were demonstrably running, and five rows each burned a
    full 180-second wait before saying so. Found by running the lane, not by reading it —
    which is the argument this feature makes about assemblies, arriving one level up.
    """
    return subprocess.run(  # noqa: S603 - fixed binary, arguments built here
        ["nomad", *subcommand, f"-address={NOMAD_ADDR}", *flags, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _job_exists(job: str) -> bool:
    """Whether the scheduler knows this job at all."""
    return _nomad("job", "status", args=(job,)).stdout.strip().startswith("ID")


def running_allocation(job: str) -> str | None:
    """The id of this job's RUNNING allocation.

    Filtered by status rather than by position. `nomad job status` sorts the stopped
    allocation last, so taking the final row returns a dead one — which cost a wrong reading
    on 2026-07-31, when a restarted API was diagnosed against the allocation it replaced.
    """
    result = _nomad("job", "status", args=(job,))
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[5] == "running" and len(parts[0]) == 8:
            return parts[0]
    return None


def restart_count(job: str) -> int:
    """How many allocations this job has burned through. More than one means flapping."""
    result = _nomad("job", "status", args=(job,))
    return sum(
        1
        for line in result.stdout.splitlines()
        if len(parts := line.split()) >= 6 and parts[5] in {"failed", "complete"}
    )


def allocation_stderr(alloc: str, task: str = "server") -> str:
    """The failing process's own account, redacted. FR-004."""
    result = _nomad("alloc", "logs", flags=("-stderr", "-task", task), args=(alloc,))
    return redact(result.stdout or result.stderr)[-2000:]


def wait_for_working_state(job: str) -> str:
    """Block until this job has a running allocation, or fail naming the job.

    **The only wait in this package.** Fails rather than waiting indefinitely (FR-002), and
    reports the process's own error rather than only that the wait elapsed (FR-004).
    """
    budget = WAITS.get(job, DEFAULT_WAIT if _job_exists(job) else UNKNOWN_JOB_WAIT)
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        alloc = running_allocation(job)
        if alloc:
            return alloc
        time.sleep(2.0)

    alloc = running_allocation(job) or _last_allocation(job)
    detail = allocation_stderr(alloc) if alloc else "(no allocation was ever placed)"
    raise SurfaceUnreachable(
        f"{job} did not reach a working state within {budget:.0f}s.\n"
        f"--- {job}'s own output ---\n{detail}"
    )


def _last_allocation(job: str) -> str | None:
    result = _nomad("job", "status", args=(job,))
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 6 and len(parts[0]) == 8 and parts[3] in {"run", "stop"}:
            return parts[0]
    return None


def require_running(job: str) -> str:
    """A process that is absent, unschedulable, or flapping is a FAILURE, never a skip.

    There is no `pytest.skip` anywhere in this package, and that is asserted rather than
    left to discipline — a gate that skips when the thing it guards is missing reports green
    for the one state it exists to catch.
    """
    alloc = wait_for_working_state(job)
    burned = restart_count(job)
    if burned > 1:
        raise SurfaceUnreachable(
            f"{job} is running now but has burned {burned} allocations — it is flapping, "
            f"which observing the current state alone would have reported as healthy.\n"
            f"--- {job}'s own output ---\n{allocation_stderr(alloc)}"
        )
    return alloc


def _attempt(alloc: str, path: str, method: str) -> Response | None:
    """One request from inside the allocation. `None` when nothing answered."""
    script = f"""
import json, os, ssl, urllib.request, urllib.error


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


# HTTPS, VERIFIED AGAINST THE CONTROL PLANE'S OWN CA — never unverified.
#
# The portal serves TLS because its session cookie is `__Host-` prefixed and therefore
# `Secure`, which Safari refuses over plain HTTP. This probe runs INSIDE an allocation,
# where the working tree is mounted at /src, so the CA the enclave issued from is right
# there. Turning verification off instead would make this row pass against a surface
# presenting any certificate at all, which is a weaker assertion than the one it makes now.
_ctx = None
if {path!r}.startswith("https:"):
    _ca = "/src/.enclave/ca.pem"
    if not os.path.exists(_ca):
        raise SystemExit(f"no CA at {{_ca}} — an https probe cannot verify anything")
    _ctx = ssl.create_default_context(cafile=_ca)

opener = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=_ctx))
req = urllib.request.Request({path!r}, method={method!r})
try:
    with opener.open(req, timeout=20) as r:
        out = dict(status=r.status, body=r.read()[:2000].decode(errors="replace"),
                   headers=dict(r.headers))
except urllib.error.HTTPError as e:
    out = dict(status=e.code, body=e.read()[:2000].decode(errors="replace"),
               headers=dict(e.headers))
print("\\x00" + json.dumps(out))
"""
    result = subprocess.run(  # noqa: S603 - fixed binary
        [
            "nomad",
            "alloc",
            "exec",
            f"-address={NOMAD_ADDR}",
            "-task",
            "server",
            alloc,
            "python3",
            "-c",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=90.0,
        check=False,
    )
    marker = result.stdout.find("\x00")
    if marker == -1:
        return None
    payload = json.loads(result.stdout[marker + 1 :].splitlines()[0])
    return Response(status=payload["status"], body=payload["body"], headers=payload["headers"])


def exec_request(job: str, path: str, *, method: str = "GET") -> Response:
    """Wait for the surface to ANSWER, then return what it answered.

    **Placed is not working**, and conflating them is the mistake this gate exists to
    catch, one level in. An allocation reports `running` the moment the container starts —
    while it is still installing dependencies and long before the process binds. A wait
    that stopped there handed the rows a surface that had not finished assembling, and they
    failed against a deployment that was merely young.

    Redirects are NOT followed: what this gate asks is what the SURFACE answered. Following
    one would report the identity provider's response instead, so a portal misconfigured to
    redirect somewhere wrong would look identical to a correct one.

    This is the second half of the package's single bounded wait, and it is a **readiness
    poll, not a retry**: it waits for the surface to become answerable, then the caller
    asserts once on the answer. FR-014 forbids re-running a failed assertion, which this
    never does — a response that arrives and is wrong is returned, not retried.
    """
    budget = WAITS.get(job, DEFAULT_WAIT)
    deadline = time.monotonic() + budget
    alloc = require_running(job)
    last: Response | None = None
    while time.monotonic() < deadline:
        last = _attempt(alloc, path, method)
        if last is not None:
            return last
        time.sleep(3.0)
        alloc = running_allocation(job) or alloc

    raise SurfaceUnreachable(
        f"{job} answered nothing at {path} within {budget:.0f}s. This is 'nothing replied', "
        f"which FR-009 requires be distinguished from 'the surface refused'.\n"
        f"--- {job}'s own output ---\n{allocation_stderr(alloc)}"
    )


@pytest.fixture(scope="session")
def declared_processes() -> list[surfaces.DeclaredProcess]:
    return surfaces.declared()
