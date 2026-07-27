# SPDX-License-Identifier: Apache-2.0
"""Regression tests for two `enclave-up` bring-up bugs.

Both bugs were shell-level and silent: the script reported a diagnosis that named
neither cause. Neither is reachable from a unit test by running the whole script —
it provisions an enclave — so each test EXTRACTS THE REAL BLOCK from the shipped file
and executes it against stubs. Extraction rather than a transcribed copy is the point:
a copy would keep passing after someone reintroduces the bug upstream of it.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ENCLAVE_UP = REPO_ROOT / "infra" / "bin" / "enclave-up"


def _extract(pattern: str) -> str:
    source = ENCLAVE_UP.read_text(encoding="utf-8")
    match = re.search(pattern, source, re.MULTILINE | re.DOTALL)
    assert match is not None, f"block not found in {ENCLAVE_UP} — did it move? /{pattern}/"
    return match.group(0)


def _run(script: str, overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    # The scheme block honours a caller's VAULT_ADDR/VAULT_CACERT by design
    # (`${VAULT_ADDR:-…}`), so a developer who has sourced .env exports both and the
    # detection under test is bypassed. Strip them unless a test is asserting on the
    # override itself — otherwise this passes or fails according to the shell it was
    # launched from, which is worse than not testing it.
    env = {k: v for k, v in os.environ.items() if k not in ("VAULT_ADDR", "VAULT_CACERT")}
    env.update(overrides or {})
    # pipefail is what made bug 1 possible; running without it would test nothing.
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def _init_detection(stub: str) -> str:
    """Run the real initialised-detection block against a stubbed `vault`."""
    block = _extract(r"^status_json=.*?^initialized=.*?$")
    proc = _run(f"{stub}\n{block}\nprintf '%s' \"$initialized\"")
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def test_uninitialised_store_is_detected_despite_nonzero_exit() -> None:
    """`vault status` exits nonzero while printing valid JSON — the pipefail trap.

    The old one-liner ran BOTH python's `False` and its `|| echo False` fallback and
    produced "False\\nFalse", which matched neither branch. A true first run therefore
    took the "already initialised" path and died unsealing with an empty key.
    """
    stub = 'vault() { echo \'{"initialized":false,"sealed":true}\'; return 2; }'
    assert _init_detection(stub) == "False"


def test_initialised_store_is_not_reinitialised() -> None:
    """The other direction, and the expensive one.

    Misreading an initialised store as fresh would re-run `operator init` and discard
    the raft store, invalidating every credential derived from it.
    """
    stub = 'vault() { echo \'{"initialized":true,"sealed":true}\'; return 2; }'
    assert _init_detection(stub) == "True"


def test_unparseable_status_falls_back_to_uninitialised() -> None:
    """No JSON at all (store unreachable) must still yield a single clean value."""
    stub = "vault() { echo 'not json'; return 1; }"
    assert _init_detection(stub) == "False"


def _scheme_for(
    env_dir: Path,
    ca_file_exists: bool,
    tmp_path: Path,
    overrides: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Run the real scheme-detection block against a fixture environment root."""
    block = _extract(r"^CA_FILE=.*?^fi$")
    repo = tmp_path / "repo"
    (repo / ".enclave").mkdir(parents=True)
    if ca_file_exists:
        (repo / ".enclave" / "ca.pem").write_text("fixture\n", encoding="utf-8")
    preamble = f"REPO={repo!s}\nENV_DIR={env_dir!s}\n"
    proc = _run(
        f'{preamble}{block}\nprintf \'%s|%s\' "$VAULT_ADDR" "${{VAULT_CACERT:-}}"',
        overrides=overrides,
    )
    assert proc.returncode == 0, proc.stderr
    addr, _, cacert = proc.stdout.partition("|")
    return addr, cacert


def test_probe_uses_https_once_tls_material_exists(tmp_path: Path) -> None:
    """An already-bootstrapped listener is HTTPS; probing it over http fails.

    tls.auto.tfvars is auto-loaded, so Terraform brings the listener up on TLS. The
    old hardcoded http default made the probe fail (curl exit 22) against a store that
    was working perfectly, and the script reported "trust store is not answering" —
    which names neither TLS nor the scheme. This is the container-lost-but-TLS-material-
    survived case, i.e. ordinary recovery.
    """
    env_dir = tmp_path / "dev"
    env_dir.mkdir()
    (env_dir / "tls.auto.tfvars").write_text("enable_tls = true\n", encoding="utf-8")

    addr, cacert = _scheme_for(env_dir, ca_file_exists=True, tmp_path=tmp_path)

    assert addr.startswith("https://"), addr
    assert cacert.endswith("ca.pem"), cacert


def test_probe_uses_http_before_tls_is_bootstrapped(tmp_path: Path) -> None:
    """First run: no certificate has been issued yet, so the listener is plaintext.

    Defaulting to https here would break the bootstrap in the opposite direction.
    """
    env_dir = tmp_path / "dev"
    env_dir.mkdir()

    addr, cacert = _scheme_for(env_dir, ca_file_exists=False, tmp_path=tmp_path)

    assert addr.startswith("http://"), addr
    assert cacert == "", cacert


def test_half_present_tls_material_does_not_select_https(tmp_path: Path) -> None:
    """tfvars without a CA file cannot be trusted: https would have nothing to verify."""
    env_dir = tmp_path / "dev"
    env_dir.mkdir()
    (env_dir / "tls.auto.tfvars").write_text("enable_tls = true\n", encoding="utf-8")

    addr, _ = _scheme_for(env_dir, ca_file_exists=False, tmp_path=tmp_path)

    assert addr.startswith("http://"), addr


def test_caller_supplied_address_still_wins(tmp_path: Path) -> None:
    """Detection supplies a DEFAULT, not a policy.

    Worth pinning: a developer who has sourced .env exports VAULT_ADDR, and pointing the
    script at a non-default listener has to keep working. This is also what makes the
    other tests in this file need a scrubbed environment to mean anything.
    """
    env_dir = tmp_path / "dev"
    env_dir.mkdir()
    (env_dir / "tls.auto.tfvars").write_text("enable_tls = true\n", encoding="utf-8")

    addr, _ = _scheme_for(
        env_dir,
        ca_file_exists=True,
        tmp_path=tmp_path,
        overrides={"VAULT_ADDR": "http://10.0.0.1:8200"},
    )

    assert addr == "http://10.0.0.1:8200", addr
