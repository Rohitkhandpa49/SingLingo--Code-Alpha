import { describe, expect, it, vi } from "vitest";
import {
  BrowserSpeechSynthesisProvider,
  TextToSpeechService,
  TTSNotSupportedError,
  type TTSProvider
} from "./tts-service";

describe("TextToSpeechService", () => {
  it("trims text, cancels previous playback, and delegates the selected language", async () => {
    const provider: TTSProvider = {
      speak: vi.fn().mockResolvedValue(undefined),
      cancel: vi.fn()
    };
    const service = new TextToSpeechService(provider);

    await service.speak("  recognized text  ", "hi", "Selected Hindi voice");

    expect(provider.cancel).toHaveBeenCalledOnce();
    expect(provider.speak).toHaveBeenCalledWith(
      "recognized text",
      "hi",
      "Selected Hindi voice"
    );
  });

  it("rejects empty text and reports provider failures", async () => {
    const provider: TTSProvider = {
      speak: vi.fn().mockRejectedValue(new Error("provider failed")),
      cancel: vi.fn()
    };
    const service = new TextToSpeechService(provider);

    await expect(service.speak("  ", "en")).rejects.toThrow("no text to speak");
    await expect(service.speak("message", "en")).rejects.toThrow("provider failed");
  });

  it("exposes a typed unsupported-browser error", () => {
    expect(new TTSNotSupportedError()).toBeInstanceOf(Error);
  });

  it("maps Hindi output to the browser Hindi voice language and resolves on playback end", async () => {
    const spokenUtterances: Array<{ lang: string; onend: (() => void) | null }> = [];
    const speak = vi.fn((utterance: { lang: string; onend: (() => void) | null }) => {
      spokenUtterances.push(utterance);
    });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: { speak, cancel: vi.fn(), getVoices: () => [] }
    });
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      configurable: true,
      value: class {
        lang = "";
        onend: (() => void) | null = null;
        onerror: (() => void) | null = null;

        constructor(readonly text: string) {}
      }
    });
    const playback = new BrowserSpeechSynthesisProvider().speak("नमस्ते", "hi");

    expect(spokenUtterances[0]?.lang).toBe("hi-IN");
    spokenUtterances[0]?.onend?.();
    await expect(playback).resolves.toBeUndefined();
  });
});
