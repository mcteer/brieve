# SPDX-License-Identifier: Apache-2.0
"""The enclave lane may only be skipped for changes nothing could possibly assert on.

`infra/bin/paths-the-tests-read` decides. It is worth testing precisely because its wrong
answer is invisible: a spurious `skip` does not fail anything, it lets a change reach `main`
without the lane that would have caught it.

**The `skip` cases cannot be tested through the real repository, and finding out why was the
point.** The script answers "is this path read by tests?" by searching test sources — and this
file is a test source. A `skip` assertion naming any path, real or invented, embeds that path
here, makes it referenced, and flips the answer to `run`. The first version of this module used
a deliberately non-existent path to dodge that and failed anyway, because *non-existent* was
never the property that mattered; *unmentioned* was.

That is the script being right. It cannot distinguish a path a test opens from one a test names,
and it treats both as read — conservative in the direction that costs a lane run rather than a
missed one. So `skip` is exercised against a controlled source set, and everything else runs the
real script end to end.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra/bin/paths-the-tests-read"


def _module() -> ModuleType:
    """Import a script that has no `.py` extension."""
    loader = SourceFileLoader("paths_the_tests_read", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def verdict(*paths: str) -> str:
    """The real script, over the real repository."""
    result = subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, str(SCRIPT), *paths],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


# ------------------------------------------------------------------ it may skip


def test_documentation_no_test_reads_may_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    """The case the whole thing exists for: a planning artifact nothing asserts on."""
    module = _module()
    monkeypatch.setattr(module, "_test_sources", lambda: ["a source mentioning nothing relevant"])
    assert module.decide(["specs/some-feature/spec.md"])[0] == "skip"


def test_several_such_paths_may_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "_test_sources", lambda: ["unrelated"])
    assert module.decide(["specs/some-feature/spec.md", "specs/some-feature/plan.md"])[0] == "skip"


def test_a_named_path_is_read_even_when_only_mentioned(monkeypatch: pytest.MonkeyPatch) -> None:
    """The conservative rule, asserted so nobody 'improves' it into intent-parsing."""
    module = _module()
    monkeypatch.setattr(module, "_test_sources", lambda: ['NOTE = "specs/some-feature/spec.md"'])
    assert module.decide(["specs/some-feature/spec.md"])[0] == "run"


def test_an_empty_source_set_must_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """If nothing can be read, nothing can be established."""
    module = _module()
    monkeypatch.setattr(module, "_test_sources", lambda: [])
    assert module.decide(["specs/some-feature/spec.md"])[0] == "run"


# ------------------------------------------------------------------ it must not skip


def test_a_contract_a_row_asserts_on_must_run() -> None:
    """**The case a `paths-ignore` allowlist gets wrong**, which is why this is derived.

    018's row asserts that this contract still records the limits its rows depend on. Editing
    it is a documentation change that turns an enclave row red — exactly what the lane is for.
    """
    assert verdict("specs/018-registry-isolation/contracts/conformance.md") == "run"


def test_the_parity_snapshot_must_run() -> None:
    assert verdict("specs/008-northbound-api/contracts/operations.snapshot.json") == "run"


@pytest.mark.parametrize(
    "path",
    ["src/core/identity/kind.py", "tests/unit/test_no_live_dependencies.py", "Makefile"],
)
def test_code_must_run(path: str) -> None:
    assert verdict(path) == "run"


def test_a_mixed_change_must_run() -> None:
    """One code file among documentation is still a code change."""
    assert verdict("specs/some-feature/spec.md", "src/core/identity/kind.py") == "run"


# ------------------------------------------------------------------ it fails closed


def test_no_arguments_must_run() -> None:
    assert verdict() == "run"


def test_an_unknown_root_must_run() -> None:
    assert verdict("some/unknown/place.txt") == "run"


def test_paths_crammed_into_one_argument_must_run() -> None:
    """This guard caught a real fail-open while the script was being written.

    A test harness in zsh passed several paths as one argument — zsh does not word-split
    unquoted parameter expansions the way bash does. The script matched the resulting
    space-containing string against nothing and answered `skip` for a changed set that
    included `src/core/identity/kind.py`. Wrong in the only direction that matters.
    """
    assert verdict("specs/some-feature/spec.md src/core/identity/kind.py") == "run"
