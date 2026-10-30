# Local Whisper setup

SignLingo uses the optional `openai-whisper` package in the backend process. No model weights are bundled. Install the optional requirements into the same virtual environment used to run FastAPI:

```powershell
backend\.venv\Scripts\python.exe -m pip install -r backend\speech-requirements.txt
```

In the root `.env`, opt in to a model and choose a device:

```dotenv
WHISPER_MODEL=tiny
WHISPER_DEVICE=cpu
WHISPER_DOWNLOAD_ROOT=ai-engine\models\whisper
SPEECH_MAX_AUDIO_BYTES=4000000
SPEECH_MAX_DURATION_SECONDS=60
```

Supported model names are `tiny`, `base`, and `small`; supported devices are `cpu`, `cuda`, and `auto`. The first transcription request lazily loads the model and downloads its weights to the configured cache if they are not already present. The backend must be able to reach the model download host on first use. Check available disk, RAM, CUDA/PyTorch compatibility, model terms, and expected latency before choosing a larger model or exposing the service to multiple users. The provider serializes inference within one application process; the API rate limit is not a distributed quota.

Leave `WHISPER_MODEL` unset to keep the endpoint disabled. Restart FastAPI after changing environment variables. A configured model with missing optional dependencies, unavailable CUDA, download errors, or inference errors produces a safe `503` response and a server-side error log. The application does not claim that a real model was downloaded or tested by its unit suite.

To run the backend checks without downloading a model:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_speech_audio.py backend\tests\test_speech_service.py backend\tests\test_whisper_provider.py backend\tests\test_speech_api.py -q
```

These tests use generated in-memory PCM fixtures and fake providers. For a real local smoke test, configure the model, start the backend, sign in through the frontend, record a short utterance in a supported browser, and review the returned transcript. Do not upload sensitive speech to an environment unless its privacy policy permits it.
