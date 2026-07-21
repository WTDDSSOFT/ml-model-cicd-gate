"""Validates the shape and label range of the MNIST data the model trains on."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model"))
from common import DATA_DIR  # noqa: E402


@pytest.fixture(scope="module")
def train_dataset():
    torchvision = pytest.importorskip("torchvision")
    transforms = pytest.importorskip("torchvision.transforms")
    dataset = torchvision.datasets.MNIST(
        root=str(DATA_DIR), train=True, download=True, transform=transforms.ToTensor()
    )
    return dataset


def test_dataset_is_not_empty(train_dataset) -> None:
    assert len(train_dataset) > 0


def test_sample_image_shape_and_dtype(train_dataset) -> None:
    image, label = train_dataset[0]
    assert tuple(image.shape) == (1, 28, 28)
    assert image.min() >= 0.0
    assert image.max() <= 1.0
    assert isinstance(label, int)


def test_labels_are_valid_digits(train_dataset) -> None:
    sample_labels = {train_dataset[i][1] for i in range(200)}
    assert sample_labels.issubset(set(range(10)))
