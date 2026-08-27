# SPDX-License-Identifier: Apache-2.0
"""SC-002 (051): does DELIVERING a pinned skill change what Write authors?

Runs one corpus task n times with the skill bound into the Write instruction, and n times
with it removed, and reports both rates. Nothing else differs between the arms — same task,
same subject, same model, same everything but the bytes under test.

**Why not the whole `tests/evals_live/authoring` lane.** That lane runs every golden task per
invocation, so a 5-and-5 comparison costs seventy model calls to learn something ten answer.
This is the measurement, isolated, so it is cheap enough to re-run when somebody doubts it.

**What a null result means.** SC-002 says the rule must be followed with the binding and
*demonstrably less often* without it — a rule the model already follows is not evidence the
skill did anything. A run that comes back level is a real answer about the rule, not a
failure of the harness, and the first attempt here returned exactly that: the task prompt
described the rule in words, so the model produced it in both arms. The prompt was the
defect. Read a level result as "this rule cannot measure the skill", and change the rule or
the prompt — never the threshold.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = _SCRIPT_DIR.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(_SCRIPT_DIR))

from _common import provider_api_key  # noqa: E402
from tests.evals_live.authoring import _author  # noqa: E402
from tests.evals_live.authoring_properties import detect  # noqa: E402

from core.evals.authoring_corpus import load_corpus  # noqa: E402
from core.evals.scoring import LIVE_MODEL  # noqa: E402
from core.packs.agents import load_phase_agents  # noqa: E402
from core.packs.loader import FilesystemPackLoader  # noqa: E402

CORPUS = ROOT / "evals" / "authoring" / "corpus.toml"
PACKS = ROOT / "packs"

#: The rule under test, and the task that asks for the situation it applies to.
PROPERTY = "tags_are_shared_not_ad_hoc"
TASK = "tagged_artifact_bucket"


def _arms() -> dict[str, str]:
    """The two instructions. They differ only in whether the skills are appended."""
    bound = load_phase_agents(
        "terraform", "write", loader=FilesystemPackLoader(PACKS), packs_root=PACKS
    ).body
    unbound = (PACKS / "terraform" / "agents" / "write" / "AGENTS.md").read_text(encoding="utf-8")
    if bound == unbound:
        raise SystemExit("the arms are identical — the pack binds no skill to write")
    return {"bound": bound, "unbound": unbound}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", type=int, default=5, help="runs per arm")
    args = parser.parse_args()

    key = provider_api_key()

    task = next(t for t in load_corpus(CORPUS).golden if t.name == TASK)
    arms = _arms()
    print(f"== SC-002 — {LIVE_MODEL} — {TASK} — n={args.n} per arm")
    print(f"   rule: {PROPERTY}")
    for name, body in arms.items():
        print(f"   {name:8} instruction: {len(body):,} bytes")
    print()

    rates: dict[str, int] = {}
    with tempfile.TemporaryDirectory() as raw:
        workdir = Path(raw)
        for arm, instruction in arms.items():
            hits = 0
            for run in range(1, args.n + 1):
                _artifact, contents, _merged, stop = _author(
                    task, api_key=key, workdir=workdir, instruction=instruction
                )
                found = PROPERTY in detect(contents)
                hits += int(found)
                mark = "yes" if found else "no "
                print(f"   {arm:8} run {run}: {mark}" + (f"  (stop: {stop})" if stop else ""))
            rates[arm] = hits
            print(f"   {arm:8} -> {hits}/{args.n}\n")

    bound, unbound = rates["bound"], rates["unbound"]
    print(f"== bound {bound}/{args.n}   unbound {unbound}/{args.n}   delta {bound - unbound:+d}")
    passed = bound >= 4 * args.n // 5 and bound > unbound
    print("== SC-002:", "PASS" if passed else "NOT DEMONSTRATED")
    if not passed:
        print(
            "   A level result is an answer about the rule, not a harness failure. Either the\n"
            "   model already follows it, or the task prompt describes it. Change the rule or\n"
            "   the prompt — never the threshold."
        )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
