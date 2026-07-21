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
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from torchvision import transforms

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model"))
from common import CLASS_NAMES, METRICS_PATH, MODEL_PATH, load_model  # noqa: E402

MODEL_VERSION = os.environ.get("MODEL_VERSION", "dev")

app = FastAPI(title="ml-model-cicd-gate API", version=MODEL_VERSION)
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

model_accuracy_gauge = Gauge(
    "ml_model_accuracy", "Accuracy recorded for the currently deployed model at training/eval time"
)
if METRICS_PATH.exists():
    model_accuracy_gauge.set(json.loads(METRICS_PATH.read_text())["accuracy"])

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
    model = get_model()
    try:
        image = Image.open(io.BytesIO(await file.read()))
    except Exception as exc:  # noqa: BLE001 - surface any decode failure as a 400
        raise HTTPException(status_code=400, detail=f"invalid image: {exc}") from exc

    tensor = _transform(image).unsqueeze(0)
    with torch.no_grad():
        logits = model(tensor)
        probabilities = torch.softmax(logits, dim=1).squeeze(0)
        predicted_index = int(probabilities.argmax())

    return {
        "prediction": CLASS_NAMES[predicted_index],
        "confidence": float(probabilities[predicted_index]),
        "model_version": MODEL_VERSION,
    }
