"""Unit tests for the gate logic in scripts/model_gate.py, independent of any
trained model -- these use synthetic metrics dicts, not model/artifacts/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from model_gate import check_gate, check_regression, load_metrics  # noqa: E402

THRESHOLD = 0.95
REGRESSION_THRESHOLD = 0.01


def test_check_gate_passes_above_threshold() -> None:
    metrics = {"accuracy": 0.97, "precision": 0.96, "recall": 0.98}
    assert check_gate(metrics, THRESHOLD) == []


def test_check_gate_fails_below_threshold() -> None:
    metrics = {"accuracy": 0.80, "precision": 0.96, "recall": 0.98}
    failures = check_gate(metrics, THRESHOLD)
    assert len(failures) == 1
    assert "accuracy" in failures[0]


def test_check_gate_fails_on_every_metric_below_threshold() -> None:
    metrics = {"accuracy": 0.5, "precision": 0.5, "recall": 0.5}
    failures = check_gate(metrics, THRESHOLD)
    assert len(failures) == 3


def test_check_gate_passes_at_exact_threshold() -> None:
    metrics = {"accuracy": THRESHOLD, "precision": THRESHOLD, "recall": THRESHOLD}
    assert check_gate(metrics, THRESHOLD) == []


def test_load_metrics_missing_file_exits(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        load_metrics(tmp_path / "does_not_exist.json")


def test_load_metrics_missing_required_key_exits(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({"accuracy": 0.97}))
    with pytest.raises(SystemExit):
        load_metrics(metrics_path)


def test_check_regression_passes_when_no_drop() -> None:
    baseline = {"accuracy": 0.97}
    new = {"accuracy": 0.975}
    assert check_regression(new, baseline, REGRESSION_THRESHOLD) == []


def test_check_regression_passes_within_allowed_drop() -> None:
    baseline = {"accuracy": 0.975}
    new = {"accuracy": 0.970}  # drop of 0.005, under the 0.01 threshold
    assert check_regression(new, baseline, REGRESSION_THRESHOLD) == []


def test_check_regression_fails_on_significant_drop() -> None:
    baseline = {"accuracy": 0.975}
    new = {"accuracy": 0.95}  # drop of 0.025, still above the absolute 0.95 gate
    failures = check_regression(new, baseline, REGRESSION_THRESHOLD)
    assert len(failures) == 1
    assert "regressed" in failures[0]


def test_load_metrics_valid_file(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    payload = {"accuracy": 0.97, "precision": 0.96, "recall": 0.98}
    metrics_path.write_text(json.dumps(payload))
    assert load_metrics(metrics_path) == payload
