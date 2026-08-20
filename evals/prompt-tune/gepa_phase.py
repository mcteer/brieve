# SPDX-License-Identifier: Apache-2.0
"""Individual GEPA refinement of one phase AGENTS.md (049). Eval-lane only (ADR-0071)."""

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
    REPO_ROOT,
    PhaseCompileOutcome,
    RefinementUnavailable,
    configure_dspy,
    extract_instruction,
    gepa_budget,
    instruction_lost_to_lens,
    mean_score,
    phase_metric,
    phase_trainset,
    refinement_available,
    write_result_json,
)

# Re-export for hermetic tests that load this file via runpy.
__all__ = [
    "RefinementUnavailable",
    "compile_phase",
    "copy_into_packs",
    "main",
    "refinement_available",
    "write_candidates",
]


def copy_into_packs(*, lost: bool, files: dict[str, bytes], packs_root: Path, pack: str) -> int:
    """Whole-set rule: any loss copies zero files into packs/."""
    if lost:
        return 0
    # Production copy is promote_phase_agents. This function exists so a losing metric
    # has a named no-op rather than a partial write.
    _ = (files, packs_root, pack)
    return 0


def write_candidates(pack: str, phase: str, body: str) -> Path:
    dest = CANDIDATES / pack / phase
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "AGENTS.md"
    path.write_text(body, encoding="utf-8")
    return path


def _phase_program(instruction: str) -> object:
    import dspy

    signature = dspy.Signature("task -> guidance", instructions=instruction)

    class PhasePredictor(dspy.Module):  # type: ignore[misc]
        def __init__(self) -> None:
            super().__init__()
            self.steer = dspy.Predict(signature)

        def forward(self, task: str) -> object:
            result = self.steer(task=task)
            return dspy.Prediction(
                guidance=getattr(result, "guidance", str(result)),
                instruction=str(self.steer.signature.instructions),
            )

    return PhasePredictor()


def compile_phase(
    instruction: str,
    metric_lost: bool,
    *,
    live: bool = False,
    pack: str = "",
    phase: str = "",
    auto: str | None = None,
    max_full_evals: int = DEFAULT_FULL_EVALS,
    max_metric_calls: int | None = None,
    repo_root: Path | None = None,
) -> str:
    """Compile one predictor with dspy.GEPA. Hermetic callers pass metric_lost."""
    if not refinement_available():
        raise RefinementUnavailable()
    import dspy

    _optimizer = dspy.GEPA
    if metric_lost or not live:
        return instruction
    outcome = compile_phase_live(
        instruction,
        pack=pack,
        phase=phase,
        auto=auto,
        max_full_evals=max_full_evals,
        max_metric_calls=max_metric_calls,
        repo_root=repo_root or REPO_ROOT,
    )
    return outcome.instruction


def compile_phase_live(
    instruction: str,
    *,
    pack: str,
    phase: str,
    auto: str | None = None,
    max_full_evals: int = DEFAULT_FULL_EVALS,
    max_metric_calls: int | None = None,
    repo_root: Path | None = None,
) -> PhaseCompileOutcome:
    if not refinement_available():
        raise RefinementUnavailable()
    if not pack or not phase:
        raise RefinementUnavailable("live GEPA requires --pack and --phase")
    import dspy

    root = repo_root or REPO_ROOT
    reflection_lm = configure_dspy()
    trainset = phase_trainset(pack, phase, repo_root=root)
    valset = trainset[-1:] or trainset
    score_set = valset
    metric = phase_metric(pack, phase)
    seed = _phase_program(instruction)
    seed_score = mean_score(seed, score_set, metric)
    log_path = CANDIDATES / pack / phase / "gepa-log"
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
        trainset=trainset[:1] or trainset,
        valset=valset,
    )
    compiled_text = extract_instruction(compiled, "steer")
    lens_reason = instruction_lost_to_lens(compiled_text)
    if lens_reason is not None:
        return PhaseCompileOutcome(
            instruction=instruction,
            seed_score=seed_score,
            compiled_score=0.0,
            lost=True,
            reason=f"injection_suspected: {lens_reason}",
        )
    compiled_score = mean_score(compiled, score_set, metric)
    lost = compiled_score < seed_score
    reason = "metric_lost" if lost else "improved_or_tied"
    if lost:
        # Keep the seed bytes rather than a worse candidate.
        compiled_text = instruction
    return PhaseCompileOutcome(
        instruction=compiled_text,
        seed_score=seed_score,
        compiled_score=compiled_score,
        lost=lost,
        reason=reason,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GEPA per-phase AGENTS.md refinement")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--instruction-file", required=True)
    parser.add_argument("--lost", action="store_true")
    parser.add_argument(
        "--live",
        action="store_true",
        help="compile with dspy.GEPA against Sonnet 5 (named-runner eval lane)",
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
    args = parser.parse_args(argv)
    if not refinement_available():
        print("refinement_unavailable", file=sys.stderr)
        return 2
    text = Path(args.instruction_file).read_text(encoding="utf-8")
    lost = bool(args.lost)
    reason = "cli_lost" if lost else "seed_passthrough"
    seed_score = 0.0
    compiled_score = 0.0
    compiled = text
    if args.live and not args.lost:
        try:
            outcome = compile_phase_live(
                text,
                pack=args.pack,
                phase=args.phase,
                auto=args.auto,
                max_full_evals=args.max_full_evals,
                max_metric_calls=args.max_metric_calls,
            )
        except RefinementUnavailable as exc:
            print(str(exc) or "refinement_unavailable", file=sys.stderr)
            return 2
        compiled = outcome.instruction
        lost = outcome.lost
        reason = outcome.reason
        seed_score = outcome.seed_score
        compiled_score = outcome.compiled_score
    else:
        compiled = compile_phase(text, metric_lost=args.lost, live=False)
    dest = write_candidates(args.pack, args.phase, compiled)
    write_result_json(
        dest.parent / "result.json",
        {
            "pack": args.pack,
            "phase": args.phase,
            "lost": lost,
            "reason": reason,
            "seed_score": seed_score,
            "compiled_score": compiled_score,
            "live": bool(args.live),
            "auto": args.auto,
            "max_full_evals": args.max_full_evals,
            "max_metric_calls": args.max_metric_calls,
            "optimizer": "dspy.GEPA",
        },
    )
    copied = copy_into_packs(
        lost=lost,
        files={args.phase: compiled.encode()},
        packs_root=Path("packs"),
        pack=args.pack,
    )
    return 1 if lost or copied else 0


if __name__ == "__main__":
    raise SystemExit(main())
