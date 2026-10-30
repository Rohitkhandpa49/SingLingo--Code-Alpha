import numpy as np
import pytest
import torch

from training.train_static_landmark_classifier import (
    StaticLandmarkClassifier,
    image_manifest,
    normalize_landmarks,
    pack_detected_hands,
    train_model,
)


def test_normalize_landmarks_centers_and_scales_points() -> None:
    points = [[float(index), 0.0, 0.0] for index in range(21)]

    normalized = normalize_landmarks(points)

    assert normalized.shape == (21, 3)
    assert normalized[0].tolist() == [0.0, 0.0, 0.0]
    assert normalized[-1].tolist() == [1.0, 0.0, 0.0]


def test_normalize_landmarks_rejects_invalid_input() -> None:
    with pytest.raises(ValueError, match="exactly 21"):
        normalize_landmarks([[0.0, 0.0, 0.0]])

    with pytest.raises(ValueError, match="zero landmark extent"):
        normalize_landmarks([[0.0, 0.0, 0.0] for _ in range(21)])


def test_pack_detected_hands_places_each_hand_in_runtime_slot() -> None:
    points = [[float(index + 1), 0.0, 0.0] for index in range(21)]

    pose = pack_detected_hands([points], ["Right"])

    assert pose.shape == (2, 21, 3)
    assert pose.dtype == np.float32
    assert pose[0].sum() == 0
    assert pose[1, 0].tolist() == [0.0, 0.0, 0.0]
    assert pose[1, -1].tolist() == [1.0, 0.0, 0.0]


def test_pack_detected_hands_rejects_duplicate_handedness() -> None:
    points = [[float(index + 1), 0.0, 0.0] for index in range(21)]

    with pytest.raises(ValueError, match="Duplicate handedness"):
        pack_detected_hands([points, points], ["Left", "Left"])


def test_export_model_averages_runtime_sequence_and_returns_class_logits() -> None:
    model = StaticLandmarkClassifier(class_count=35).eval()
    sequence = torch.zeros((2, 30, 2, 21, 3))
    sequence[:, :, 1, :, :] = 0.25
    scripted_model = torch.jit.script(model)

    first = scripted_model(sequence)
    sequence[:, 10:, 1, :, :] = 0.75
    second = scripted_model(sequence)

    assert first.shape == (2, 35)
    assert not torch.equal(first, second)


def test_image_manifest_can_exclude_non_class_directories(tmp_path) -> None:
    for label in ("A", "B"):
        image = tmp_path / label / "0.jpg"
        image.parent.mkdir()
        image.write_bytes(b"metadata-only test fixture")
    validation_image = tmp_path / "validation" / "Validation" / "A" / "0.jpg"
    validation_image.parent.mkdir(parents=True)
    validation_image.write_bytes(b"not part of training classes")

    records, _ = image_manifest(tmp_path, excluded_dirs=("validation",))

    assert len(records) == 2
    assert {label for label, _ in records} == {"A", "B"}


def test_train_model_uses_external_validation_without_training_on_it() -> None:
    training_features = np.random.default_rng(42).random((6, 2, 21, 3), dtype=np.float32)
    validation_features = np.random.default_rng(43).random((2, 2, 21, 3), dtype=np.float32)

    _, metrics = train_model(
        training_features,
        ["A", "A", "A", "B", "B", "B"],
        ["A", "B"],
        epochs=1,
        batch_size=2,
        patience=1,
        hidden_size=4,
        dropout=0,
        validation_data=(validation_features, ["A", "B"]),
    )

    assert metrics["evaluation_split"] == "validation"
    assert metrics["split_counts"] == {"train": 6, "validation": 2, "test": 0}
    assert metrics["validation"]["macro_precision"] >= 0
    assert metrics["validation"]["macro_recall"] >= 0
