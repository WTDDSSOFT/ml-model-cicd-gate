"""Validates the shape and label range of the MNIST data the model trains on.

The default (non-integration) tests read from whatever is already cached
under model/data/ -- they skip rather than fail if nothing is cached, so
`pytest` never needs network access. test_download_fetches_dataset is the
one test that actually exercises the download path; it's marked
`integration` and only runs when explicitly requested with `pytest -m
integration`, since it needs to reach the internet.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "model"))
from common import DATA_DIR  # noqa: E402


@pytest.fixture(scope="module")
def cached_train_dataset():
    torchvision = pytest.importorskip("torchvision")
    transforms = pytest.importorskip("torchvision.transforms")
    try:
        return torchvision.datasets.MNIST(
            root=str(DATA_DIR), train=True, download=False, transform=transforms.ToTensor()
        )
    except RuntimeError:
        pytest.skip(f"no cached MNIST data under {DATA_DIR}; run model/train.py once, or "
                    f"`pytest -m integration` to test the download path")


def test_dataset_is_not_empty(cached_train_dataset) -> None:
    assert len(cached_train_dataset) > 0


def test_sample_image_shape_and_dtype(cached_train_dataset) -> None:
    image, label = cached_train_dataset[0]
    assert tuple(image.shape) == (1, 28, 28)
    assert image.min() >= 0.0
    assert image.max() <= 1.0
    assert isinstance(label, int)


def test_labels_are_valid_digits(cached_train_dataset) -> None:
    sample_labels = {cached_train_dataset[i][1] for i in range(200)}
    assert sample_labels.issubset(set(range(10)))


@pytest.mark.integration
def test_download_fetches_dataset() -> None:
    torchvision = pytest.importorskip("torchvision")
    transforms = pytest.importorskip("torchvision.transforms")
    dataset = torchvision.datasets.MNIST(
        root=str(DATA_DIR), train=True, download=True, transform=transforms.ToTensor()
    )
    assert len(dataset) > 0
