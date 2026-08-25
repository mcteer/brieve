# SPDX-License-Identifier: Apache-2.0
"""A task that declares an entrypoint and no command runs nothing (041, FR-014).

**This is the layer nobody checked.** `infra/jobs/authoring-tier.nomad.hcl` was written with
care — mounts, per-task identities, the prestart lifecycle, task scope, and a paragraph of
reasoning on each — and both of its tasks declared `entrypoint = ["/bin/sh", "-c"]` with no
`args`. A shell with no command exits immediately and successfully. The tier could not execute,
and every review of that file was reading the parts that were right.

The check is general because the defect is: any task whose entrypoint takes a command must
supply one. `agent-run.nomad.hcl` always did, which is why the gap looked like an absence
rather than a difference.
"""

from __future__ import annotations

import pathlib
import re

import pytest

JOBS = pathlib.Path(__file__).resolve().parents[2] / "infra" / "jobs"

#: Entrypoints that consume a command. `/bin/sh -c` with nothing after it is the whole defect.
_COMMAND_TAKING = re.compile(r'entrypoint\s*=\s*\[[^\]]*"-c"[^\]]*\]')

#: Tasks known to declare a command-taking entrypoint and no command, with the record that
#: owns each. **Entries here are a debt, not a dispensation** — the same shape
#: `DELIBERATELY_UNREACHABLE` uses for capabilities, and for the same reason: a reader must be
#: able to tell "nobody has got to this" from "somebody decided this".
#:
#: **041 found these while closing its own instance of the defect and deliberately did not fix
#: them.** They belong to 037's intake gauntlet, and inventing a command for somebody else's
#: tier would be guessing at what it should run — worse than recording that it runs nothing.
#: 041's own tasks are absent from this list because 041 fixed them.
KNOWN_UNEXECUTABLE: dict[tuple[str, str], str] = {
    ("analysis-tier.nomad.hcl", "analyzer"): (
        "037's intake gauntlet — declared, reasoned, and never given a command. Found by this "
        "check on the day it was written, one feature after the same defect shipped in the "
        "authoring tier."
    ),
    ("detonation-range.nomad.hcl", "specimen"): (
        "037's detonation range — same shape, same feature, same absence."
    ),
    ("detonation-range.nomad.hcl", "observer"): (
        "037's detonation range — same shape, same feature, same absence."
    ),
}


def _tasks(text: str) -> list[tuple[str, str]]:
    """(task name, body) for every `task "x" { ... }` block, by brace depth.

    Parsed by counting braces rather than by regex over the whole block: a nested `config`
    or `env` closes with the same character, and a lazy match would end the task at the first
    one — reporting a task as having no `args` because the block stopped before reaching them.
    """
    found: list[tuple[str, str]] = []
    for match in re.finditer(r'task\s+"([^"]+)"\s*\{', text):
        name = match.group(1)
        depth = 0
        start = match.end() - 1
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    found.append((name, text[start : index + 1]))
                    break
    return found


@pytest.mark.parametrize("jobspec", sorted(JOBS.glob("*.nomad.hcl")), ids=lambda p: p.name)
def test_every_task_with_a_command_taking_entrypoint_supplies_a_command(
    jobspec: pathlib.Path,
) -> None:
    text = jobspec.read_text()
    offenders = [
        name
        for name, body in _tasks(text)
        if _COMMAND_TAKING.search(body)
        and "args" not in body
        and (jobspec.name, name) not in KNOWN_UNEXECUTABLE
    ]

    assert not offenders, (
        f"{jobspec.name}: task(s) {offenders} declare a command-taking entrypoint and no "
        f"`args`, so the task starts a shell with nothing to run and exits successfully. "
        f"That is how 038's authoring tier shipped unable to execute. Fix the task, or — if "
        f"the debt genuinely belongs to another feature — record it in KNOWN_UNEXECUTABLE "
        f"with the record that owns it."
    )


