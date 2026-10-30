# AI engine

The AI engine provides static-pose and dynamic-landmark training workflows, a fixed-length LSTM baseline, model metadata/registry checks, and evaluation helpers. There is no validated training dataset or trained recognition model included in the repository. Without a configured compatible checkpoint, the backend reports `model_unavailable`.

## Landmark formats

The static TorchScript classifier accepts `[batch, 30, 2, 21, 3]` float landmarks. The dynamic LSTM accepts `[batch, 30, 2, 22, 3]`; each hand slot has the same 21 wrist-centered/scale-normalized landmarks plus one camera-space wrist XYZ point to preserve translation across frames. Empty hand slots are zero-filled. Both models return logits shaped `[batch, class_count]`.

The model contract is versioned as `1.0`. Training outputs an ordered `gesture-labels.json` and a `gesture-model.json` descriptor containing model type/version, input shape, feature configuration, architecture, confidence threshold, and label mapping. The backend validates colocated metadata and preserves legacy static TorchScript support when no descriptor exists.

## Install

From the repository root in PowerShell:

```powershell
python -m venv ai-engine\.venv
ai-engine\.venv\Scripts\python.exe -m pip install -r ai-engine\requirements.txt
```

The dependency set includes large machine-learning packages. Install it only when training or evaluating models.

## Static-pose training

Supply a local directory with one class directory per gesture and JPEG/PNG still images. The command processes images locally, extracts landmarks, and uses an image-level stratified train/validation/test split:

```powershell
New-Item -ItemType Directory -Force ai-engine\models | Out-Null
Invoke-WebRequest `
  -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" `
  -OutFile ai-engine\models\hand_landmarker.task
ai-engine\.venv\Scripts\python.exe ai-engine\training\train_static_landmark_classifier.py `
  --dataset-dir "C:\path\to\static-image-classes" `
  --hand-model ai-engine\models\hand_landmarker.task
```

The still-image model only classifies held poses. It cannot learn dynamic signs or establish signer-independent generalization unless the data and split include appropriate signer/session metadata. The extraction cache is local and can be rebuilt with `--force-extract`.

## Dynamic sequence training

Provide `train.jsonl`, `validation.jsonl`, and `test.jsonl` files with 30-frame samples, labels, contiguous class IDs, dataset version, optional consented pseudonymous signer ID, and hand points plus wrist coordinates. The loader rejects malformed points, missing dynamic wrist coordinates, sample leakage, inconsistent labels, and signer overlap across splits.

```powershell
ai-engine\.venv\Scripts\python.exe ai-engine\training\train_dynamic_landmark_classifier.py `
  --split-dir "C:\path\to\dynamic-splits" `
  --output-dir ai-engine\models\checkpoints\dynamic `
  --epochs 50 `
  --batch-size 64 `
  --hidden-size 128
```

Both training commands select CUDA when PyTorch reports it available and otherwise use CPU. They save the best validation-loss model and evaluate only on the explicit held-out test split. Existing artifacts are not overwritten unless `--overwrite` is passed. Reports include accuracy, precision, recall, F1, per-class results, confusion matrix, test class distribution, inference time, and model size. No performance number should be generalized beyond the measured split.

## Configure backend inference

Set `GESTURE_MODEL_PATH` and `GESTURE_LABELS_PATH` to the generated checkpoint and label file. Install a compatible PyTorch build in the backend environment, keep `gesture-model.json` beside both files, and restart FastAPI. `GESTURE_CONFIDENCE_THRESHOLD` controls the minimum accepted confidence; lower scores return `unknown`. A classifier is not a full ISL translator.

See [computer vision and recognition](../docs/computer-vision-and-recognition.md) for the dataset schema, privacy guidance, and webcam test procedure. Model checkpoints, generated data, caches, and local media are excluded from Git. Do not commit private datasets or unverified model artifacts.
