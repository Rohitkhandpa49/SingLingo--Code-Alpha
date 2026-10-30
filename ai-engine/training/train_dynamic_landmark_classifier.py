from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from datasets.landmark_dataset import load_dataset_splits
from evaluation.metrics import classification_metrics, measure_inference_seconds, model_file_size_bytes
from recognition.dynamic_classifier import DynamicLandmarkClassifier

SEED = 42
SEQUENCE_LENGTH = 30
HAND_COUNT = 2
LANDMARKS_WITH_WRIST = 22
COORDINATES = 3
CONFIDENCE_THRESHOLD = 0.75
OUTPUT_FILES = (
    "gesture-classifier.pt",
    "gesture-labels.json",
    "gesture-model.json",
    "evaluation.json",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train and evaluate a dynamic landmark LSTM using explicit dataset splits."
    )
    parser.add_argument("--split-dir", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models" / "checkpoints" / "dynamic",
    )
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--patience", type=int, default=7)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--optimizer", choices=("Adam", "AdamW"), default="AdamW")
    parser.add_argument("--hidden-size", type=int, default=128)
    parser.add_argument("--num-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--model-version", type=str)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if min(args.epochs, args.batch_size, args.patience, args.hidden_size, args.num_layers) < 1:
        parser.error("epochs, batch-size, patience, hidden-size, and num-layers must be positive")
    if args.learning_rate <= 0 or args.weight_decay < 0:
        parser.error("learning-rate must be positive and weight-decay cannot be negative")
    if not 0 <= args.dropout < 1:
        parser.error("dropout must be in [0, 1)")
    if args.model_version is not None and not args.model_version.strip():
        parser.error("model-version cannot be blank")
    return args


