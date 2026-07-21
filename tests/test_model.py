"""Unit-test form of the same criterion scripts/model_gate.py enforces in CI."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

METRICS_PATH = Path(__file__).resolve().parent.parent / "model" / "artifacts" / "metrics.json"
MIN_ACCURACY = 0.95


@pytest.fixture()
def metrics() -> dict[str, float]:
    if not METRICS_PATH.exists():
        pytest.skip(f"no trained model metrics at {METRICS_PATH}; run model/train.py first")
    return json.loads(METRICS_PATH.read_text())


def test_metrics_file_has_required_keys(metrics: dict[str, float]) -> None:
    for key in ("accuracy", "precision", "recall"):
        assert key in metrics


def test_accuracy_meets_minimum_bar(metrics: dict[str, float]) -> None:
    assert metrics["accuracy"] >= MIN_ACCURACY


def test_precision_and_recall_are_valid_probabilities(metrics: dict[str, float]) -> None:
    assert 0.0 <= metrics["precision"] <= 1.0
    assert 0.0 <= metrics["recall"] <= 1.0
