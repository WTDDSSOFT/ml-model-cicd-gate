"""FastAPI serving layer for the trained digit classifier.

Endpoints:
  POST /predict  - classify an uploaded grayscale digit image
  GET  /health   - liveness/readiness probe used by health_check.py and Ansible
  GET  /metrics  - Prometheus exposition format, scraped by monitoring/prometheus.yml
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException, UploadFile
from PIL import Image
from prometheus_client import Counter, Gauge, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from torchvision import transforms

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model"))
from common import CLASS_NAMES, METRICS_PATH, MODEL_PATH, load_model  # noqa: E402

MODEL_VERSION = os.environ.get("MODEL_VERSION", "dev")

app = FastAPI(title="ml-model-cicd-gate API", version=MODEL_VERSION)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Static, set once at startup from the metrics.json the training/eval stage
# produced -- this is a TRAINING-time number (held-out test set), not a
# measurement of how the model is doing on live traffic. It answers "was
# this the model we intended to ship", not "is it still accurate in
# production" -- there's no production ground truth to compare against
# without a labeling pipeline, which this project doesn't have.
model_training_accuracy_gauge = Gauge(
    "ml_model_training_accuracy",
    "Accuracy recorded for the currently deployed model at training/eval time (not a live metric)",
)
if METRICS_PATH.exists():
    model_training_accuracy_gauge.set(json.loads(METRICS_PATH.read_text())["accuracy"])

# These two, by contrast, are real production signals: what the model is
# actually being asked to classify, and how confident it is while doing it.
predictions_total = Counter(
    "ml_predictions_total", "Total predictions served, by predicted class", ["predicted_class"]
)
prediction_confidence = Histogram(
    "ml_prediction_confidence",
    "Top-1 predicted class probability for each /predict call",
    buckets=(0.5, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0),
)

_transform = transforms.Compose([
    transforms.Grayscale(num_output_channels=1),
    transforms.Resize((28, 28)),
    transforms.ToTensor(),
])

_model = None


def get_model():
    global _model
    if _model is None:
        if not MODEL_PATH.exists():
            raise HTTPException(status_code=503, detail="model artifact not found")
        _model = load_model(MODEL_PATH)
    return _model


@app.get("/health")
def health() -> dict[str, str]:
    model_status = "loaded" if MODEL_PATH.exists() else "missing"
    return {"status": "ok", "model_version": MODEL_VERSION, "model": model_status}


@app.post("/predict")
async def predict(file: UploadFile) -> dict[str, object]:
    # Validate the input before touching the model, so a bad upload always
    # gets a 400 regardless of whether a model is currently loaded.
    try:
        image = Image.open(io.BytesIO(await file.read()))
    except Exception as exc:  # noqa: BLE001 - surface any decode failure as a 400
        raise HTTPException(status_code=400, detail=f"invalid image: {exc}") from exc

    model = get_model()
    tensor = _transform(image).unsqueeze(0)
    with torch.no_grad():
        logits = model(tensor)
        probabilities = torch.softmax(logits, dim=1).squeeze(0)
        predicted_index = int(probabilities.argmax())
        confidence = float(probabilities[predicted_index])

    predicted_class = CLASS_NAMES[predicted_index]
    predictions_total.labels(predicted_class=predicted_class).inc()
    prediction_confidence.observe(confidence)

    return {
        "prediction": predicted_class,
        "confidence": confidence,
        "model_version": MODEL_VERSION,
    }
