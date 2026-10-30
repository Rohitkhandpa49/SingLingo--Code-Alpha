import json
from argparse import Namespace
from pathlib import Path

import numpy as np
import pytest
import torch

from datasets.landmark_dataset import load_dataset_splits
from recognition.dynamic_classifier import DynamicLandmarkClassifier
from recognition.model_registry import ModelRegistry
from training.train_dynamic_landmark_classifier import train


def _sample(sample_id: str, label: str, class_id: int, signer_id: str) -> dict[str, object]:
    frames = []
    for frame_index in range(30):
        points = [[0.0, 0.0, 0.0] for _ in range(21)]
        points[1] = [1.0, 0.0, 0.0]
        points[2] = [0.2, ((frame_index % 10) / 10), 0.0]
        frames.append(
            {
                "hands": [
                    {
                        "handedness": "Right",
                        "points": points,
                        "wrist": [frame_index / 30, class_id * 0.2, 0.0],
                    }
                ]
            }
        )
    return {
        "sample_id": sample_id,
        "label": label,
        "class_id": class_id,
        "dataset_version": "test-v1",
        "schema_version": "1.0",
        "signer_id": signer_id,
        "frames": frames,
    }


def _write_splits(directory: Path, *, leak_signer: bool = False) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    train_samples = [
        _sample("train-a-1", "A", 0, "signer-a-1"),
        _sample("train-a-2", "A", 0, "signer-a-2"),
        _sample("train-b-1", "B", 1, "signer-b-1"),
        _sample("train-b-2", "B", 1, "signer-b-2"),
    ]
    validation_signer = "signer-a-1" if leak_signer else "signer-validation"
    samples = {
        "train": train_samples,
        "validation": [
            _sample("validation-a", "A", 0, validation_signer),
            _sample("validation-b", "B", 1, "signer-validation-b"),
        ],
        "test": [
            _sample("test-a", "A", 0, "signer-test-a"),
            _sample("test-b", "B", 1, "signer-test-b"),
        ],
    }
    for name, split in samples.items():
        (directory / f"{name}.jsonl").write_text(
            "\n".join(json.dumps(sample) for sample in split) + "\n",
            encoding="utf-8",
        )


def test_dynamic_classifier_runs_and_scripts_fixed_length_sequences() -> None:
    model = DynamicLandmarkClassifier(
        class_count=3,
        hidden_size=16,
        num_layers=1,
        dropout=0.1,
    ).eval()
    sequence = torch.zeros((2, 30, 2, 22, 3))
    sequence[:, :, 1, 21, 0] = torch.linspace(0, 1, 30)

    logits = torch.jit.script(model)(sequence)

    assert logits.shape == (2, 3)
    assert torch.isfinite(logits).all()


def test_dataset_loader_checks_shape_and_signer_split_isolation(tmp_path: Path) -> None:
    split_dir = tmp_path / "splits"
    _write_splits(split_dir)

    splits, classes = load_dataset_splits(split_dir, include_wrist=True)

    assert classes == ["A", "B"]
    assert splits["train"].features.shape == (4, 30, 2, 22, 3)
    assert splits["validation"].labels.tolist() == ["A", "B"]
    assert np.isfinite(splits["test"].features).all()

    _write_splits(split_dir / "leaked", leak_signer=True)
    with pytest.raises(ValueError, match="signer leakage"):
        load_dataset_splits(split_dir / "leaked", include_wrist=True)


def test_dynamic_training_saves_test_metrics_and_refuses_implicit_overwrite(
    tmp_path: Path,
) -> None:
    split_dir = tmp_path / "splits"
    output_dir = tmp_path / "output"
    _write_splits(split_dir)
    args = Namespace(
        split_dir=split_dir,
        output_dir=output_dir,
        epochs=2,
        batch_size=4,
        patience=2,
        learning_rate=0.001,
        weight_decay=0.0,
        optimizer="AdamW",
        hidden_size=8,
        num_layers=1,
        dropout=0.0,
        seed=7,
        model_version="dynamic-lstm-test-v1",
        overwrite=False,
    )

    report = train(args)

    assert (output_dir / "gesture-classifier.pt").is_file()
    assert (output_dir / "gesture-labels.json").read_text(encoding="utf-8") == '[\n  "A",\n  "B"\n]\n'
    assert report["evaluation_split"] == "test"
    assert report["test"]["confusion_matrix"]
    assert report["test"]["model_size_bytes"] > 0
    registry = ModelRegistry()
    descriptor = registry.register_directory(output_dir)
    assert descriptor.model_type == "dynamic"
    assert descriptor.input_shape == (1, 30, 2, 22, 3)
    assert descriptor.checkpoint_path.name == "gesture-classifier.pt"
    assert descriptor.architecture["name"] == "LSTM"
    with pytest.raises(ValueError, match="Duplicate model version"):
        registry.register_directory(output_dir)
    with pytest.raises(FileExistsError, match="Refusing to overwrite"):
        train(args)
