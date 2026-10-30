from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Mapping

ModelType = Literal["static", "dynamic"]


@dataclass(frozen=True)
class ModelDescriptor:
    directory: Path
    checkpoint_path: Path
    model_version: str
    model_type: ModelType
    input_schema_version: str
    input_shape: tuple[int, ...]
    labels: tuple[str, ...]
    confidence_threshold: float
    feature_config: Mapping[str, object]
    architecture: Mapping[str, object]
    dataset_version: str | None


class ModelRegistry:
    """Discovers checkpoint bundles and rejects duplicate or incompatible versions."""

    def __init__(self) -> None:
        self._models: dict[str, ModelDescriptor] = {}

    @property
    def models(self) -> tuple[ModelDescriptor, ...]:
        return tuple(self._models.values())

    def register_directory(self, directory: Path) -> ModelDescriptor:
        metadata_path = directory / "gesture-model.json"
        labels_path = directory / "gesture-labels.json"
        checkpoint_path = directory / "gesture-classifier.pt"
        if not checkpoint_path.is_file():
            raise FileNotFoundError(f"Model checkpoint not found: {checkpoint_path}")
        if not metadata_path.is_file() or not labels_path.is_file():
            raise FileNotFoundError(f"Model metadata or labels are missing from {directory}")

        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        labels = json.loads(labels_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict) or not isinstance(labels, list):
            raise ValueError(f"Invalid model bundle in {directory}")
        model_type = metadata.get("model_type")
        points_per_hand = 22 if model_type == "dynamic" else 21
        expected_shape = (1, 30, 2, points_per_hand, 3)
        valid_labels = bool(labels) and all(
            isinstance(label, str) and label.strip() for label in labels
        )
        valid_labels = valid_labels and len(labels) == len(set(labels))
        class_mapping = (
            {label: index for index, label in enumerate(labels)}
            if valid_labels
            else {}
        )
        threshold = metadata.get("confidence_threshold")
        model_version = metadata.get("model_version")
        feature_config = metadata.get("feature_config")
        architecture = metadata.get("architecture")
        dataset_version = metadata.get("dataset_version")
        if (
            metadata.get("schema_version") != "1.0"
            or metadata.get("input_schema_version") != "1.0"
            or model_type not in {"static", "dynamic"}
            or metadata.get("input_shape") != list(expected_shape)
            or not valid_labels
            or metadata.get("class_mapping") != class_mapping
            or not isinstance(model_version, str)
            or not model_version.strip()
            or not isinstance(threshold, (float, int))
            or isinstance(threshold, bool)
            or not 0 <= threshold <= 1
            or not isinstance(feature_config, dict)
            or not isinstance(architecture, dict)
            or (
                dataset_version is not None
                and (not isinstance(dataset_version, str) or not dataset_version.strip())
            )
        ):
            raise ValueError(f"Model bundle metadata is incompatible: {directory}")
        if model_version in self._models:
            raise ValueError(f"Duplicate model version registered: {model_version}")

        descriptor = ModelDescriptor(
            directory=directory,
            checkpoint_path=checkpoint_path,
            model_version=model_version,
            model_type=model_type,
            input_schema_version="1.0",
            input_shape=expected_shape,
            labels=tuple(labels),
            confidence_threshold=float(threshold),
            feature_config=feature_config,
            architecture=architecture,
            dataset_version=dataset_version,
        )
        self._models[model_version] = descriptor
        return descriptor

    def discover(self, models_root: Path) -> tuple[ModelDescriptor, ...]:
        for metadata_path in sorted(models_root.rglob("gesture-model.json")):
            self.register_directory(metadata_path.parent)
        return self.models
