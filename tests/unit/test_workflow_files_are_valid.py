# SPDX-License-Identifier: Apache-2.0
"""Every workflow file is one GitHub will actually accept.

**A workflow GitHub refuses is a gate that does not exist**, and it fails in the one way
nobody investigates: the run appears in the checks list with a red cross, zero jobs, and the
message "This run likely failed because of a workflow file issue". Nothing names the file,
nothing names the line, and a red cross on a CI file reads as somebody else's problem.

Found when `.github/workflows/enclave.yml` declared `workflow_dispatch:` twice under `on:` —
two comments, each correct, each followed by the same key. GitHub rejects a duplicate mapping
key outright, so **every push after that change produced a jobless failure, on `main` as well
as on branches**, and the enclave lane could not be dispatched at all. Its own comments said
it remained available on demand. It did not.

**Why the obvious check does not catch it.** `yaml.safe_load` accepts duplicate keys — last
one wins — and returns a perfectly valid document, so a parse check reports the file as fine.
The duplicate has to be looked for on purpose, which is what `_no_duplicates` does.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[2] / ".github/workflows"


#: A loader that refuses what `SafeLoader` silently accepts.
#:
#: Built with `type()` rather than a `class` statement because PyYAML ships no stubs, so
#: `SafeLoader` is `Any` to mypy and subclassing it is an error. This is the same untyped
#: boundary the `pg8000` and `anthropic` overrides describe, kept to one line.
_DuplicateKeyLoader: Any = type("_DuplicateKeyLoader", (yaml.SafeLoader,), {})


def _no_duplicates(loader: Any, node: Any, deep: bool = False) -> dict[Any, Any]:
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None,
                None,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        seen.add(key)
    mapping: dict[Any, Any] = yaml.SafeLoader.construct_mapping(loader, node, deep)
    return mapping


_DuplicateKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _no_duplicates,
)


def _workflow_files() -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))


def test_there_are_workflow_files_to_check() -> None:
    """The check must not pass by finding nothing.

    A glob that stops matching — a renamed directory, a moved workflow — would make every
    assertion below vacuously true, which is the failure mode this repository has paid for
    in three other checks.
    """
    assert _workflow_files(), f"no workflow files found under {WORKFLOWS}"


@pytest.mark.parametrize("path", _workflow_files(), ids=lambda p: p.name)
def test_workflow_has_no_duplicate_keys(path: Path) -> None:
    """GitHub rejects a duplicate mapping key; `yaml.safe_load` does not."""
    try:
        yaml.load(path.read_text(encoding="utf-8"), Loader=_DuplicateKeyLoader)
    except yaml.constructor.ConstructorError as exc:
        pytest.fail(
            f"{path.name} has a duplicate key, which GitHub rejects outright — the workflow "
            f"will produce runs with zero jobs and a red cross naming no file: {exc}"
        )


@pytest.mark.parametrize("path", _workflow_files(), ids=lambda p: p.name)
def test_workflow_declares_a_trigger_and_a_job(path: Path) -> None:
    """A workflow with no `on:` never runs; one with no `jobs:` runs and does nothing.

    Both are gates that exist on disk and nowhere else. ``on`` parses as the boolean ``True``
    in YAML 1.1 — that is not a quirk to work around, it is why this check reads the parsed
    document rather than grepping for the word.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(document, dict), f"{path.name} is not a mapping"

    triggers = document.get("on", document.get(True))
    assert triggers, f"{path.name} declares no trigger, so it can never run"
    assert document.get("jobs"), f"{path.name} declares no jobs, so running it does nothing"


def test_the_duplicate_key_detector_actually_fires() -> None:
    """The check can fail — asserted, not assumed.

    `AGENTS.md`: every assertion must be able to fail, and a gate-tagged test that cannot is
    a governance hole with a green checkmark. This is the violating input the detector exists
    for, and `yaml.safe_load` accepts it — which is the whole reason the detector exists.
    """
    violating = "on:\n  workflow_dispatch:\n  workflow_dispatch:\njobs:\n  a:\n    runs-on: x\n"

    assert yaml.safe_load(violating), "safe_load rejected it, so the detector is redundant"

    with pytest.raises(yaml.constructor.ConstructorError, match="duplicate key"):
        yaml.load(violating, Loader=_DuplicateKeyLoader)
