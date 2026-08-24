# SPDX-License-Identifier: Apache-2.0
"""Joint five-predictor DSPy program compiled with dspy.GEPA (049). Eval-lane only."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
_SRC = _SCRIPT_DIR.parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from _common import (  # noqa: E402
    CANDIDATES,
    DEFAULT_FULL_EVALS,
    PHASES,
    REPO_ROOT,
    JointCompileOutcome,
    RefinementUnavailable,
    build_metric,
    build_trainset,
    configure_dspy,
    extract_instructions,
    gepa_budget,
    instruction_lost_to_lens,
    mean_score,
    refinement_available,
    write_result_json,
)

__all__ = [
    "RefinementUnavailable",
    "compile_build",
    "copy_into_packs",
    "main",
    "refinement_available",
]

PHASES_LOCAL = PHASES


def copy_into_packs(*, lost: bool, files: dict[str, bytes], packs_root: Path, pack: str) -> int:
    """Whole-set rule: a losing joint metric copies zero files into packs/."""
    if lost:
        return 0
    _ = (files, packs_root, pack)
    return 0


def _build_program(texts: dict[str, str]) -> object:
    import dspy

    class BuildProgram(dspy.Module):  # type: ignore[misc]
        def __init__(self, instructions: dict[str, str]) -> None:
            super().__init__()
            self.research = dspy.Predict(
                dspy.Signature("task -> research", instructions=instructions["research"])
            )
            self.plan = dspy.Predict(
                dspy.Signature("task -> plan", instructions=instructions["plan"])
            )
            self.write = dspy.Predict(
                dspy.Signature("task -> write", instructions=instructions["write"])
            )
            self.judge = dspy.Predict(
                dspy.Signature("task -> judge", instructions=instructions["judge"])
            )
            self.propose = dspy.Predict(
                dspy.Signature("task -> proposal", instructions=instructions["propose"])
            )

        def forward(self, task: str) -> object:
            research = self.research(task=task)
            plan = self.plan(task=task)
            write = self.write(task=task)
            judge = self.judge(task=task)
            propose = self.propose(task=task)
            return dspy.Prediction(
                research=getattr(research, "research", str(research)),
                plan=getattr(plan, "plan", str(plan)),
                write=getattr(write, "write", str(write)),
                judge=getattr(judge, "judge", str(judge)),
                proposal=getattr(propose, "proposal", str(propose)),
                propose=getattr(propose, "proposal", str(propose)),
                research_instruction=str(self.research.signature.instructions),
                plan_instruction=str(self.plan.signature.instructions),
                write_instruction=str(self.write.signature.instructions),
                judge_instruction=str(self.judge.signature.instructions),
                propose_instruction=str(self.propose.signature.instructions),
            )

    return BuildProgram(texts)


def compile_build(
    instructions: dict[str, str],
    *,
    metric_lost: bool,
    live: bool = False,
    pack: str = "",
    auto: str | None = None,
    max_full_evals: int = DEFAULT_FULL_EVALS,
    max_metric_calls: int | None = None,
    repo_root: Path | None = None,
) -> dict[str, str]:
    if not refinement_available():
        raise RefinementUnavailable()
    import dspy

    _optimizer = dspy.GEPA
    _ = _build_program
    if metric_lost or not live:
        return instructions
    outcome = compile_build_live(
        instructions,
        pack=pack,
        auto=auto,
        max_full_evals=max_full_evals,
        max_metric_calls=max_metric_calls,
        repo_root=repo_root or REPO_ROOT,
    )
    return outcome.instructions


def compile_build_live(
    instructions: dict[str, str],
    *,
    pack: str,
    auto: str | None = None,
    max_full_evals: int = DEFAULT_FULL_EVALS,
    max_metric_calls: int | None = None,
    repo_root: Path | None = None,
) -> JointCompileOutcome:
    if not refinement_available():
        raise RefinementUnavailable()
    if not pack:
        raise RefinementUnavailable("live joint compile requires --pack")
    import dspy

    root = repo_root or REPO_ROOT
    reflection_lm = configure_dspy()
    trainset = build_trainset(pack, repo_root=root)
    valset = trainset
    score_set = valset
    metric = build_metric(pack)
    seed = _build_program(instructions)
    seed_score = mean_score(seed, score_set, metric)
    log_path = CANDIDATES / pack / "joint-gepa-log"
    if log_path.exists():
        shutil.rmtree(log_path)
    log_dir = str(log_path)
    optimizer = dspy.GEPA(
        metric=metric,
        reflection_lm=reflection_lm,
        num_threads=1,
        track_stats=True,
        skip_perfect_score=False,
        add_format_failure_as_feedback=True,
        log_dir=log_dir,
        seed=0,
        use_merge=False,
        **gepa_budget(
            auto=auto,
            max_full_evals=max_full_evals,
            max_metric_calls=max_metric_calls,
        ),
    )
    compiled = optimizer.compile(
        seed,
        trainset=trainset,
        valset=valset,
    )
    compiled_texts = extract_instructions(compiled)
    merged = dict(instructions)
    merged.update(compiled_texts)
    # Predictor named `propose` emits field `proposal`; keep the phase key.
    if "proposal" in merged and "propose" not in compiled_texts:
        merged["propose"] = merged["proposal"]
    for phase in PHASES_LOCAL:
        body = merged.get(phase, instructions.get(phase, ""))
        lens_reason = instruction_lost_to_lens(body)
        if lens_reason is not None:
            return JointCompileOutcome(
                instructions=instructions,
                seed_score=seed_score,
                compiled_score=0.0,
                lost=True,
                reason=f"injection_suspected:{phase}:{lens_reason}",
            )
    compiled_score = mean_score(compiled, score_set, metric)
    lost = compiled_score < seed_score
    reason = "metric_lost" if lost else "improved_or_tied"
    if lost:
        merged = instructions
    return JointCompileOutcome(
        instructions={phase: merged[phase] for phase in PHASES_LOCAL},
        seed_score=seed_score,
        compiled_score=compiled_score,
        lost=lost,
        reason=reason,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Joint DSPy GEPA compile for five AGENTS.md")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--lost", action="store_true")
    parser.add_argument(
        "--live",
        action="store_true",
        help="compile the five-predictor module with dspy.GEPA against Sonnet 5",
    )
    parser.add_argument(
        "--auto",
        choices=("light", "medium", "heavy"),
        default=None,
        help="GEPA preset. Do not use for a test run; it is far larger than 10 evals.",
    )
    parser.add_argument(
        "--max-full-evals",
        type=int,
        default=DEFAULT_FULL_EVALS,
        help=f"GEPA full-eval cap (default {DEFAULT_FULL_EVALS}, the test iteration limit)",
    )
    parser.add_argument(
        "--max-metric-calls",
        type=int,
        default=None,
        help="Optional raw metric-call cap; overrides --max-full-evals when set",
    )
    parser.add_argument(
        "--from-candidates",
        action="store_true",
        help="read individual GEPA candidates instead of seed packs/ files",
    )
    args = parser.parse_args(argv)
    if not refinement_available():
        print("refinement_unavailable", file=sys.stderr)
        return 2
    instructions: dict[str, str] = {}
    for phase in PHASES_LOCAL:
        if args.from_candidates:
            path = CANDIDATES / args.pack / phase / "AGENTS.md"
        else:
            path = Path("packs") / args.pack / "agents" / phase / "AGENTS.md"
        instructions[phase] = path.read_text(encoding="utf-8") if path.is_file() else ""
    lost = bool(args.lost)
    reason = "cli_lost" if lost else "seed_passthrough"
    seed_score = 0.0
    compiled_score = 0.0
    compiled = instructions
    if args.live and not args.lost:
        try:
            outcome = compile_build_live(
                instructions,
                pack=args.pack,
                auto=args.auto,
                max_full_evals=args.max_full_evals,
                max_metric_calls=args.max_metric_calls,
            )
        except RefinementUnavailable as exc:
            print(str(exc) or "refinement_unavailable", file=sys.stderr)
            return 2
        compiled = outcome.instructions
        lost = outcome.lost
        reason = outcome.reason
        seed_score = outcome.seed_score
        compiled_score = outcome.compiled_score
    else:
        compiled = compile_build(instructions, metric_lost=args.lost, live=False)
    for phase, body in compiled.items():
        dest = CANDIDATES / args.pack / phase
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "AGENTS.md").write_text(body, encoding="utf-8")
    write_result_json(
        CANDIDATES / args.pack / "joint_result.json",
        {
            "pack": args.pack,
            "lost": lost,
            "reason": reason,
            "seed_score": seed_score,
            "compiled_score": compiled_score,
            "live": bool(args.live),
            "auto": args.auto,
            "max_full_evals": args.max_full_evals,
            "max_metric_calls": args.max_metric_calls,
            "optimizer": "dspy.GEPA",
            "predictors": 5,
        },
    )
    copied = copy_into_packs(
        lost=lost,
        files={phase: body.encode() for phase, body in compiled.items()},
        packs_root=Path("packs"),
        pack=args.pack,
    )
    return 1 if lost or copied else 0


if __name__ == "__main__":
    raise SystemExit(main())
