from __future__ import annotations

import argparse
import statistics
import subprocess


def run_baseline_once(python_exe: str) -> dict[str, float]:
    cmd = [python_exe, "-m", "baseline.run_baseline"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    scores: dict[str, float] = {}
    for line in result.stdout.splitlines():
        if line.startswith("SCORE:"):
            _, task, score = line.split(":")
            scores[task] = float(score)
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default="python")
    parser.add_argument("--episodes", type=int, default=5)
    args = parser.parse_args()

    all_scores: dict[str, list[float]] = {}
    for _ in range(args.episodes):
        run_scores = run_baseline_once(args.python)
        for task, score in run_scores.items():
            all_scores.setdefault(task, []).append(score)

    for task, values in sorted(all_scores.items()):
        mean = statistics.mean(values)
        std = statistics.pstdev(values) if len(values) > 1 else 0.0
        print(
            f"{task}: mean={mean:.4f} std={std:.4f} "
            f"min={min(values):.4f} max={max(values):.4f} n={len(values)}"
        )


if __name__ == "__main__":
    main()
