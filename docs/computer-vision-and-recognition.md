# Browser vision and gesture models

## Browser-side camera pipeline

The sign-to-speech screen uses `@mediapipe/tasks-vision` Hand Landmarker in `VIDEO` mode. It asks for camera permission only after the user starts tracking, samples at 10 Hz, detects up to two hands, and runs all frame inference in the browser. The video stream is never sent to the backend. The user can choose an available camera, pause/stop tracking, independently stop recognition, and toggle the landmark overlay.

Set the public MediaPipe asset URLs in `frontend/.env.local` (copy the values from `frontend/.env.example`). Keep the WASM bundle version aligned with the installed `@mediapipe/tasks-vision` dependency. The model URL points to the official MediaPipe Hand Landmarker task asset. The browser requires a secure context for camera access, except for loopback development.

The versioned `1.0` landmark contract retains the Phase 5 message shape and includes optional `session_id`, source frame dimensions, detected-hand count, detection confidence, and camera-space wrist coordinates. Each hand still contains exactly 21 wrist-centered, hand-scale-normalized points. Wrist positions remain separate so temporal models can observe inter-frame translation without losing the static pose normalization. Dynamic models require wrist coordinates for every detected hand. Missing hands are represented by an empty `hands` list in that frame; no synthetic points are generated. Numeric fields are validated in the browser and backend.

The sequence builder keeps a fixed 30-frame sliding window and emits overlapping windows at a stride of 10 frames. This is a compatibility default, not a universal optimum; tune it only using representative training data and measured latency. Long frame gaps reset the window, and memory is bounded.

## Dataset format and privacy

No training dataset is bundled in `ai-engine/datasets`. Do not download or fabricate samples for model training. Use a consented, licensed dataset and keep it outside version control. The dynamic training pipeline consumes three explicit files: `train.jsonl`, `validation.jsonl`, and `test.jsonl`. Each line is a sample object with:

The following JSON is schematic and abbreviates both the frame list and landmark list; it is not a valid complete sample as written.

```json
{
  "sample_id": "opaque-unique-id",
  "label": "example-label",
  "class_id": 0,
  "dataset_version": "v1",
  "schema_version": "1.0",
  "signer_id": "optional-consented-pseudonymous-id",
  "frames": [
    {
      "hands": [{
        "handedness": "Right",
        "points": [[0.0, 0.0, 0.0]],
        "wrist": [0.5, 0.5, 0.0]
      }]
    }
  ]
}
```

In actual samples, `frames` must contain exactly 30 entries and each present hand must have 21 finite points. Dynamic training requires a finite camera-space wrist XYZ value per present hand. `class_id` values in the training split must be contiguous from zero and consistent with each label; the same mapping is validated in validation and test. Sample IDs cannot occur across splits. If signer IDs are supplied, a signer cannot occur in more than one split. Store only pseudonymous signer metadata when there is informed consent and a clear need.

The static-pose workflow is separate: it accepts local class directories containing JPEG/PNG images, extracts landmarks with the MediaPipe task model, and uses an image-level stratified split. It cannot provide signer-independent evaluation without signer/session annotations. It does not train a dynamic sign model.

## Train and evaluate

Install `ai-engine/requirements.txt` in the isolated AI environment, and prepare the local dataset in the format above. The existing static workflow is:

```powershell
ai-engine\.venv\Scripts\python.exe ai-engine\training\train_static_landmark_classifier.py `
  --dataset-dir "C:\path\to\static-image-classes" `
  --hand-model ai-engine\models\hand_landmarker.task
```

The dynamic LSTM baseline is:

```powershell
ai-engine\.venv\Scripts\python.exe ai-engine\training\train_dynamic_landmark_classifier.py `
  --split-dir "C:\path\to\dynamic-splits" `
  --output-dir ai-engine\models\checkpoints\dynamic `
  --model-version "dynamic-lstm-v1-your-dataset-version"
```

Both training flows support configurable training parameters and CPU execution, use CUDA when PyTorch reports it available, preserve the best validation-loss checkpoint, and refuse to overwrite existing model artifacts unless `--overwrite` is explicitly supplied. Evaluation reports are calculated from the held-out test split and include classification metrics, confusion matrix, class distribution, inference time, and checkpoint size. These results do not imply real-world or signer-independent accuracy unless the dataset split supports that conclusion.

Training writes `gesture-classifier.pt`, `gesture-labels.json`, `gesture-model.json`, and `evaluation.json`. The model metadata records model type/version, input schema, feature configuration, labels, and architecture. The dynamic model is a small fixed-length LSTM: this is a simple temporal baseline with lower complexity than attention models, but requires fixed 30-frame windows and can miss longer context.

To load an artifact, set backend `GESTURE_MODEL_PATH` and `GESTURE_LABELS_PATH` to the checkpoint and labels file in the same directory; install a compatible PyTorch build in the backend environment and restart the API. A colocated `gesture-model.json` is checked for model type and input compatibility. Legacy TorchScript static checkpoints without metadata continue to use the static input format. The backend applies its configured confidence threshold and returns `unknown` below it. With no configured model, inference explicitly returns `model_unavailable`.

## Testing

Unit tests mock camera, browser, and training inputs; they do not prove physical webcam behavior or model quality. For a real webcam check, run the frontend and backend on loopback or HTTPS, sign in, open `/translator/sign-to-speech`, start tracking, grant browser permission, verify the local preview and landmarks, then stop tracking and confirm the camera indicator turns off. The gesture output remains unavailable/unknown without trained artifacts. No real camera, Atlas, or production model evaluation is claimed by this guide.
