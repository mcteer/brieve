# SPDX-License-Identifier: Apache-2.0
"""US1 — durability across a genuine process boundary (T024a, quickstart Scenario A2).

Every other disruption in this suite is simulated in-process, which is deterministic,
fast, and what FR-016 requires. But an entirely in-process suite proves the code can
reload its own state, not that the state survived anything. One scenario therefore
writes checkpoints in one interpreter and reads them in another.

This does not violate FR-016: restarting a *test process* is not terminating real
infrastructure. Nothing is killed; a second interpreter simply picks up what the first
one persisted.
"""

from __future__ import annotations

import json
import pathlib
import socket
import subprocess
import sys
import uuid
from typing import Any

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

WRITER = """
import json, sys
sys.path.insert(0, "src")
sys.path.insert(0, ".")
from tests.conformance.durability.conftest import DevVaultCredentials
from core.durability.postgres import PostgresDurabilityProvider
from core.durability.types import CheckpointBlob

run_id = sys.argv[1]
store = PostgresDurabilityProvider(credentials=DevVaultCredentials())
store.migrate()
store.save(CheckpointBlob(
    blob_id=run_id, payload={"progress": "written-by-process-one"},
    correlation_id="corr-cross", grant_id="grant-1", step_index=7, written_by="alloc-1",
))
print(json.dumps({"ok": True}))
"""

READER = """
import json, sys
sys.path.insert(0, "src")
sys.path.insert(0, ".")
from tests.conformance.durability.conftest import DevVaultCredentials
from core.durability.postgres import PostgresDurabilityProvider

run_id = sys.argv[1]
store = PostgresDurabilityProvider(credentials=DevVaultCredentials())
blob = store.load(run_id)
print(json.dumps({
    "found": blob is not None,
    "step_index": blob.step_index if blob else None,
    "progress": blob.payload.get("progress") if blob else None,
    "correlation_id": blob.correlation_id if blob else None,
}))
"""


def _enclave_up() -> bool:
    for port in (5432, 8200):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                pass
        except OSError:
            return False
    return True


def _run(script: str, run_id: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-c", script, run_id],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"subprocess failed:\n{result.stderr}"
    parsed: dict[str, Any] = json.loads(result.stdout.strip().splitlines()[-1])
    return parsed


@pytest.mark.enclave
def test_checkpoint_written_in_one_process_resumes_in_another() -> None:
    if not _enclave_up():
        pytest.fail(
            "cross-process durability needs the enclave — run `make dev-up`. Skipping "
            "would report a guarantee nobody tested."
        )

    run_id = f"cross-process-{uuid.uuid4().hex[:12]}"

    assert _run(WRITER, run_id)["ok"]
    # The writing interpreter is gone. Nothing is shared but the database.
    read = _run(READER, run_id)

    assert read["found"], "the checkpoint did not survive the process boundary"
    assert read["step_index"] == 7
    assert read["progress"] == "written-by-process-one"
    assert read["correlation_id"] == "corr-cross", "the join key survived too"
