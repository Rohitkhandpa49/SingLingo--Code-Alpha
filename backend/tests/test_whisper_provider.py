from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.services.speech.whisper_provider import (
    SpeechProviderUnavailable,
    WhisperProvider,
)


def test_missing_model_configuration_is_reported_without_importing_whisper(
    tmp_path: Path,
) -> None:
    provider = WhisperProvider(
        model_name=None,
        device="cpu",
        download_root=tmp_path,
    )

    with pytest.raises(SpeechProviderUnavailable, match="not configured"):
        provider.transcribe(np.ones(100, dtype=np.float32), language="en")


def test_model_load_is_lazy_and_reused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, object]] = []

    class Model:
        def transcribe(
            self,
            audio: np.ndarray,
            *,
            language: str | None,
            fp16: bool,
            verbose: bool,
        ) -> dict[str, object]:
            calls.append(("transcribe", language))
            return {"text": "hello", "language": "en"}

    def fake_import(name: str) -> object:
        if name == "whisper":
            return SimpleNamespace(
                load_model=lambda model_name, **kwargs: (
                    calls.append(("load", model_name)),
                    Model(),
                )[1]
            )
        if name == "torch":
            return SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("app.services.speech.whisper_provider.importlib.import_module", fake_import)
    provider = WhisperProvider(
        model_name="tiny",
        device="auto",
        download_root=tmp_path / "whisper",
    )
    audio = np.ones(100, dtype=np.float32)

    assert provider.transcribe(audio, language="en")["text"] == "hello"
    assert provider.transcribe(audio, language=None)["language"] == "en"

    assert calls == [("load", "tiny"), ("transcribe", "en"), ("transcribe", None)]
    assert (tmp_path / "whisper").is_dir()


def test_missing_optional_dependencies_are_reported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fake_import(name: str) -> object:
        raise ModuleNotFoundError(name)

    monkeypatch.setattr("app.services.speech.whisper_provider.importlib.import_module", fake_import)
    provider = WhisperProvider(
        model_name="tiny",
        device="cpu",
        download_root=tmp_path,
    )

    with pytest.raises(SpeechProviderUnavailable, match="optional speech requirements"):
        provider.transcribe(np.ones(100, dtype=np.float32), language=None)
