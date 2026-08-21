# SPDX-License-Identifier: Apache-2.0
"""Two-gate scoring for a Terraform Write artefact (SC-006 / Write GEPA).

Gate one is `terraform validate` on the merged tree. Gate two is the property detector
on the authored files. The live authoring lane reports the two numbers separately.
Write GEPA needs a scalar: 1.0 both, 0.5 exactly one, 0.0 neither — plus feedback that
names which gate failed.

**Empty-when-needed is zero, not a tooling pass.** An empty artefact against a subject
that does not already implement the request is the failure mode the Write card's
"already implemented / no extra work" line over-fired. Scoring it as 0.5 (tooling pass,
reference fail) would teach GEPA to author nothing. The live SC-006 lane still reports
that shape as valid-but-wrong; the optimizer must not be paid for it.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from core.evals.authoring_corpus import GoldenTask, load_corpus
from core.evals.authoring_scoring import ToolingResult, score_reference
from tests.evals_live.authoring_properties import detect
from tests.evals_live.authoring_subjects import subject_for

ROOT = Path(__file__).resolve().parents[2]

#: Response format for the eval-lane author, not production `author_file`. Kept out of
#: `AGENTS.md` so GEPA cannot promote FILE-block protocol into a served Write cell.
FILE_PROTOCOL = """Respond with ONE file per block, in exactly this format and nothing else:

--- FILE: path/to/file.tf
<contents>
--- END

Respond `--- NO CHANGE` ONLY when the repository ALREADY contains a complete implementation of
what the task asks. Read the given files before deciding: if what the task asks for is absent,
you must author it. An empty answer to a task that is not yet done is a wrong answer.

Author complete files, not fragments: a file you emit REPLACES the one at that path.

Do not explain. Do not add commentary outside the blocks."""


@dataclass(frozen=True)
class WriteTrainItem:
    """One golden-task example for Write GEPA. ``task_text`` is the Predict input."""

    task_text: str
    task_name: str
    expects_no_artifact: bool


@dataclass(frozen=True)
class WriteGateScore:
    """Scalar plus the two gates, so feedback can name which one failed."""

    score: float
    tooling_passed: bool
    reference_passed: bool
    feedback: str


def parse_authored(response: str) -> dict[str, str]:
    """Files the model authored. ``--- NO CHANGE`` yields none, which is a valid answer."""
    if "--- NO CHANGE" in response:
        return {}
    files: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in response.splitlines():
        if line.startswith("--- FILE:"):
            current = line.split(":", 1)[1].strip()
            body = []
        elif line.startswith("--- END"):
            if current:
                files[current] = "\n".join(body) + "\n"
            current = None
        elif current is not None:
            body.append(line)
    if current and body:
        files[current] = "\n".join(body) + "\n"
    return files


def first_error(blob: str) -> str:
    """The first line that names the problem, stripped of terminal colour."""
    plain = re.sub(r"\x1b\[[0-9;]*m", "", blob)
    for line in plain.splitlines():
        if "Error:" in line:
            return line.split("Error:", 1)[1].strip()[:160]
    return plain.strip()[:160]


def terraform_validates(contents: dict[str, str]) -> ToolingResult:
    """Gate one, by the product's own tooling. Never degrades to a formatter."""
    if not contents:
        return ToolingResult(ran=True, passed=True, detail="no artefact")
    with tempfile.TemporaryDirectory() as raw:
        directory = Path(raw)
        for name, body in contents.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
        init = subprocess.run(
            ["terraform", "-chdir=" + str(directory), "init", "-backend=false", "-input=false"],
            capture_output=True,
            text=True,
            check=False,
        )
        if init.returncode != 0:
            blob = f"{init.stderr}\n{init.stdout}"
            unreachable = any(
                signal in blob
                for signal in (
                    "Failed to query available provider packages",
                    "could not connect",
                    "no available releases",
                    "Failed to install provider",
                    "network is unreachable",
                )
            )
            if unreachable:
                return ToolingResult(
                    ran=False,
                    passed=False,
                    detail=f"provider registry unreachable: {init.stderr.strip()[:160]}",
                )
            return ToolingResult(
                ran=True,
                passed=False,
                detail=f"configuration refused by init: {first_error(blob)}",
            )
        validated = subprocess.run(
            ["terraform", "-chdir=" + str(directory), "validate"],
            capture_output=True,
            text=True,
            check=False,
        )
        return ToolingResult(
            ran=True,
            passed=validated.returncode == 0,
            detail=validated.stderr.strip()[:200],
        )


