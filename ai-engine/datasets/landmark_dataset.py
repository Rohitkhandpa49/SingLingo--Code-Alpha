from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FRAME_COUNT = 30
HAND_COUNT = 2
LANDMARK_COUNT = 21
COORDINATE_COUNT = 3


@dataclass(frozen=True)
class DatasetSplit:
    features: np.ndarray
    labels: np.ndarray
    class_ids: np.ndarray
    sample_ids: tuple[str, ...]
    signer_ids: tuple[str | None, ...]
    dataset_version: str


def _read_split(path: Path, *, include_wrist: bool) -> DatasetSplit:
    if not path.is_file():
        raise FileNotFoundError(f"Dataset split file not found: {path}")

    features: list[np.ndarray] = []
    labels: list[str] = []
    class_ids: list[int] = []
    sample_ids: list[str] = []
    signer_ids: list[str | None] = []
    versions: set[str] = set()
    seen_sample_ids: set[str] = set()
    expected_points = LANDMARK_COUNT + int(include_wrist)

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            sample = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON") from error
        if not isinstance(sample, dict):
            raise ValueError(f"{path}:{line_number}: each sample must be an object")

        sample_id = sample.get("sample_id")
        label = sample.get("label")
        version = sample.get("dataset_version")
        schema_version = sample.get("schema_version")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError(f"{path}:{line_number}: sample_id must be a non-empty string")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"{path}:{line_number}: label must be a non-empty string")
        if not isinstance(version, str) or not version.strip():
            raise ValueError(f"{path}:{line_number}: dataset_version must be a non-empty string")
        if schema_version != "1.0":
            raise ValueError(f"{path}:{line_number}: schema_version must be '1.0'")
        if sample_id in seen_sample_ids:
            raise ValueError(f"{path}:{line_number}: duplicate sample_id {sample_id!r}")
        seen_sample_ids.add(sample_id)

        frames = sample.get("frames")
        if not isinstance(frames, list) or len(frames) != FRAME_COUNT:
            raise ValueError(f"{path}:{line_number}: frames must contain exactly {FRAME_COUNT} entries")

        values = np.zeros(
            (FRAME_COUNT, HAND_COUNT, expected_points, COORDINATE_COUNT),
            dtype=np.float32,
        )
        for frame_index, frame in enumerate(frames):
            if not isinstance(frame, dict) or not isinstance(frame.get("hands"), list):
                raise ValueError(f"{path}:{line_number}: each frame must contain a hands list")
            if len(frame["hands"]) > HAND_COUNT:
                raise ValueError(f"{path}:{line_number}: at most two hands are supported")
            occupied: set[int] = set()
            for hand in frame["hands"]:
                if not isinstance(hand, dict) or hand.get("handedness") not in {"Left", "Right"}:
                    raise ValueError(f"{path}:{line_number}: invalid hand handedness")
                slot = 0 if hand["handedness"] == "Left" else 1
                if slot in occupied:
                    raise ValueError(f"{path}:{line_number}: duplicate hand handedness")
                occupied.add(slot)
                try:
                    points = np.asarray(hand.get("points"), dtype=np.float32)
                except (TypeError, ValueError, OverflowError) as error:
                    raise ValueError(f"{path}:{line_number}: malformed landmark values") from error
                if points.shape != (LANDMARK_COUNT, COORDINATE_COUNT):
                    raise ValueError(f"{path}:{line_number}: each hand needs 21 three-dimensional points")
                if not np.isfinite(points).all() or np.any(np.abs(points) > 1):
                    raise ValueError(f"{path}:{line_number}: points must be finite and in [-1, 1]")
                if not np.allclose(points[0], 0, atol=1e-4) or not np.isclose(
                    np.linalg.norm(points, axis=1).max(),
                    1,
                    atol=1e-3,
                ):
                    raise ValueError(
                        f"{path}:{line_number}: points must be wrist-centered and hand-scale-normalized"
                    )
                values[frame_index, slot, :LANDMARK_COUNT] = points
                if include_wrist:
                    try:
                        wrist = np.asarray(hand.get("wrist"), dtype=np.float32)
                    except (TypeError, ValueError, OverflowError) as error:
                        raise ValueError(f"{path}:{line_number}: malformed wrist coordinates") from error
                    if wrist.shape != (COORDINATE_COUNT,) or not np.isfinite(wrist).all():
                        raise ValueError(f"{path}:{line_number}: dynamic samples require a finite wrist point")
                    if np.any(np.abs(wrist) > 1):
                        raise ValueError(f"{path}:{line_number}: wrist coordinates must be in [-1, 1]")
                    values[frame_index, slot, LANDMARK_COUNT] = wrist

        class_id = sample.get("class_id")
        if not isinstance(class_id, int) or isinstance(class_id, bool) or class_id < 0:
            raise ValueError(f"{path}:{line_number}: class_id must be a non-negative integer")
        signer_id = sample.get("signer_id")
        if signer_id is not None and (not isinstance(signer_id, str) or not signer_id.strip()):
            raise ValueError(f"{path}:{line_number}: signer_id must be a non-empty string or null")

        values.setflags(write=False)
        features.append(values)
        labels.append(label)
        class_ids.append(class_id)
        sample_ids.append(sample_id)
        signer_ids.append(signer_id)
        versions.add(version)

    if not features:
        raise ValueError(f"Dataset split is empty: {path}")
    if len(versions) != 1:
        raise ValueError(f"{path}: all samples in a split must use the same dataset_version")

    return DatasetSplit(
        features=np.stack(features),
        labels=np.asarray(labels, dtype=np.str_),
        class_ids=np.asarray(class_ids, dtype=np.int64),
        sample_ids=tuple(sample_ids),
        signer_ids=tuple(signer_ids),
        dataset_version=next(iter(versions)),
    )