def test_the_known_debt_is_real_and_only_shrinks() -> None:
    """A stale allowlist is worse than none: it says a fixed thing is still broken.

    Every entry must still describe a task that exists and still runs nothing. When somebody
    fixes one, this row makes them delete the entry rather than leaving a record that has
    quietly become false — the defect this repository's roadmap warns about, in a test file.
    """
    stale: list[str] = []
    for (filename, task), _reason in KNOWN_UNEXECUTABLE.items():
        path = JOBS / filename
        if not path.exists():
            stale.append(f"{filename} (no such jobspec)")
            continue
        bodies = dict(_tasks(path.read_text()))
        if task not in bodies:
            stale.append(f"{filename}:{task} (no such task)")
        elif "args" in bodies[task]:
            stale.append(f"{filename}:{task} (now runs a command — delete this entry)")

    assert not stale, f"KNOWN_UNEXECUTABLE has entries that are no longer true: {stale}"


def test_the_authoring_tier_carries_no_known_debt() -> None:
    """041 fixed its own instance rather than recording it. Asserted, so it stays fixed."""
    assert not [k for k in KNOWN_UNEXECUTABLE if k[0] == "authoring-tier.nomad.hcl"]


def test_the_authoring_tier_runs_the_dispatch_entrypoint() -> None:
    """Not merely *a* command — the one that carries this platform's governance."""
    text = (JOBS / "authoring-tier.nomad.hcl").read_text()
    tasks = dict(_tasks(text))

    assert set(tasks) == {"analyzer", "proposer"}
    for name, body in tasks.items():
        assert "surfaces.dispatch.entrypoint" in body, (
            f"the {name} task must run the governed dispatch entrypoint; a task running "
            f"anything else would author outside the pipeline that governs authoring"
        )


def test_the_publishing_task_verifies_its_tooling_and_fails_by_name() -> None:
    """`git` and `gh` are the publishing path; their absence must not surface as a run failure.

    Checked at task start rather than at publish time, because by then the run has done all of
    its analysis and a person is waiting for a proposal.
    """
    text = (JOBS / "authoring-tier.nomad.hcl").read_text()
    proposer = dict(_tasks(text))["proposer"]

    assert "tooling_missing" in proposer
    for binary in ("git", "gh"):
        assert f"command -v {binary}" in proposer, (
            f"the publishing task must verify {binary} at start; installing it at runtime "
            f"would be an unpinned fetch inside the hardened tier"
        )


def test_the_analysing_task_verifies_terraform_and_fails_by_name() -> None:
    """Terraform is the Plan oracle; a missing binary must not become a green fixture.

    Checked at analyzer start rather than after Write, because a person waiting on a PR
    should not learn the allocation never had Terraform.
    """
    text = (JOBS / "authoring-tier.nomad.hcl").read_text()
    analyzer = dict(_tasks(text))["analyzer"]

    assert "tooling_missing" in analyzer
    assert "command -v terraform" in analyzer, (
        "the analysing task must verify terraform at start; installing it at runtime "
        "would be an unpinned fetch inside the hardened tier"
    )


def test_the_authoring_runtime_image_pins_terraform() -> None:
    """T023 — the allocation's image carries Terraform, not a host PATH coincidence."""
    dockerfile = JOBS.parent / "images" / "authoring-runtime" / "Dockerfile"
    text = dockerfile.read_text()
    assert "TERRAFORM_VERSION=1.15.8" in text
    assert "releases.hashicorp.com/terraform/" in text
    assert "terraform version" in text


def test_the_walk_examined_something() -> None:
    """A parser that finds no tasks reports a clean tree — the 008 failure, one file over."""
    jobspecs = list(JOBS.glob("*.nomad.hcl"))
    assert len(jobspecs) >= 3, f"only {len(jobspecs)} jobspecs found under {JOBS}"

    parsed = sum(len(_tasks(p.read_text())) for p in jobspecs)
    assert parsed >= 5, f"the task parser found only {parsed} tasks across {len(jobspecs)} files"


def test_the_detector_finds_a_task_that_runs_nothing() -> None:
    """Positive control: the check must fail on the shape it exists to catch."""
    rigged = """
    task "broken" {
      config {
        entrypoint = ["/bin/sh", "-c"]
      }
    }
    """
    name, body = _tasks(rigged)[0]
    assert name == "broken"
    assert _COMMAND_TAKING.search(body) and "args" not in body
