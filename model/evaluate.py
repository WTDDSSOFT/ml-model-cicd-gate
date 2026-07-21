"""Reloads the saved model and recomputes metrics against the MNIST test set.

Run as a separate pipeline stage from training so the "Validate Metrics" gate
always scores the artifact that will actually be shipped, not whatever was
in memory at the end of the training process.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, METRICS_PATH, MODEL_PATH, load_model  # noqa: E402
from train import TEST_SUBSET_SIZE, evaluate  # noqa: E402


def main() -> None:
    if not MODEL_PATH.exists():
        raise SystemExit(f"no model found at {MODEL_PATH}; run train.py first")

    transform = transforms.Compose([transforms.ToTensor()])
    test_full = datasets.MNIST(root=str(DATA_DIR), train=False, download=True, transform=transform)
    test_subset = Subset(test_full, range(TEST_SUBSET_SIZE))
    test_loader = DataLoader(test_subset, batch_size=64)

    model = load_model(MODEL_PATH)
    metrics = evaluate(model, test_loader)

    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"re-evaluated metrics: {metrics}")
    print(f"updated {METRICS_PATH}")


if __name__ == "__main__":
    main()