def load_dataset_splits(
    split_dir: Path,
    *,
    include_wrist: bool,
) -> tuple[dict[str, DatasetSplit], list[str]]:
    splits = {
        name: _read_split(split_dir / f"{name}.jsonl", include_wrist=include_wrist)
        for name in ("train", "validation", "test")
    }
    dataset_versions = {split.dataset_version for split in splits.values()}
    if len(dataset_versions) != 1:
        raise ValueError("All dataset splits must use the same dataset_version")
    all_ids: set[str] = set()
    signers_by_split: dict[str, set[str]] = {}
    for name, split in splits.items():
        overlap = all_ids.intersection(split.sample_ids)
        if overlap:
            raise ValueError(f"sample_id leakage across dataset splits: {sorted(overlap)}")
        all_ids.update(split.sample_ids)
        signers_by_split[name] = {signer for signer in split.signer_ids if signer is not None}

    names = tuple(splits)
    for index, name in enumerate(names):
        for other in names[index + 1 :]:
            overlap = signers_by_split[name].intersection(signers_by_split[other])
            if overlap:
                raise ValueError(
                    f"signer leakage between {name} and {other} splits: {sorted(overlap)}"
                )

    training = splits["train"]
    mapping: dict[str, int] = {}
    for label, class_id in zip(training.labels, training.class_ids, strict=True):
        known_id = mapping.setdefault(str(label), int(class_id))
        if known_id != int(class_id):
            raise ValueError(f"Training label {label!r} maps to multiple class IDs")
    if len(mapping) < 2:
        raise ValueError("The training split must contain at least two gesture classes")
    if sorted(mapping.values()) != list(range(len(mapping))):
        raise ValueError("Training class IDs must be contiguous and start at zero")
    classes = [label for label, _ in sorted(mapping.items(), key=lambda entry: entry[1])]
    for name, split in splits.items():
        unknown = set(split.labels.tolist()).difference(mapping)
        if unknown:
            raise ValueError(f"{name} split contains labels absent from training: {sorted(unknown)}")
        for sample_label, class_id in zip(split.labels, split.class_ids, strict=True):
            if mapping[str(sample_label)] != int(class_id):
                raise ValueError(f"{name} split has an inconsistent class_id for {sample_label!r}")

    return splits, classes
