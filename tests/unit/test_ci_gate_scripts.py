# SPDX-License-Identifier: Apache-2.0
"""CI gate scripts must fail on violating input (enforcement code)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_check_specs_fails_on_needs_clarification(tmp_path: Path) -> None:
    feat = tmp_path / "specs" / "999-gate-fixture"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text(
        "# Fixture\n\n[NEEDS CLARIFICATION: unresolved for gate test]\n",
        encoding="utf-8",
    )
    script = REPO_ROOT / "scripts" / "check-specs.sh"
    proc = subprocess.run(
        ["bash", str(script), str(feat / "spec.md")],
        cwd=REPO_ROOT,
        env={**os.environ, "CHECK_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "unresolved clarification" in proc.stderr or "NEEDS CLARIFICATION" in proc.stdout


def test_check_specs_fails_on_missing_spec_md(tmp_path: Path) -> None:
    feat = tmp_path / "specs" / "998-missing-spec"
    feat.mkdir(parents=True)
    (feat / "notes.md").write_text("no spec.md here\n", encoding="utf-8")
    script = REPO_ROOT / "scripts" / "check-specs.sh"
    proc = subprocess.run(
        ["bash", str(script), str(feat / "notes.md")],
        cwd=REPO_ROOT,
        env={**os.environ, "CHECK_ROOT": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
    assert "missing" in proc.stderr


def test_check_licenses_fails_on_disallowed_allowlist(tmp_path: Path) -> None:
    """Empty/impossible allowlist must make pip-licenses --allow-only fail."""
    allow = tmp_path / "allowlist.txt"
    allow.write_text("# fixture — no real license matches\nNotARealLicenseXYZ\n", encoding="utf-8")
    script = REPO_ROOT / "scripts" / "check-licenses.sh"
    proc = subprocess.run(
        ["bash", str(script)],
        cwd=REPO_ROOT,
        env={**os.environ, "LICENSE_ALLOWLIST": str(allow)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0, proc.stdout + proc.stderr
