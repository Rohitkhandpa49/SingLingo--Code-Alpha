import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.landmarks import LandmarkSequence
from app.services.gesture_classifier import GestureClassifier, GesturePrediction


def test_classifier_builds_fixed_shape_input_and_stays_unknown_without_model() -> None:
    settings = Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
    )
    classifier = GestureClassifier(settings)
    points = [{"x": 0.25, "y": -0.5, "z": 0.75} for _ in range(21)]
    payload = {
        "type": "landmark_sequence",
        "sequence_id": "00000000-0000-0000-0000-000000000001",
        "sample_rate_hz": 10,
        "frames": [
            {"hands": [{"handedness": "Left", "points": points}]},
            *({"hands": []} for _ in range(29)),
        ],
    }
    sequence = LandmarkSequence.model_validate(payload)

    model_input = classifier._to_model_input(sequence)

    assert len(model_input) == 1
    assert len(model_input[0]) == 30
    assert len(model_input[0][0]) == 2
    assert len(model_input[0][0][0]) == 21
    assert model_input[0][0][0][0] == [0.25, -0.5, 0.75]
    assert model_input[0][0][1][0] == [0.0, 0.0, 0.0]
    assert classifier.classify(sequence) == GesturePrediction(
        status="model_unavailable",
        label=None,
        confidence=None,
    )


def test_dynamic_input_preserves_camera_space_wrist_motion() -> None:
    settings = Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
    )
    classifier = GestureClassifier(settings)
    points = [{"x": 0.1, "y": -0.2, "z": 0.3} for _ in range(21)]
    frames = [
        {
            "hands": [
                {
                    "handedness": "Right",
                    "points": points,
                    "wrist": {"x": frame_index / 30, "y": 0.5, "z": 0.1},
                    "confidence": 0.9,
                }
            ],
            "hands_detected": 1,
        }
        for frame_index in range(30)
    ]
    sequence = LandmarkSequence.model_validate(
        {
            "type": "landmark_sequence",
            "sequence_id": "00000000-0000-0000-0000-000000000001",
            "sample_rate_hz": 10,
            "schema_version": "1.0",
            "session_id": "00000000-0000-0000-0000-000000000002",
            "frame_width": 640,
            "frame_height": 480,
            "frames": frames,
        }
    )

    model_input = classifier._to_dynamic_model_input(sequence)

    assert len(model_input[0]) == 30
    assert len(model_input[0][0][1]) == 22
    assert model_input[0][0][1][0] == [0.1, -0.2, 0.3]
    assert model_input[0][0][1][21] == [0.0, 0.5, 0.1]
    assert model_input[0][-1][1][21][0] == pytest.approx(29 / 30)


def test_classifier_does_not_infer_when_no_hands_are_present() -> None:
    settings = Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
    )
    classifier = GestureClassifier(settings)
    classifier._model = object()
    classifier._torch = object()
    sequence = LandmarkSequence.model_validate(
        {
            "type": "landmark_sequence",
            "sequence_id": "00000000-0000-0000-0000-000000000001",
            "sample_rate_hz": 10,
            "frames": [{"hands": []} for _ in range(30)],
        }
    )

    assert classifier.classify(sequence) == GesturePrediction("unknown", None, None)


def test_dynamic_classifier_requires_wrist_coordinates() -> None:
    settings = Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
    )
    classifier = GestureClassifier(settings)
    classifier._model = object()
    classifier._torch = object()
    classifier._model_type = "dynamic"
    points = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(21)]
    sequence = LandmarkSequence.model_validate(
        {
            "type": "landmark_sequence",
            "sequence_id": "00000000-0000-0000-0000-000000000001",
            "sample_rate_hz": 10,
            "frames": [
                {"hands": [{"handedness": "Left", "points": points}]},
                *({"hands": []} for _ in range(29)),
            ],
        }
    )

    with pytest.raises(RuntimeError, match="requires wrist coordinates"):
        classifier.classify(sequence)


def test_landmark_schema_rejects_mismatched_metadata() -> None:
    payload = {
        "type": "landmark_sequence",
        "sequence_id": "00000000-0000-0000-0000-000000000001",
        "sample_rate_hz": 10,
        "frames": [{"hands": [], "hands_detected": 1} for _ in range(30)],
    }

    with pytest.raises(ValidationError, match="hands_detected"):
        LandmarkSequence.model_validate(payload)

    payload["frames"] = [{"hands": []} for _ in range(30)]
    payload["schema_version"] = "2.0"
    with pytest.raises(ValidationError, match="schema_version"):
        LandmarkSequence.model_validate(payload)


def test_classifier_loads_dynamic_model_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "gesture-classifier.pt"
    labels_path = tmp_path / "gesture-labels.json"
    model_path.write_bytes(b"test")
    labels_path.write_text(json.dumps(["A", "B"]), encoding="utf-8")
    (tmp_path / "gesture-model.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "model_type": "dynamic",
                "model_version": "dynamic-lstm-v1",
                "input_schema_version": "1.0",
                "input_shape": [1, 30, 2, 22, 3],
                "class_mapping": {"A": 0, "B": 1},
            }
        ),
        encoding="utf-8",
    )
    fake_model = SimpleNamespace(eval=lambda: None)
    fake_torch = SimpleNamespace(
        jit=SimpleNamespace(load=lambda *args, **kwargs: fake_model)
    )
    monkeypatch.setattr(
        "app.services.gesture_classifier.importlib.import_module",
        lambda _: fake_torch,
    )
    settings = Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
        gesture_model_path=model_path,
        gesture_labels_path=labels_path,
    )

    classifier = GestureClassifier(settings)

    assert classifier._model_type == "dynamic"


def test_classifier_rejects_incompatible_model_metadata_before_loading_torch(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "gesture-classifier.pt"
    labels_path = tmp_path / "gesture-labels.json"
    model_path.write_bytes(b"test")
    labels_path.write_text(json.dumps(["A", "B"]), encoding="utf-8")
    (tmp_path / "gesture-model.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "model_type": "dynamic",
                "model_version": "dynamic-lstm-v1",
                "input_schema_version": "1.0",
                "input_shape": [1, 30, 2, 21, 3],
                "class_mapping": {"A": 0, "B": 1},
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        app_env="test",
        mongodb_uri="mongodb://localhost:27017/signlingo_test",
        mongodb_database="signlingo_test",
        jwt_secret="test-only-secret-that-is-at-least-32-bytes",
        frontend_origin="http://localhost:3000",
        gesture_model_path=model_path,
        gesture_labels_path=labels_path,
    )

    with pytest.raises(RuntimeError, match="incompatible"):
        GestureClassifier(settings)
