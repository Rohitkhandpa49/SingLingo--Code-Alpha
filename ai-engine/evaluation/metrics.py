from __future__ import annotations

import time
from pathlib import Path
from typing import Sequence

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)


def classification_metrics(
    actual: Sequence[int] | np.ndarray,
    predicted: Sequence[int] | np.ndarray,
    class_names: Sequence[str],
) -> dict[str, object]:
    labels = np.arange(len(class_names))
    actual_values = np.asarray(actual, dtype=np.int64)
    predicted_values = np.asarray(predicted, dtype=np.int64)
    return {
        "accuracy": float(accuracy_score(actual_values, predicted_values)),
        "macro_precision": float(
            precision_score(actual_values, predicted_values, labels=labels, average="macro", zero_division=0)
        ),
        "weighted_precision": float(
            precision_score(actual_values, predicted_values, labels=labels, average="weighted", zero_division=0)
        ),
        "macro_recall": float(
            recall_score(actual_values, predicted_values, labels=labels, average="macro", zero_division=0)
        ),
        "weighted_recall": float(
            recall_score(actual_values, predicted_values, labels=labels, average="weighted", zero_division=0)
        ),
        "macro_f1": float(f1_score(actual_values, predicted_values, labels=labels, average="macro", zero_division=0)),
        "weighted_f1": float(
            f1_score(actual_values, predicted_values, labels=labels, average="weighted", zero_division=0)
        ),
        "per_class": classification_report(
            actual_values,
            predicted_values,
            labels=labels,
            target_names=list(class_names),
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(actual_values, predicted_values, labels=labels).tolist(),
    }


def measure_inference_seconds(predict, features: np.ndarray, *, repeats: int = 10) -> float:
    if len(features) == 0 or repeats < 1:
        raise ValueError("features and repeats must be non-empty and positive")
    start = time.perf_counter()
    for _ in range(repeats):
        predict(features)
    return (time.perf_counter() - start) / (repeats * len(features))


def model_file_size_bytes(path: Path) -> int:
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {path}")
    return path.stat().st_size
