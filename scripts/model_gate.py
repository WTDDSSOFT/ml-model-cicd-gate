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

ARTIFACTS_DIR = Path(__file__).resolve().parent.parent / "model" / "artifacts"
DEFAULT_METRICS_PATH = ARTIFACTS_DIR / "metrics.json"
# Snapshot of the metrics for whatever model is currently live, written by
# the Jenkinsfile's Notify stage after a build actually ships. Not committed
# to git (it's a build artifact, gitignored like metrics.json itself) --
# on a fresh checkout/agent with no prior successful build it simply won't
# exist yet, and the regression check below skips itself gracefully.
DEFAULT_BASELINE_PATH = ARTIFACTS_DIR / "production_metrics.json"
DEFAULT_THRESHOLD = 0.95
DEFAULT_REGRESSION_THRESHOLD = 0.01
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


def check_regression(
    new_metrics: dict[str, float], baseline_metrics: dict[str, float], regression_threshold: float
) -> list[str]:
    """Blocks a drop in accuracy vs. the currently-live model, even if the new
    model still clears the absolute threshold -- a model can be "good enough"
    in isolation and still be a step backwards from what's already deployed.
    """
    drop = baseline_metrics["accuracy"] - new_metrics["accuracy"]
    if drop > regression_threshold:
        return [
            f"accuracy regressed by {drop:.4f} vs. production baseline "
            f"({baseline_metrics['accuracy']:.4f} -> {new_metrics['accuracy']:.4f}), "
            f"exceeds allowed drop of {regression_threshold:.4f}"
        ]
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate a Jenkins build on model metrics")
    parser.add_argument("--metrics-path", type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--baseline-metrics-path", type=Path, default=DEFAULT_BASELINE_PATH)
    parser.add_argument("--regression-threshold", type=float, default=DEFAULT_REGRESSION_THRESHOLD)
    args = parser.parse_args()

    metrics = load_metrics(args.metrics_path)
    failures = check_gate(metrics, args.threshold)

    if args.baseline_metrics_path.exists():
        baseline_metrics = load_metrics(args.baseline_metrics_path)
        failures += check_regression(metrics, baseline_metrics, args.regression_threshold)
    else:
        print(f"no production baseline at {args.baseline_metrics_path} -- skipping regression check")

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
