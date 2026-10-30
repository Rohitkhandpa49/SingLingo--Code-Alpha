import importlib
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from numpy.typing import NDArray
import numpy as np

logger = logging.getLogger(__name__)


class SpeechProviderError(RuntimeError):
    pass


class SpeechProviderUnavailable(SpeechProviderError):
    pass


class WhisperProvider:
    def __init__(
        self,
        *,
        model_name: str | None,
        device: str,
        download_root: Path,
    ) -> None:
        self.model_name = model_name
        self._device_setting = device
        self._download_root = download_root
        self._model: Any = None
        self._device: str | None = None
        self._lock = Lock()

    def transcribe(
        self,
        audio: NDArray[np.float32],
        *,
        language: str | None,
    ) -> dict[str, Any]:
        if self.model_name is None:
            raise SpeechProviderUnavailable("Whisper model selection is not configured")
        with self._lock:
            model = self._get_model()
            try:
                result = model.transcribe(
                    audio,
                    language=language,
                    fp16=self._device == "cuda",
                    verbose=False,
                )
            except Exception as error:
                logger.error(
                    "Whisper inference failed",
                    extra={"error_type": error.__class__.__name__},
                )
                raise SpeechProviderError("Whisper inference failed") from error
        if not isinstance(result, dict):
            raise SpeechProviderError("Whisper returned an invalid response")
        return result

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            whisper = importlib.import_module("whisper")
            torch = importlib.import_module("torch")
        except ModuleNotFoundError as error:
            raise SpeechProviderUnavailable(
                "Install the optional speech requirements to enable Whisper"
            ) from error

        if self._device_setting == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        elif self._device_setting == "cuda":
            if not torch.cuda.is_available():
                raise SpeechProviderUnavailable("CUDA was requested but is not available")
            device = "cuda"
        else:
            device = "cpu"
        try:
            self._download_root.mkdir(parents=True, exist_ok=True)
            self._model = whisper.load_model(
                self.model_name,
                device=device,
                download_root=str(self._download_root),
            )
        except Exception as error:
            logger.error(
                "Whisper model initialization failed",
                extra={"error_type": error.__class__.__name__},
            )
            raise SpeechProviderUnavailable("Whisper model could not be initialized") from error
        self._device = device
        return self._model
