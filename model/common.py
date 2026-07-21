"""Shared model definition and paths used by train.py, evaluate.py and the serving API."""
from __future__ import annotations

from pathlib import Path

import torch
from torch import nn

MODEL_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = MODEL_DIR / "artifacts"
DATA_DIR = MODEL_DIR / "data"
MODEL_PATH = ARTIFACTS_DIR / "model.pt"
METRICS_PATH = ARTIFACTS_DIR / "metrics.json"

CLASS_NAMES = [str(digit) for digit in range(10)]


class DigitCNN(nn.Module):
    """Small CNN for 28x28 grayscale digit classification (MNIST)."""

    def __init__(self) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
            nn.Conv2d(16, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 7 * 7, 64),
            nn.ReLU(),
            nn.Linear(64, 10),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.features(x))


def load_model(path: Path = MODEL_PATH) -> DigitCNN:
    model = DigitCNN()
    state_dict = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    return model
