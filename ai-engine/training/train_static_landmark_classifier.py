from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Sequence

import mediapipe as mp
import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import train_test_split
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
FRAME_COUNT = 30
HAND_COUNT = 2
LANDMARK_COUNT = 21
COORDINATE_COUNT = 3
DEFAULT_MIN_DETECTION_RATE = 0.8
DEFAULT_CONFIDENCE_THRESHOLD = 0.75
SEED = 42


class StaticLandmarkClassifier(nn.Module):
    def __init__(
        self,
        class_count: int,
        *,
        hidden_size: int = 256,
        dropout: float = 0.2,
    ) -> None:
        super().__init__()
        if class_count < 2 or hidden_size < 2:
            raise ValueError("class_count and hidden_size must be at least two")
        if not 0 <= dropout < 1:
            raise ValueError("dropout must be in [0, 1)")
        self.network = nn.Sequential(
            nn.Linear(HAND_COUNT * LANDMARK_COUNT * COORDINATE_COUNT, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, max(hidden_size // 2, 1)),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(max(hidden_size // 2, 1), class_count),
        )

    def forward(self, sequence: torch.Tensor) -> torch.Tensor:
        static_pose = sequence.mean(dim=1).flatten(start_dim=1)
        return self.network(static_pose)


def normalize_landmarks(points: Sequence[Sequence[float]]) -> np.ndarray:
    values = np.asarray(points, dtype=np.float32)
    if values.shape != (LANDMARK_COUNT, COORDINATE_COUNT):
        raise ValueError("A detected hand must contain exactly 21 three-dimensional landmarks")
    if not np.isfinite(values).all():
        raise ValueError("Hand landmarks must contain only finite coordinates")

    centered = values - values[0]
    scale = float(np.linalg.norm(centered, axis=1).max())
    if scale <= np.finfo(np.float32).eps:
        raise ValueError("A hand with zero landmark extent cannot be normalized")
    return centered / scale


def pack_detected_hands(
    landmarks: Sequence[Sequence[Sequence[float]]],
    handedness: Sequence[str],
) -> np.ndarray:
    if len(landmarks) != len(handedness):
        raise ValueError("Each detected hand must have one handedness category")
    if len(landmarks) > HAND_COUNT:
        raise ValueError("The classifier supports at most two hands")

    pose = np.zeros((HAND_COUNT, LANDMARK_COUNT, COORDINATE_COUNT), dtype=np.float32)
    slots = {"Left": 0, "Right": 1}
    for hand, category in zip(landmarks, handedness, strict=True):
        if category not in slots:
            raise ValueError(f"Unexpected handedness category: {category}")
        slot = slots[category]
        if np.any(pose[slot]):
            raise ValueError(f"Duplicate handedness category: {category}")
        pose[slot] = normalize_landmarks(hand)
    return pose


def image_manifest(
    dataset_dir: Path,
    *,
    excluded_dirs: Sequence[str] = (),
) -> tuple[list[tuple[str, Path]], str]:
    excluded = set(excluded_dirs)
    class_dirs = sorted(
        path
        for path in dataset_dir.iterdir()
        if path.is_dir() and path.name not in excluded
    )
    if len(class_dirs) < 2:
        raise ValueError(f"Expected at least two class directories in {dataset_dir}")

    records: list[tuple[str, Path]] = []
    for class_dir in class_dirs:
        images = sorted(
            (path for path in class_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS),
            key=lambda path: path.name.casefold(),
        )
        if not images:
            raise ValueError(f"Class directory contains no supported images: {class_dir}")
        records.extend((class_dir.name, path) for path in images)

    digest = hashlib.sha256()
    for label, path in records:
        stat = path.stat()
        entry = f"{label}\0{path.relative_to(dataset_dir).as_posix()}\0{stat.st_size}\0{stat.st_mtime_ns}\n"
        digest.update(entry.encode("utf-8"))
    return records, digest.hexdigest()


def extract_features(
    records: Sequence[tuple[str, Path]],
    model_asset: Path,
    *,
    progress_interval: int = 500,
) -> tuple[np.ndarray, list[str], dict[str, int]]:
    if not model_asset.is_file():
        raise FileNotFoundError(f"MediaPipe hand-landmarker model not found: {model_asset}")

    labels = sorted({label for label, _ in records})
    features: list[np.ndarray] = []
    extracted_labels: list[str] = []
    failures: Counter[str] = Counter()
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_asset)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_hands=HAND_COUNT,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
        for index, (label, path) in enumerate(records, start=1):
            try:
                image = mp.Image.create_from_file(str(path))
                result = detector.detect(image)
                categories = [
                    category[0].category_name if category else ""
                    for category in result.handedness
                ]
                if not result.hand_landmarks:
                    failures[label] += 1
                else:
                    pose = pack_detected_hands(
                        [
                            [[point.x, point.y, point.z] for point in hand]
                            for hand in result.hand_landmarks
                        ],
                        categories,
                    )
                    features.append(pose)
                    extracted_labels.append(label)
            except (OSError, ValueError, RuntimeError) as error:
                raise RuntimeError(f"Could not extract landmarks from {path}: {error}") from error

            if progress_interval > 0 and index % progress_interval == 0:
                print(f"Extracted {index:,}/{len(records):,} images", flush=True)

    feature_array = np.stack(features) if features else np.empty((0, HAND_COUNT, LANDMARK_COUNT, COORDINATE_COUNT), dtype=np.float32)
    return feature_array, extracted_labels, {
        label: failures[label] for label in labels if failures[label]
    }


def train_model(
    features: np.ndarray,
    labels: Sequence[str],
    class_names: Sequence[str],
    *,
    epochs: int,
    batch_size: int,
    patience: int,
    learning_rate: float = 1e-3,
    weight_decay: float = 1e-4,
    hidden_size: int = 256,
    dropout: float = 0.2,
    seed: int = SEED,
    optimizer_name: str = "AdamW",
    validation_data: tuple[np.ndarray, Sequence[str]] | None = None,
) -> tuple[StaticLandmarkClassifier, dict[str, object]]:
    if len(features) != len(labels):
        raise ValueError("The feature and label counts do not match")
    counts = Counter(labels)
    if any(counts[class_name] < 3 for class_name in class_names):
        insufficient = {name: counts[name] for name in class_names if counts[name] < 3}
        raise ValueError(f"Each class needs at least three extracted images: {insufficient}")

    label_to_index = {name: index for index, name in enumerate(class_names)}
    targets = np.asarray([label_to_index[label] for label in labels], dtype=np.int64)
    indices = np.arange(len(targets))
    if validation_data is None:
        train_and_validation, test_indices = train_test_split(
            indices,
            test_size=0.15,
            random_state=seed,
            stratify=targets,
        )
        train_indices, validation_indices = train_test_split(
            train_and_validation,
            test_size=0.15 / 0.85,
            random_state=seed,
            stratify=targets[train_and_validation],
        )
        validation_features = torch.from_numpy(features[validation_indices])
        validation_targets = torch.from_numpy(targets[validation_indices])
    else:
        validation_features_array, validation_labels = validation_data
        unknown_validation_labels = set(validation_labels).difference(label_to_index)
        if unknown_validation_labels:
            raise ValueError(
                f"Validation split contains labels absent from training: {sorted(unknown_validation_labels)}"
            )
        if len(validation_features_array) != len(validation_labels) or len(validation_labels) == 0:
            raise ValueError("Validation features and labels must have the same non-zero length")
        train_indices = indices
        test_indices = np.empty(0, dtype=np.int64)
        validation_features = torch.from_numpy(validation_features_array)
        validation_targets = torch.from_numpy(
            np.asarray([label_to_index[label] for label in validation_labels], dtype=np.int64)
        )

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = StaticLandmarkClassifier(
        len(class_names),
        hidden_size=hidden_size,
        dropout=dropout,
    ).to(device)
    optimizer_type = {
        "Adam": torch.optim.Adam,
        "AdamW": torch.optim.AdamW,
    }.get(optimizer_name)
    if optimizer_type is None:
        raise ValueError(f"Unsupported optimizer: {optimizer_name}")
    optimizer = optimizer_type(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )
    loss_function = nn.CrossEntropyLoss()
    train_set = TensorDataset(
        torch.from_numpy(features[train_indices]),
        torch.from_numpy(targets[train_indices]),
    )
    train_loader = DataLoader(
        train_set,
        batch_size=batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    validation_features = validation_features.to(device)
    validation_targets = validation_targets.to(device)
    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    best_epoch = 0
    epochs_without_improvement = 0

    for epoch in range(1, epochs + 1):
        model.train()
        for batch_features, batch_targets in train_loader:
            batch_features = batch_features.to(device)
            batch_targets = batch_targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model.network(batch_features.flatten(start_dim=1))
            loss = loss_function(logits, batch_targets)
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.inference_mode():
            validation_logits = model.network(validation_features.flatten(start_dim=1))
            validation_loss = float(loss_function(validation_logits, validation_targets).item())
        print(
            f"Epoch {epoch:02d}/{epochs}: validation loss {validation_loss:.4f}",
            flush=True,
        )
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = {
                name: value.detach().cpu().clone()
                for name, value in model.state_dict().items()
            }
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                break

    if best_state is None:
        raise RuntimeError("Training did not produce a validated model checkpoint")
    model.load_state_dict(best_state)
    model.to(device)
    model.eval()

    evaluation_split = "validation" if validation_data is not None else "test"
    if validation_data is None:
        evaluation_features = torch.from_numpy(features[test_indices]).to(device)
        evaluation_targets = targets[test_indices]
    else:
        evaluation_features = validation_features
        evaluation_targets = validation_targets.cpu().numpy()
    inference_started = time.perf_counter()
    with torch.inference_mode():
        test_logits = model.network(evaluation_features.flatten(start_dim=1))
        probabilities = torch.softmax(test_logits, dim=1).cpu().numpy()
    inference_seconds_per_sequence = (
        time.perf_counter() - inference_started
    ) / len(evaluation_targets)

    predicted = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    threshold = DEFAULT_CONFIDENCE_THRESHOLD
    accepted = confidence >= threshold
    selective_accuracy = (
        float(accuracy_score(evaluation_targets[accepted], predicted[accepted]))
        if accepted.any()
        else None
    )
    report = classification_report(
        evaluation_targets,
        predicted,
        labels=np.arange(len(class_names)),
        target_names=list(class_names),
        output_dict=True,
        zero_division=0,
    )
    evaluation_metrics: dict[str, object] = {
        "accuracy": float(accuracy_score(evaluation_targets, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(evaluation_targets, predicted)),
        "macro_precision": float(
            precision_score(evaluation_targets, predicted, average="macro", zero_division=0)
        ),
        "macro_recall": float(
            recall_score(evaluation_targets, predicted, average="macro", zero_division=0)
        ),
        "macro_f1": float(f1_score(evaluation_targets, predicted, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(evaluation_targets, predicted, average="weighted", zero_division=0)),
        "confidence_threshold": threshold,
        "threshold_coverage": float(accepted.mean()),
        "threshold_selective_accuracy": selective_accuracy,
        "inference_seconds_per_sequence": inference_seconds_per_sequence,
        "class_distribution": {
            name: int(np.count_nonzero(evaluation_targets == index))
            for index, name in enumerate(class_names)
        },
        "per_class": report,
        "confusion_matrix": confusion_matrix(
            evaluation_targets,
            predicted,
            labels=np.arange(len(class_names)),
        ).tolist(),
    }
    metrics: dict[str, object] = {
        "evaluation_split": evaluation_split,
        "seed": seed,
        "device": str(device),
        "best_epoch": best_epoch,
        "validation_loss": best_loss,
        "split_counts": {
            "train": int(len(train_indices)),
            "validation" if validation_data is not None else "internal_validation": int(
                len(validation_targets)
            ),
            "test": int(len(test_indices)),
        },
        evaluation_split: evaluation_metrics,
        "training_config": {
            "epochs": epochs,
            "batch_size": batch_size,
            "patience": patience,
            "learning_rate": learning_rate,
            "weight_decay": weight_decay,
            "hidden_size": hidden_size,
            "dropout": dropout,
            "optimizer": optimizer_name,
        },
    }
    return model, metrics


def load_or_extract(
    records: Sequence[tuple[str, Path]],
    manifest_hash: str,
    model_asset: Path,
    cache_path: Path,
) -> tuple[np.ndarray, list[str], dict[str, int]]:
    metadata_path = cache_path.with_suffix(".json")
    model_hash = hashlib.sha256(model_asset.read_bytes()).hexdigest()
    if cache_path.is_file() and metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (
            metadata.get("dataset_manifest_sha256") == manifest_hash
            and metadata.get("hand_model_sha256") == model_hash
        ):
            with np.load(cache_path, allow_pickle=False) as cache:
                features = cache["features"]
                labels = cache["labels"].tolist()
                failures = json.loads(str(cache["failures"].item()))
            print(f"Reusing landmark cache: {cache_path}", flush=True)
            return features, labels, failures

    features, labels, failures = extract_features(records, model_asset)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        cache_path,
        features=features,
        labels=np.asarray(labels, dtype=np.str_),
        failures=json.dumps(failures),
    )
    metadata_path.write_text(
        json.dumps(
            {
                "dataset_manifest_sha256": manifest_hash,
                "hand_model_sha256": model_hash,
                "record_count": len(records),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return features, labels, failures


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract local hand landmarks and train an experimental static-sign classifier."
    )
    parser.add_argument("--dataset-dir", required=True, type=Path)
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Top-level directory name to ignore instead of treating it as a class (repeatable).",
    )
    parser.add_argument(
        "--validation-dir",
        type=Path,
        help="Separate class-folder validation set; excluded from model fitting.",
    )
    parser.add_argument("--hand-model", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "checkpoints",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--hidden-size", type=int, default=256)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--optimizer", choices=("Adam", "AdamW"), default="AdamW")
    parser.add_argument("--model-version", type=str, default="static-pose-mlp-v1")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--min-detection-rate",
        type=float,
        default=DEFAULT_MIN_DETECTION_RATE,
    )
    parser.add_argument("--force-extract", action="store_true")
    args = parser.parse_args(argv)
    if min(args.epochs, args.batch_size, args.patience, args.hidden_size) < 1:
        parser.error("epochs, batch-size, patience, and hidden-size must be positive")
    if args.learning_rate <= 0 or args.weight_decay < 0:
        parser.error("learning-rate must be positive and weight-decay cannot be negative")
    if not 0 <= args.dropout < 1:
        parser.error("dropout must be in [0, 1)")
    if not 0 < args.min_detection_rate <= 1:
        parser.error("min-detection-rate must be in (0, 1]")
    if not args.model_version.strip():
        parser.error("model-version cannot be blank")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    dataset_dir = args.dataset_dir.resolve()
    model_asset = args.hand_model.resolve()
    output_dir = args.output_dir.resolve()
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory does not exist: {dataset_dir}")
    expected_artifacts = [
        output_dir / name
        for name in (
            "gesture-classifier.pt",
            "gesture-labels.json",
            "gesture-model.json",
            "evaluation.json",
        )
    ]
    existing_artifacts = [path for path in expected_artifacts if path.exists()]
    if existing_artifacts and not args.overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing model artifacts; pass --overwrite explicitly: "
            + ", ".join(str(path) for path in existing_artifacts)
        )
    records, manifest_hash = image_manifest(dataset_dir, excluded_dirs=args.exclude_dir)
    class_names = sorted({label for label, _ in records})
    print(
        f"Found {len(records):,} images across {len(class_names)} class folders.",
        flush=True,
    )
    cache_path = output_dir / "static-landmark-cache.npz"
    if args.force_extract:
        cache_path.unlink(missing_ok=True)
        cache_path.with_suffix(".json").unlink(missing_ok=True)
    features, extracted_labels, failures = load_or_extract(
        records,
        manifest_hash,
        model_asset,
        cache_path,
    )
    validation_data = None
    validation_records: list[tuple[str, Path]] = []
    validation_features: np.ndarray | None = None
    validation_labels: list[str] = []
    validation_failures: dict[str, int] = {}
    validation_rates: dict[str, float] = {}
    if args.validation_dir is not None:
        validation_dir = args.validation_dir.resolve()
        if not validation_dir.is_dir():
            raise FileNotFoundError(f"Validation directory does not exist: {validation_dir}")
        validation_records, validation_manifest_hash = image_manifest(validation_dir)
        validation_classes = sorted({label for label, _ in validation_records})
        if validation_classes != class_names:
            raise ValueError("Training and validation directories must contain the same class folders")
        validation_cache_path = output_dir / "static-validation-landmark-cache.npz"
        validation_features, validation_labels, validation_failures = load_or_extract(
            validation_records,
            validation_manifest_hash,
            model_asset,
            validation_cache_path,
        )

    source_counts = Counter(label for label, _ in records)
    extracted_counts = Counter(extracted_labels)
    rates = {
        label: extracted_counts[label] / source_counts[label]
        for label in class_names
    }
    low_coverage = {
        label: rate
        for label, rate in rates.items()
        if rate < args.min_detection_rate
    }
    if low_coverage:
        details = ", ".join(f"{label}: {rate:.1%}" for label, rate in low_coverage.items())
        raise RuntimeError(
            "Landmark coverage is below the configured minimum; refusing to train "
            f"an incomplete class set ({details}). Review the extraction report or camera/model setup."
        )
    if validation_features is not None:
        validation_source_counts = Counter(label for label, _ in validation_records)
        validation_extracted_counts = Counter(validation_labels)
        validation_rates = {
            label: validation_extracted_counts[label] / validation_source_counts[label]
            for label in class_names
        }
        low_validation_coverage = {
            label: rate
            for label, rate in validation_rates.items()
            if rate < args.min_detection_rate
        }
        if low_validation_coverage:
            details = ", ".join(
                f"{label}: {rate:.1%}" for label, rate in low_validation_coverage.items()
            )
            raise RuntimeError(
                "Validation landmark coverage is below the configured minimum; refusing to "
                f"report incomplete validation metrics ({details})."
            )
        validation_data = (validation_features, validation_labels)

    model, metrics = train_model(
        features,
        extracted_labels,
        class_names,
        epochs=args.epochs,
        batch_size=args.batch_size,
        patience=args.patience,
        learning_rate=args.learning_rate,
        weight_decay=args.weight_decay,
        hidden_size=args.hidden_size,
        dropout=args.dropout,
        seed=args.seed,
        optimizer_name=args.optimizer,
        validation_data=validation_data,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    scripted_model = torch.jit.script(model.cpu().eval())
    sample = torch.zeros((1, FRAME_COUNT, HAND_COUNT, LANDMARK_COUNT, COORDINATE_COUNT))
    output_shape = tuple(scripted_model(sample).shape)
    if output_shape != (1, len(class_names)):
        raise RuntimeError(f"Exported model has unexpected output shape: {output_shape}")
    scripted_model.save(str(output_dir / "gesture-classifier.pt"))
    write_json(output_dir / "gesture-labels.json", class_names)
    write_json(
        output_dir / "gesture-model.json",
        {
            "schema_version": "1.0",
            "model_type": "static",
            "model_version": args.model_version,
            "input_schema_version": "1.0",
            "input_shape": [1, FRAME_COUNT, HAND_COUNT, LANDMARK_COUNT, COORDINATE_COUNT],
            "class_mapping": {label: index for index, label in enumerate(class_names)},
            "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD,
            "feature_config": {
                "pose_points": "wrist-centered and hand-scale-normalized XYZ",
                "temporal_aggregation": "mean across 30 frames",
            },
            "architecture": {
                "name": "MLP",
                "hidden_size": args.hidden_size,
                "dropout": args.dropout,
            },
        },
    )
    evaluation_split = str(metrics["evaluation_split"])
    metrics[evaluation_split]["model_size_bytes"] = (output_dir / "gesture-classifier.pt").stat().st_size
    metrics["limitations"] = (
        (
            "Metrics describe the supplied held-out validation split and do not establish "
            "signer-independent or real-world performance without appropriate signer/session metadata."
            if validation_data is not None
            else "Metrics describe the supplied held-out test split and do not establish "
            "signer-independent or real-world performance without appropriate signer/session metadata."
        )
    )
    metrics["dataset"] = {
        "image_count": len(records),
        "extracted_count": len(extracted_labels),
        "class_count": len(class_names),
        "class_counts": dict(sorted(extracted_counts.items())),
        "landmark_detection_rates": rates,
        "landmark_detection_failures": failures,
        "source_directory": str(dataset_dir),
        "validation_image_count": len(validation_records),
        "validation_extracted_count": len(validation_labels),
        "validation_class_counts": dict(sorted(Counter(validation_labels).items())),
        "validation_landmark_detection_rates": validation_rates,
        "validation_landmark_detection_failures": validation_failures,
        "validation_source_directory": (
            str(args.validation_dir.resolve()) if args.validation_dir is not None else None
        ),
        "provenance": (
            "User-provided local image folder. No dataset license or provenance file was present; "
            "confirm usage rights before distributing this model or using it commercially."
        ),
        "evaluation_limitations": (
            (
                "Separate held-out validation images; no signer/session metadata was available, "
                "so results do not establish signer-independent or real-world camera performance."
                if validation_data is not None
                else "Random stratified image-level split; no signer/session metadata was available, "
                "so results do not establish signer-independent or real-world camera performance."
            )
        ),
        "dynamic_sign_limitations": (
            "Each training item is a still image. This model classifies held static poses and "
            "does not learn motion-dependent sign transitions."
        ),
    }
    metrics["model"] = {
        "architecture": "static-pose-mlp-v1",
        "input_shape": [1, FRAME_COUNT, HAND_COUNT, LANDMARK_COUNT, COORDINATE_COUNT],
        "output_shape": [1, len(class_names)],
        "labels_path": "gesture-labels.json",
    }
    write_json(output_dir / "evaluation.json", metrics)
    print(
        f"Saved TorchScript model, labels, and evaluation report to {output_dir}",
        flush=True,
    )
    print(
        f"{evaluation_split.title()} accuracy: {metrics[evaluation_split]['accuracy']:.3f}; "
        f"macro F1: {metrics[evaluation_split]['macro_f1']:.3f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    random.seed(SEED)
    sys.exit(main())
