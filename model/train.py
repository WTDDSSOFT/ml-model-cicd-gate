"""Trains DigitCNN on MNIST and writes model.pt + metrics.json to model/artifacts/.

Kept intentionally small (subset of MNIST, 5 epochs) so it runs in well under
a minute on CI free-tier runners -- the pipeline exists to gate the model,
not to chase state-of-the-art accuracy.
"""
from __future__ import annotations

import os

# Must be set before CUDA is initialized for cuBLAS determinism; harmless on
# CPU-only runs (which is what CI and this README's local instructions use).
os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import precision_score, recall_score
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS_DIR, DATA_DIR, METRICS_PATH, MODEL_PATH, DigitCNN  # noqa: E402

TRAIN_SUBSET_SIZE = 10000
TEST_SUBSET_SIZE = 2000
EPOCHS = 10
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
DEFAULT_SEED = 42


def set_seed(seed: int) -> None:
    """Pins every RNG this script touches so metrics.json is bit-for-bit
    reproducible across runs given the same code and data. On GPU this also
    forces deterministic (slower) kernel implementations; on CPU -- the only
    target this project tests against -- it has no measurable performance cost.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def get_datasets() -> tuple[Subset, Subset]:
    transform = transforms.Compose([transforms.ToTensor()])
    train_full = datasets.MNIST(root=str(DATA_DIR), train=True, download=True, transform=transform)
    test_full = datasets.MNIST(root=str(DATA_DIR), train=False, download=True, transform=transform)
    train_subset = Subset(train_full, range(TRAIN_SUBSET_SIZE))
    test_subset = Subset(test_full, range(TEST_SUBSET_SIZE))
    return train_subset, test_subset


def train_one_epoch(model: DigitCNN, loader: DataLoader, optimizer: torch.optim.Optimizer) -> float:
    model.train()
    criterion = nn.CrossEntropyLoss()
    total_loss = 0.0
    for images, labels in loader:
        optimizer.zero_grad()
        loss = criterion(model(images), labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * images.size(0)
    return total_loss / len(loader.dataset)


@torch.no_grad()
def evaluate(model: DigitCNN, loader: DataLoader) -> dict[str, float]:
    model.eval()
    all_preds: list[int] = []
    all_labels: list[int] = []
    for images, labels in loader:
        preds = model(images).argmax(dim=1)
        all_preds.extend(preds.tolist())
        all_labels.extend(labels.tolist())
    accuracy = sum(p == t for p, t in zip(all_preds, all_labels)) / len(all_labels)
    precision = precision_score(all_labels, all_preds, average="macro", zero_division=0)
    recall = recall_score(all_labels, all_preds, average="macro", zero_division=0)
    return {"accuracy": accuracy, "precision": precision, "recall": recall}


def main() -> None:
    parser = argparse.ArgumentParser(description="Train DigitCNN on MNIST")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--seed", type=int, default=int(os.environ.get("TRAIN_SEED", DEFAULT_SEED)))
    args = parser.parse_args()

    set_seed(args.seed)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    train_subset, test_subset = get_datasets()
    train_loader = DataLoader(train_subset, batch_size=BATCH_SIZE, shuffle=True)
    test_loader = DataLoader(test_subset, batch_size=BATCH_SIZE)

    model = DigitCNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    for epoch in range(1, args.epochs + 1):
        loss = train_one_epoch(model, train_loader, optimizer)
        print(f"epoch {epoch}/{args.epochs} - train_loss={loss:.4f}")

    metrics = evaluate(model, test_loader)
    print(f"eval metrics: {metrics}")

    torch.save(model.state_dict(), MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    print(f"saved model to {MODEL_PATH}")
    print(f"saved metrics to {METRICS_PATH}")


if __name__ == "__main__":
    main()
