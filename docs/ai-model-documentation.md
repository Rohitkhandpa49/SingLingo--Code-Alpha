# AI model status

The browser uses MediaPipe Tasks Vision to detect hand landmarks locally. The optional backend classifier consumes landmark sequences and remains `model_unavailable` unless a TorchScript model and ordered JSON label list are configured.

A local user-supplied image folder was found with 35 class directories (`1`–`9`, `A`–`Z`) and 1,200 JPEGs per class. These are still images, not continuous signing videos. The folder included no dataset provenance, license, signer IDs, or capture-session metadata. Training therefore produces an **experimental static-pose baseline**, not a validated ISL recognition model. Confirm usage rights before commercial use or sharing the model.

The training command extracts normalized MediaPipe landmarks locally, requires at least 80% detection coverage for every class, uses a fixed stratified image-level train/validation/test split, and writes per-class metrics and a confusion matrix to `evaluation.json`. Since signer/session metadata is unavailable, the held-out results cannot establish signer-independent or in-the-wild accuracy. Single still images cannot train motion-dependent signs, phrase translation, or complete ISL.

The TorchScript input contract remains `[batch, 30, 2, 21, 3]`; the static-pose model averages the 30-frame window and returns logits matching the ordered label list. The backend's configured confidence threshold controls whether a prediction is returned as `classified` or `unknown`. Treat confidence and test metrics as dataset-specific estimates, not calibrated real-world performance. No sign-language animation or phrase translation is included.
