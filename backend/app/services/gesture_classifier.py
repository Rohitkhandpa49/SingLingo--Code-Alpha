import importlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

from app.core.config import Settings
from app.schemas.landmarks import LandmarkSequence

ClassificationStatus = Literal["classified", "unknown", "model_unavailable"]


@dataclass(frozen=True, slots=True)
class GesturePrediction:
    status: ClassificationStatus
    label: str | None
    confidence: float | None
    model_version: str | None = None


class GestureClassifier:
    def __init__(self, settings: Settings) -> None:
        self._confidence_threshold = settings.gesture_confidence_threshold
        self._torch: ModuleType | None = None
        self._model: Any = None
        self._labels: list[str] = []
        self._model_type: Literal["static", "dynamic"] = "static"
        self._model_version: str | None = None

        model_path = settings.gesture_model_path
        labels_path = settings.gesture_labels_path
        if model_path is not None and labels_path is not None:
            self._load_model(model_path, labels_path)

    def classify(self, sequence: LandmarkSequence) -> GesturePrediction:
        if self._model is None or self._torch is None:
            return GesturePrediction("model_unavailable", None, None)
        if not any(frame.hands for frame in sequence.frames):
            return GesturePrediction("unknown", None, None, self._model_version)
        if self._model_type == "dynamic" and any(
            hand.wrist is None
            for frame in sequence.frames
            for hand in frame.hands
        ):
            raise RuntimeError("The dynamic gesture model requires wrist coordinates for detected hands")

        model_input = (
            self._to_dynamic_model_input(sequence)
            if self._model_type == "dynamic"
            else self._to_model_input(sequence)
        )
        input_tensor = self._torch.tensor(model_input, dtype=self._torch.float32)
        with self._torch.inference_mode():
            logits = self._model(input_tensor)

        tensor_type = self._torch.Tensor
        if not isinstance(logits, tensor_type):
            raise RuntimeError("The configured gesture model must return a logits tensor")
        if logits.ndim != 2 or logits.shape[0] != 1 or logits.shape[1] != len(self._labels):
            raise RuntimeError(
                "The configured gesture model output does not match the configured label list"
            )

        probabilities = self._torch.softmax(logits, dim=1)
        confidence, index = probabilities.max(dim=1)
        score = float(confidence[0].item())
        if not math.isfinite(score):
            raise RuntimeError("The configured gesture model returned a non-finite confidence")
        if score < self._confidence_threshold:
            return GesturePrediction("unknown", None, score, self._model_version)
        return GesturePrediction(
            "classified",
            self._labels[int(index[0].item())],
            score,
            self._model_version,
        )

    def _load_model(self, model_path: Path, labels_path: Path) -> None:
        if not model_path.is_file():
            raise RuntimeError(f"Gesture model file does not exist: {model_path}")
        if not labels_path.is_file():
            raise RuntimeError(f"Gesture labels file does not exist: {labels_path}")

        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        if (
            not isinstance(labels, list)
            or not labels
            or any(not isinstance(label, str) or not label.strip() for label in labels)
            or len(labels) != len(set(labels))
        ):
            raise RuntimeError("Gesture labels must be a non-empty JSON list of unique strings")

        model_type: Literal["static", "dynamic"] = "static"
        model_version: str | None = None
        metadata_path = model_path.with_name("gesture-model.json")
        if metadata_path.is_file():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise RuntimeError("Gesture model metadata must contain a JSON object")
            model_type_value = metadata.get("model_type")
            expected_points = 22 if model_type_value == "dynamic" else 21
            expected_shape = [1, 30, 2, expected_points, 3]
            if (
                metadata.get("schema_version") != "1.0"
                or metadata.get("input_schema_version") != "1.0"
                or model_type_value not in {"static", "dynamic"}
                or metadata.get("input_shape") != expected_shape
                or metadata.get("class_mapping")
                != {label: index for index, label in enumerate(labels)}
                or not isinstance(metadata.get("model_version"), str)
                or not metadata["model_version"].strip()
            ):
                raise RuntimeError("Gesture model metadata is incompatible with its labels or input schema")
            model_type = model_type_value
            model_version = metadata["model_version"]

        try:
            torch = importlib.import_module("torch")
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "Install the AI-engine requirements to load the configured PyTorch gesture model"
            ) from error

        self._torch = torch
        self._model = torch.jit.load(str(model_path), map_location="cpu")
        self._model.eval()
        self._labels = labels
        self._model_type = model_type
        self._model_version = model_version

    @staticmethod
    def _to_model_input(sequence: LandmarkSequence) -> list[list[list[list[list[float]]]]]:
        values = [
            [
                [
                    [[0.0, 0.0, 0.0] for _ in range(21)]
                    for _ in range(2)
                ]
                for _ in sequence.frames
            ]
        ]
        hand_slots = {"Left": 0, "Right": 1}
        for frame_index, frame in enumerate(sequence.frames):
            for hand in frame.hands:
                slot = hand_slots[hand.handedness]
                values[0][frame_index][slot] = [
                    [point.x, point.y, point.z] for point in hand.points
                ]
        return values

    @staticmethod
    def _to_dynamic_model_input(sequence: LandmarkSequence) -> list[list[list[list[list[float]]]]]:
        values = [
            [
                [
                    [[0.0, 0.0, 0.0] for _ in range(22)]
                    for _ in range(2)
                ]
                for _ in sequence.frames
            ]
        ]
        hand_slots = {"Left": 0, "Right": 1}
        for frame_index, frame in enumerate(sequence.frames):
            for hand in frame.hands:
                slot = hand_slots[hand.handedness]
                values[0][frame_index][slot][:21] = [
                    [point.x, point.y, point.z] for point in hand.points
                ]
                if hand.wrist is not None:
                    values[0][frame_index][slot][21] = [
                        hand.wrist.x,
                        hand.wrist.y,
                        hand.wrist.z,
                    ]
        return values