def _encode_labels(values: np.ndarray, class_to_id: dict[str, int]) -> np.ndarray:
    return np.asarray([class_to_id[str(value)] for value in values], dtype=np.int64)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def train(args: argparse.Namespace) -> dict[str, object]:
    output_dir = args.output_dir.resolve()
    existing = [output_dir / name for name in OUTPUT_FILES if (output_dir / name).exists()]
    if existing and not args.overwrite:
        raise FileExistsError(
            "Refusing to overwrite existing model artifacts; pass --overwrite explicitly: "
            + ", ".join(str(path) for path in existing)
        )

    splits, classes = load_dataset_splits(args.split_dir.resolve(), include_wrist=True)
    class_to_id = {label: index for index, label in enumerate(classes)}
    for label, count in zip(
        *np.unique(splits["train"].labels, return_counts=True),
        strict=True,
    ):
        if count < 2:
            raise ValueError(f"Training class {label!r} needs at least two samples")

    train_split = splits["train"]
    validation_split = splits["validation"]
    test_split = splits["test"]
    seed = int(args.seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = DynamicLandmarkClassifier(
        len(classes),
        hidden_size=args.hidden_size,
        num_layers=args.num_layers,
        dropout=args.dropout,
    ).to(device)
    optimizer_type = {
        "Adam": torch.optim.Adam,
        "AdamW": torch.optim.AdamW,
    }[args.optimizer]
    optimizer = optimizer_type(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    loss_function = nn.CrossEntropyLoss()
    training_data = TensorDataset(
        torch.from_numpy(train_split.features),
        torch.from_numpy(_encode_labels(train_split.labels, class_to_id)),
    )
    loader = DataLoader(
        training_data,
        batch_size=args.batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    validation_features = torch.from_numpy(validation_split.features).to(device)
    validation_targets = torch.from_numpy(_encode_labels(validation_split.labels, class_to_id)).to(device)

    best_loss = float("inf")
    best_state: dict[str, torch.Tensor] | None = None
    best_epoch = 0
    epochs_without_improvement = 0
    for epoch in range(1, args.epochs + 1):
        model.train()
        for batch_features, batch_targets in loader:
            optimizer.zero_grad(set_to_none=True)
            logits = model(batch_features.to(device))
            loss = loss_function(logits, batch_targets.to(device))
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.inference_mode():
            validation_logits = model(validation_features)
            validation_loss = float(loss_function(validation_logits, validation_targets).item())
        print(
            f"Epoch {epoch:02d}/{args.epochs}: validation loss {validation_loss:.4f}",
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
            if epochs_without_improvement >= args.patience:
                break

    if best_state is None:
        raise RuntimeError("Training did not produce a validated model checkpoint")
    model.load_state_dict(best_state)
    model.to(device).eval()
    test_features = torch.from_numpy(test_split.features).to(device)
    test_targets = _encode_labels(test_split.labels, class_to_id)
    with torch.inference_mode():
        probabilities = torch.softmax(model(test_features), dim=1).cpu().numpy()
    predictions = probabilities.argmax(axis=1)
    confidence = probabilities.max(axis=1)
    accepted = confidence >= CONFIDENCE_THRESHOLD
    scripted_model = torch.jit.script(model.cpu().eval())
    sample = torch.zeros((1, SEQUENCE_LENGTH, HAND_COUNT, LANDMARKS_WITH_WRIST, COORDINATES))
    expected_output = tuple(scripted_model(sample).shape)
    if expected_output != (1, len(classes)):
        raise RuntimeError(f"Exported model has unexpected output shape: {expected_output}")

    output_dir.mkdir(parents=True, exist_ok=True)
    model_path = output_dir / OUTPUT_FILES[0]
    scripted_model.save(str(model_path))
    _write_json(output_dir / OUTPUT_FILES[1], classes)
    model_metadata = {
        "schema_version": "1.0",
        "model_type": "dynamic",
        "model_version": args.model_version
        or f"dynamic-lstm-v1-{train_split.dataset_version}",
        "input_schema_version": "1.0",
        "input_shape": [1, SEQUENCE_LENGTH, HAND_COUNT, LANDMARKS_WITH_WRIST, COORDINATES],
        "class_mapping": {label: class_to_id[label] for label in classes},
        "dataset_version": train_split.dataset_version,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "feature_config": {
            "pose_points": "wrist-centered and hand-scale-normalized XYZ",
            "wrist_point_index": 21,
            "wrist_coordinates": "MediaPipe image-normalized XYZ, preserving inter-frame motion",
        },
        "architecture": {
            "name": "LSTM",
            "hidden_size": args.hidden_size,
            "num_layers": args.num_layers,
            "dropout": args.dropout,
        },
    }
    _write_json(output_dir / OUTPUT_FILES[2], model_metadata)
    test_metrics = classification_metrics(test_targets, predictions, classes)
    test_metrics["confidence_threshold"] = CONFIDENCE_THRESHOLD
    test_metrics["threshold_coverage"] = float(accepted.mean())
    test_metrics["threshold_selective_accuracy"] = (
        float((predictions[accepted] == test_targets[accepted]).mean())
        if accepted.any()
        else None
    )
    test_metrics["class_distribution"] = {
        label: int(np.count_nonzero(test_split.labels == label)) for label in classes
    }
    test_metrics["model_size_bytes"] = model_file_size_bytes(model_path)

    def run_inference(values: np.ndarray) -> torch.Tensor:
        with torch.inference_mode():
            return scripted_model(torch.from_numpy(values).to(dtype=torch.float32))

    test_metrics["inference_seconds_per_sequence"] = measure_inference_seconds(
        run_inference,
        test_split.features[: min(10, len(test_split.features))],
    )
    report = {
        "evaluation_split": "test",
        "test": test_metrics,
        "validation_loss_at_best_epoch": best_loss,
        "best_epoch": best_epoch,
        "device": str(device),
        "seed": seed,
        "dataset_version": train_split.dataset_version,
        "model_version": model_metadata["model_version"],
        "split_counts": {name: len(split.labels) for name, split in splits.items()},
        "training_config": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "patience": args.patience,
            "learning_rate": args.learning_rate,
            "weight_decay": args.weight_decay,
            "optimizer": args.optimizer,
            "hidden_size": args.hidden_size,
            "num_layers": args.num_layers,
            "dropout": args.dropout,
        },
        "limitations": (
            "Metrics describe only the supplied held-out test split. They do not establish "
            "real-world or signer-independent performance unless the supplied split metadata does so."
        ),
    }
    _write_json(output_dir / OUTPUT_FILES[3], report)
    print(f"Saved dynamic model artifacts to {output_dir}", flush=True)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    train(parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
