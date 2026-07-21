"""Exercises api/serve.py through FastAPI's TestClient -- no live server needed."""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api import serve  # noqa: E402

client = TestClient(serve.app)

# The Jenkinsfile/GitHub Actions run Unit Tests *before* Train Model, so on a
# first-ever run there is no model/artifacts/model.pt yet. Skip (not fail)
# the tests that need a real loaded model rather than assume pipeline order.
requires_trained_model = pytest.mark.skipif(
    not serve.MODEL_PATH.exists(), reason=f"no trained model at {serve.MODEL_PATH}; run model/train.py first"
)


def _synthetic_digit_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (28, 28), color=0).save(buffer, format="PNG")
    return buffer.getvalue()


@requires_trained_model
def test_health_reports_model_loaded() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model"] == "loaded"


def test_health_reports_ok_status_regardless_of_model_presence() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@requires_trained_model
def test_predict_with_valid_image_returns_prediction_and_confidence() -> None:
    files = {"file": ("digit.png", _synthetic_digit_png(), "image/png")}
    response = client.post("/predict", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["prediction"] in [str(digit) for digit in range(10)]
    assert 0.0 <= body["confidence"] <= 1.0


def test_predict_with_invalid_file_returns_400() -> None:
    files = {"file": ("not_an_image.txt", b"this is definitely not image data", "text/plain")}
    response = client.post("/predict", files=files)
    assert response.status_code == 400


def test_predict_with_missing_model_returns_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_unavailable() -> None:
        raise HTTPException(status_code=503, detail="model artifact not found")

    monkeypatch.setattr(serve, "get_model", _raise_unavailable)

    files = {"file": ("digit.png", _synthetic_digit_png(), "image/png")}
    response = client.post("/predict", files=files)
    assert response.status_code == 503
