"""CI gate: fails the pipeline if the model's metrics.json doesn't clear threshold.

This is the single quality gate this project relies on instead of Zuul's
cross-repo speculative gating -- see README.md for why. Exit code 0 means
"safe to build and deploy"; any non-zero exit must stop the Jenkins pipeline.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_METRICS_PATH = Path(__file__).resolve().parent.parent / "model" / "artifacts" / "metrics.json"
DEFAULT_THRESHOLD = 0.95
REQUIRED_METRICS = ("accuracy", "precision", "recall")


def load_metrics(metrics_path: Path) -> dict[str, float]:
    if not metrics_path.exists():
        raise SystemExit(f"BLOCKED: metrics file not found at {metrics_path}")
    metrics = json.loads(metrics_path.read_text())
    missing = [key for key in REQUIRED_METRICS if key not in metrics]
    if missing:
        raise SystemExit(f"BLOCKED: metrics file is missing required keys: {missing}")
    return metrics


def check_gate(metrics: dict[str, float], threshold: float) -> list[str]:
    failures = []
    for key in REQUIRED_METRICS:
        value = metrics[key]
        if value < threshold:
            failures.append(f"{key}={value:.4f} is below threshold {threshold:.4f}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate a Jenkins build on model metrics")
    parser.add_argument("--metrics-path", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    metrics = load_metrics(args.metrics_path)
    failures = check_gate(metrics, args.threshold)

    if failures:
        print("BLOCKED: model gate failed", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        sys.exit(1)

    print(f"PASSED: model gate cleared (threshold={args.threshold:.4f})")
    for key in REQUIRED_METRICS:
        print(f"  - {key}={metrics[key]:.4f}")


if __name__ == "__main__":
    main()
