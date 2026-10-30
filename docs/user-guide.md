# User guide

## Sign to speech: camera and hand landmarks

1. Open the Sign to speech page and select **Start hand tracking**.
2. Grant camera permission when the browser prompts you. MediaPipe detects up to two hands locally and displays landmark overlays.
3. Sign in to send 30-frame normalized landmark sequences to the backend over the authenticated WebSocket. Raw camera frames remain in the browser and are never uploaded or persisted.
4. Select **Pause tracking** to pause detection or **Stop camera** to stop the camera, close the WebSocket, and release the media tracks.

On first use, the browser downloads the MediaPipe WebAssembly runtime and hand-landmarker model from the configured public asset hosts. Those downloads do not contain camera frames.

The classifier returns `model_unavailable` until a validated PyTorch model and its label list are configured. Even when a model is configured, low-confidence output is reported as unknown. Speech output speaks only successful verified vocabulary interpretations; complete ISL translation is not available.

## Speech to sign: transcript and verified vocabulary

1. Open **Speech to sign**, choose Hindi, English, or script detection, and select **Record speech** or type a message.
2. Grant microphone permission if prompted, stop within 60 seconds, and review the returned transcript. Choose **Use transcript** to put it in the editable message box.
3. Select **Prepare sign sequence**. Only exact verified vocabulary/phrase matches are returned. Unsupported text is shown, and multiple independent signs are not presented as a grammatically complete sentence.
4. The page shows sign names and supports a 3D preview only when every sign has a registered local GLB asset and named clip. No signing assets are included, so playback is currently unavailable.
5. Use **Save to translation history** only if you want to retain the source text and ordered sign names. Nothing is saved automatically.

Audio recordings are temporarily uploaded to the authenticated backend for optional local Whisper transcription and are not persisted by the application. Whisper must be installed/configured separately. Browser TTS and model/voice availability depend on the device. See [speech-to-sign](speech-to-sign.md) and [speech setup](whisper-setup.md).

Account, profile, accessibility settings, password recovery (when SMTP is configured), and translation-history workflows are available in the frontend.
