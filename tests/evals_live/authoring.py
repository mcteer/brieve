# SPDX-License-Identifier: Apache-2.0
"""The live `write` qualification: a real model authors, and both gates score it (041, T019).

ADR-0063 says a mechanical scorer over a human-authored reference may qualify a cell, and 038
built every piece of the scoring — `score_corpus`, `score_reference`, `score_deny_case`, the
corpus with its `author` on every reference. **What did not exist was a lane that produced
artefacts to score.** `properties_of` is caller-supplied and its only implementations were
literal maps inside rows, so the machinery had never been pointed at a model.

**Two gates, never one number.** Gate one is `terraform validate` — malformed. Gate two is the
property detector against the reference — *subtly wrong*. Collapsing them would report a module
wiring a static credential where dynamic secrets were asked for as a partial pass, which is
exactly the failure ADR-0038 warns about.

**The subjects live beside this file** because a task like `existing_integration_is_not_duplicated`
is meaningless without one: the correct answer is an empty artefact, and only a subject that
already has the integration can make that the correct answer.

Run: `make evals-authoring-live`. Prints per-task detail, then the two numbers.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.anthropic_scorer import client_and_model  # noqa: E402
from core.authoring.artifact import AuthoredArtifact  # noqa: E402
from core.authoring.tool import FileAuthor  # noqa: E402
from core.authoring.workspace import Trees  # noqa: E402
from core.evals.authoring_corpus import GoldenTask, load_corpus  # noqa: E402
from core.evals.authoring_scoring import ToolingResult, score_corpus  # noqa: E402
from core.evals.scoring import LIVE_MODEL  # noqa: E402
from tests.evals_live.authoring_properties import detect  # noqa: E402
from tests.evals_live.authoring_subjects import subject_for  # noqa: E402
from tests.evals_live.write_gates import parse_authored, terraform_validates  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "evals" / "authoring" / "corpus.toml"

_SYSTEM = """You are an infrastructure engineer writing Terraform for a customer's repository.

You will be given a task and the current contents of the relevant files. Author the Terraform
that completes the task.

Respond with ONE file per block, in exactly this format and nothing else:

--- FILE: path/to/file.tf
<contents>
--- END

Respond `--- NO CHANGE` ONLY when the repository ALREADY contains a complete implementation of
what the task asks. Read the given files before deciding: if what the task asks for is absent,
you must author it. An empty answer to a task that is not yet done is a wrong answer.

Author complete files, not fragments: a file you emit REPLACES the one at that path.