def render_subject(files: dict[str, str]) -> str:
    if not files:
        return "(the repository is empty)"
    return "\n\n".join(f"--- FILE: {name}\n{body}--- END" for name, body in files.items())


def iter_write_train_items(*, repo_root: Path = ROOT) -> tuple[WriteTrainItem, ...]:
    """All five golden tasks, each with its subject. No `prompts[:1]` slice."""
    corpus = load_corpus(repo_root / "evals" / "authoring" / "corpus.toml")
    items: list[WriteTrainItem] = []
    for task in corpus.golden:
        subject = subject_for(task.name)
        prompt = (
            f"{FILE_PROTOCOL}\n\nTASK: {task.prompt}\n\n"
            f"CURRENT REPOSITORY CONTENTS:\n{render_subject(subject)}"
        )
        items.append(
            WriteTrainItem(
                task_text=prompt,
                task_name=task.name,
                expects_no_artifact=task.expects_no_artifact,
            )
        )
    return tuple(items)


def _task_by_name(name: str, *, repo_root: Path = ROOT) -> GoldenTask:
    corpus = load_corpus(repo_root / "evals" / "authoring" / "corpus.toml")
    for task in corpus.golden:
        if task.name == name:
            return task
    raise KeyError(f"no golden task named {name!r}")


def score_write_artefact(
    *,
    task: GoldenTask,
    authored: dict[str, str],
    merged: dict[str, str],
    tooling: ToolingResult | None = None,
) -> WriteGateScore:
    """Score one Write artefact. ``tooling`` is injected in hermetic tests."""
    notes: list[str] = []
    if not authored and not task.expects_no_artifact:
        want = sorted(task.reference.properties) if task.reference is not None else []
        notes.append(
            "authored nothing; the subject does not already implement this request. "
            "Author the Terraform. Empty is correct only for an already-complete integration."
        )
        if want:
            notes.append("still missing: " + ", ".join(want))
        return WriteGateScore(
            score=0.0,
            tooling_passed=False,
            reference_passed=False,
            feedback="; ".join(notes),
        )
    if authored and task.expects_no_artifact:
        notes.append(
            "authored a second copy of an existing integration; the correct artefact is empty"
        )
        reference_passed = False
        if tooling is None:
            tooling = terraform_validates(merged)
        tooling_passed = bool(tooling.ran and tooling.passed)
        score = 0.5 if tooling_passed else 0.0
        if not tooling.ran:
            notes.append(f"tooling did not run: {tooling.detail}")
        elif not tooling.passed:
            notes.append(f"terraform validate failed: {tooling.detail}")
        return WriteGateScore(
            score=score,
            tooling_passed=tooling_passed,
            reference_passed=reference_passed,
            feedback="; ".join(notes),
        )

    if tooling is None:
        tooling = terraform_validates(merged)
    if not tooling.ran:
        return WriteGateScore(
            score=0.0,
            tooling_passed=False,
            reference_passed=False,
            feedback=f"tooling did not run: {tooling.detail}",
        )
    found = detect(authored)
    reference_passed = score_reference(task, found)
    tooling_passed = tooling.passed
    score = (0.5 if tooling_passed else 0.0) + (0.5 if reference_passed else 0.0)
    if not tooling_passed:
        notes.append(f"terraform validate failed: {tooling.detail}")
    if not reference_passed:
        if task.expects_no_artifact:
            notes.append("expected no artefact")
        elif task.reference is not None:
            missing = sorted(set(task.reference.properties) - found)
            notes.append("still missing: " + ", ".join(missing) if missing else "reference miss")
    if score == 1.0:
        notes.append("both gates passed")
    return WriteGateScore(
        score=score,
        tooling_passed=tooling_passed,
        reference_passed=reference_passed,
        feedback="; ".join(notes),
    )


def score_write_prediction(
    *,
    task_name: str,
    artefact_text: str,
    tooling: ToolingResult | None = None,
    repo_root: Path = ROOT,
) -> WriteGateScore:
    """Parse a model response and score it against the named golden task."""
    task = _task_by_name(task_name, repo_root=repo_root)
    authored = parse_authored(artefact_text)
    subject = subject_for(task.name)
    merged = {**subject, **authored}
    return score_write_artefact(task=task, authored=authored, merged=merged, tooling=tooling)


__all__ = [
    "FILE_PROTOCOL",
    "WriteGateScore",
    "WriteTrainItem",
    "first_error",
    "iter_write_train_items",
    "parse_authored",
    "score_write_artefact",
    "score_write_prediction",
    "terraform_validates",
]
