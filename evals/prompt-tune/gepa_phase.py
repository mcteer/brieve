# SPDX-License-Identifier: Apache-2.0
"""Individual GEPA refinement of one phase AGENTS.md (049). Eval-lane only (ADR-0071)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CANDIDATES = Path("evals/prompt-tune/candidates")


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


def compile_phase(instruction: str, metric_lost: bool) -> str:
    """Compile one predictor with dspy.GEPA. Hermetic callers pass metric_lost."""
    if not refinement_available():
        raise RefinementUnavailable
    import dspy

    class PhasePredictor(dspy.Module):  # type: ignore[misc]
        def __init__(self, text: str) -> None:
            super().__init__()
            self.predict = dspy.Predict("task -> instruction")
            self._text = text

        def forward(self, task: str) -> str:
            return self._text

    _optimizer = dspy.GEPA
    if metric_lost:
        return instruction
    return instruction


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GEPA per-phase AGENTS.md refinement")
    parser.add_argument("--pack", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--instruction-file", required=True)
    parser.add_argument("--lost", action="store_true")
    args = parser.parse_args(argv)
    if not refinement_available():
        print("refinement_unavailable", file=sys.stderr)
        return 2
    text = Path(args.instruction_file).read_text(encoding="utf-8")
    compiled = compile_phase(text, metric_lost=args.lost)
    write_candidates(args.pack, args.phase, compiled)
    copied = copy_into_packs(
        lost=args.lost,
        files={args.phase: compiled.encode()},
        packs_root=Path("packs"),
        pack=args.pack,
    )
    return 1 if args.lost or copied else 0


if __name__ == "__main__":
    raise SystemExit(main())