Do not explain. Do not add commentary outside the blocks."""


def _system_prompt(instruction: str = "") -> str:
    """Generic write steer, optionally followed by a pinned pack Write card."""
    extra = instruction.strip()
    if not extra:
        return _SYSTEM
    return (
        _SYSTEM + "\n\nThe following is the product Write instruction for this Build. "
        "Stay in Write. Do not fetch the public web.\n\n" + extra
    )


def _ask(prompt: str, *, api_key: str, instruction: str = "") -> tuple[str, str]:
    """One model call, through the ADAPTER that owns the vendor binding.

    Not `import anthropic` here: `tests/unit/test_no_live_dependencies.py` forbids a test
    module reaching a vendor SDK directly, with no allowlist, and it is right — the vendor
    binding belongs in `adapters/` (Principle I), which is also where the credential check,
    the extra check and the model-id derivation already live, each of which has been wrong
    at least once.
    """
    client, api_model = client_and_model(LIVE_MODEL, api_key=api_key)
    message = client.messages.create(  # type: ignore[attr-defined]
        model=api_model,
        # 8192 matches Write GEPA (`WRITE_TASK_MAX_TOKENS`). 4096 truncated complete
        # `variables.tf` mid-block; `terraform init` then refused the merged tree while
        # the property detector still passed — the anonymous 4/5 tooling miss.
        max_tokens=8192,
        system=_system_prompt(instruction),
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    stop = str(getattr(message, "stop_reason", "") or "")
    return text, stop


def _author(
    task: GoldenTask, *, api_key: str, workdir: Path, instruction: str = ""
) -> tuple[AuthoredArtifact, dict[str, str], dict[str, str], str]:
    """Drive the model, then put its answer through the REAL `author_file` handler.

    Through the handler rather than into a dict: the qualification should score what the
    platform would actually have written, containment and all, not what a test harness kept.
    """
    subject_files = subject_for(task.name)
    rendered = (
        "\n\n".join(f"--- FILE: {name}\n{body}--- END" for name, body in subject_files.items())
        or "(the repository is empty)"
    )
    prompt = f"TASK: {task.prompt}\n\nCURRENT REPOSITORY CONTENTS:\n{rendered}"

    response, stop_reason = _ask(prompt, api_key=api_key, instruction=instruction)
    authored = parse_authored(response)

    subject = workdir / task.name / "subject"
    workspace = workdir / task.name / "workspace"
    subject.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)
    for name, body in subject_files.items():
        path = subject / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    artifact = AuthoredArtifact()
    author = FileAuthor(Trees(subject=subject.resolve(), workspace=workspace.resolve()), artifact)
    for name, body in authored.items():
        author({"path": name, "content": body})
    # The MERGED tree is what gate one must validate: an artefact lands INTO a repository, so
    # validity is a property of the result, not of the fragment. Validating the fragment alone
    # fails on every file that relies on a `required_providers` block it did not rewrite —
    # which is a defect in the harness, not in the answer.
    merged = {**subject_files, **author.contents}
    return artifact, author.contents, merged, stop_reason


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Live write qualification (two gates).")
    parser.add_argument(
        "--instruction-file",
        default=os.environ.get("INSTRUCTION_FILE", ""),
        help="Optional pack Write AGENTS.md to prepend after the generic steer",
    )
    parser.add_argument(
        "--label",
        default=os.environ.get("EVAL_LABEL", "generic"),
        help="Label printed in the summary (generic vs write-card)",
    )
    args = parser.parse_args()
    instruction = ""
    if args.instruction_file:
        path = Path(args.instruction_file)
        instruction = path.read_text(encoding="utf-8")
        if not instruction.strip():
            print(f"empty instruction file: {path}", file=sys.stderr)
            return 2

    key = os.environ.get("EVAL_PROVIDER_API_KEY", "").strip()
    if not key:
        print("no EVAL_PROVIDER_API_KEY; this lane cannot run", file=sys.stderr)
        return 2

    corpus = load_corpus(CORPUS)
    print(f"== live `write` qualification — {LIVE_MODEL} — {args.label}")
    if args.instruction_file:
        print(f"   instruction: {args.instruction_file}")
    else:
        print("   instruction: generic steer (no pack AGENTS.md)")
    print(f"   corpus: {len(corpus.golden)} golden tasks, {len(corpus.deny)} deny cases\n")

    artefacts: dict[str, tuple[AuthoredArtifact, dict[str, str]]] = {}
    tooling_by_task: dict[str, ToolingResult] = {}
    dump_root = ROOT / "evals" / "prompt-tune" / "sc006-dump" / args.label
    dump_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as raw:
        workdir = Path(raw)
        for task in corpus.golden:
            artifact, contents, merged, stop_reason = _author(
                task, api_key=key, workdir=workdir, instruction=instruction
            )
            found = detect(contents)
            tooling = terraform_validates(merged)
            print(f"--- {task.name}")
            print(f"    stop       : {stop_reason or '(none)'}")
            print(f"    files      : {sorted(contents) or '(none)'}")
            print(f"    properties : {sorted(found) or '(none)'}")
            if task.reference is not None:
                want = set(task.reference.properties)
                print(f"    expected   : {sorted(want)}")
                print(f"    missing    : {sorted(want - found) or '(none)'}")
            else:
                print("    expected   : no artefact")
            status = "pass" if tooling.passed else "FAIL"
            print(f"    tooling    : {status}" + (f" — {tooling.detail}" if tooling.detail else ""))
            artefacts[task.name] = (artifact, contents)
            tooling_by_task[task.name] = tooling
            task_dump = dump_root / task.name
            task_dump.mkdir(parents=True, exist_ok=True)
            for name, body in merged.items():
                target = task_dump / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(body)

        report = score_corpus(
            corpus,
            tooling=lambda task, _a, _c: tooling_by_task[task.name],
            artefacts=artefacts,
            properties_of=lambda _t, _a, contents: detect(contents),
        )

    print("\n== gates, two numbers and never one")
    print(f"   label                : {args.label}")
    print(f"   product tooling      : {report.tooling_passed}/{report.tooling_total}")
    print(f"   reference comparison : {report.reference_passed}/{report.reference_total}")
    if report.tooling_failed:
        print(f"   TOOLING FAILED       : {list(report.tooling_failed)}")
    if report.valid_but_wrong:
        print(f"   VALID BUT WRONG      : {list(report.valid_but_wrong)}")
    print(f"   dump                 : {dump_root}")
    print(f"\n   both gates passed    : {report.both_passed}")
    return 0 if report.both_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
