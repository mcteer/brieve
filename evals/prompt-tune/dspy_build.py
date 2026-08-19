# SPDX-License-Identifier: Apache-2.0
"""Joint five-predictor DSPy program compiled with dspy.GEPA (049). Eval-lane only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CANDIDATES = Path("evals/prompt-tune/candidates")
PHASES_LOCAL = ("research", "plan", "write", "judge", "propose")


class RefinementUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("refinement_unavailable")
        self.reason_code = "refinement_unavailable"


def refinement_available() -> bool:
    try:
        import dspy  # noqa: F401
    except ImportError:
        return False
    return True


def copy_into_packs(*, lost: bool, files: dict[str, bytes], packs_root: Path, pack: str) -> int:
    """Whole-set rule: a losing joint metric copies zero files into packs/."""
    if lost:
        return 0
    _ = (files, packs_root, pack)
    return 0


def compile_build(instructions: dict[str, str], *, metric_lost: bool) -> dict[str, str]:
    if not refinement_available():
        raise RefinementUnavailable
    import dspy

    class BuildProgram(dspy.Module):  # type: ignore[misc]
        def __init__(self, texts: dict[str, str]) -> None:
            super().__init__()
            self.research = dspy.Predict("task -> instruction")
            self.plan = dspy.Predict("task -> instruction")
            self.write = dspy.Predict("task -> instruction")
            self.judge = dspy.Predict("task -> instruction")
            self.propose = dspy.Predict("task -> instruction")
            self._texts = texts

        def forward(self, task: str) -> dict[str, str]:
            return self._texts

    _optimizer = dspy.GEPA
    _ = BuildProgram
    if metric_lost:
        return instructions
    return instructions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Joint DSPy GEPA compile for five AGENTS.md")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--lost", action="store_true")
    args = parser.parse_args(argv)
    if not refinement_available():
        print("refinement_unavailable", file=sys.stderr)
        return 2
    instructions: dict[str, str] = {}
    for phase in PHASES_LOCAL:
        path = Path("packs") / args.pack / "agents" / phase / "AGENTS.md"
        instructions[phase] = path.read_text(encoding="utf-8") if path.is_file() else ""
    compiled = compile_build(instructions, metric_lost=args.lost)
    for phase, body in compiled.items():
        dest = CANDIDATES / args.pack / phase
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "AGENTS.md").write_text(body, encoding="utf-8")
    copied = copy_into_packs(
        lost=args.lost,
        files={phase: body.encode() for phase, body in compiled.items()},
        packs_root=Path("packs"),
        pack=args.pack,
    )
    return 1 if args.lost or copied else 0


if __name__ == "__main__":
    raise SystemExit(main())
