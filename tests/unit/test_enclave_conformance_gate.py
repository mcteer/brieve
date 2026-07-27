# SPDX-License-Identifier: Apache-2.0
"""The durability gate must report the run in front of it, and say which answer it has.

Three failures lived here, and all three were silent — the gate went on printing a
verdict while meaning something else by it. They are driven against a stubbed `nomad`
rather than a real enclave: what is under test is the SCRIPT'S reasoning about the
scheduler, not the scheduler.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "infra" / "bin" / "enclave-conformance"

# Emulates just enough of the CLI for the script's control flow. `state` and `exit_code`
# are the two axes the gate has to reason about; every invocation is appended to a log so
# a test can assert on the ORDER of calls, which is where the stale-replay bug lived.
STUB_NOMAD = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
with open(os.environ["STUB_CALLS"], "a") as fh:
    fh.write(" ".join(args) + "\\n")

state = os.environ.get("STUB_STATE", "dead")
exit_code = int(os.environ.get("STUB_EXIT_CODE", "0"))

if args[:2] == ["job", "status"]:
    print("Allocations")
    print("ID        Node ID   Task Group  Version  Desired  Status   Created  Modified")
    print("abcd1234  bcb3a8e3  durability  0        run      running  1s ago   1s ago")
elif args[:2] == ["alloc", "status"]:
    events = [{"Type": "Terminated", "ExitCode": exit_code}] if state == "dead" else []
    print(json.dumps({"TaskStates": {"pytest": {"State": state, "Events": events}}}))
elif args[:2] == ["alloc", "logs"]:
    print("stub streamed log line")
    # `-f` never returns on a dead task in the real CLI (Nomad 2.0.4). Reproduced here,
    # because the fix is precisely that the script must not wait on it.
    if "-f" in args:
        import time

        time.sleep(3600)
sys.exit(0)
"""

STUB_CURL = "#!/bin/sh\nexit 0\n"


def _bin_dir(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("nomad", STUB_NOMAD), ("curl", STUB_CURL)):
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(0o755)
    return bin_dir


def _run_gate(
    tmp_path: Path, *, state: str = "dead", exit_code: int = 0, wait_secs: int = 4
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    calls = tmp_path / "calls.log"
    calls.touch()
    bin_dir = _bin_dir(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "STUB_CALLS": str(calls),
        "STUB_STATE": state,
        "STUB_EXIT_CODE": str(exit_code),
        "CONFORMANCE_WAIT_SECS": str(wait_secs),
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT)], capture_output=True, text=True, check=False, env=env, timeout=120
    )
    return proc, calls.read_text(encoding="utf-8").splitlines()


def test_gate_returns_instead_of_following_a_dead_task(tmp_path: Path) -> None:
    """`alloc logs -f` does not exit when the task dies; the gate must not wait on it.

    The stub sleeps an hour on `-f`, exactly as the real CLI does. If the script ever
    goes back to foregrounding that stream, this test stops returning rather than fails
    politely — which is the honest shape of the bug it guards.
    """
    proc, _ = _run_gate(tmp_path, state="dead", exit_code=0)

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "durability rows passed" in proc.stdout


def test_previous_run_is_purged_before_submitting(tmp_path: Path) -> None:
    """A completed batch job is not re-run by `job run`, so the gate replayed its verdict.

    Without the purge the script reported a PREVIOUS run's exit code as this run's — a
    merge gate answering green for a tree it never tested.
    """
    _, calls = _run_gate(tmp_path)

    purge = next(i for i, c in enumerate(calls) if c.startswith("job stop -purge"))
    submit = next(i for i, c in enumerate(calls) if c.startswith("job run"))
    assert purge < submit, f"purge must precede submit, got: {calls}"


def test_failing_rows_are_reported_red(tmp_path: Path) -> None:
    """The gate has to be able to fail, or it is decoration."""
    proc, _ = _run_gate(tmp_path, state="dead", exit_code=1)

    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "durability rows failed" in proc.stderr


def test_timeout_is_not_reported_as_a_failure(tmp_path: Path) -> None:
    """Running out of patience is not a verdict on the rows.

    A cold run measured at 166s against a 120s bound, so the gate declared 31 passing
    rows red and sent the reader to debug passing tests. Timeout now exits 2, distinct
    from the rows' own 1, and says so.
    """
    proc, _ = _run_gate(tmp_path, state="running", wait_secs=4)

    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "no verdict" in proc.stderr
    assert "did not finish" in proc.stderr
    assert "rows failed" not in proc.stderr
