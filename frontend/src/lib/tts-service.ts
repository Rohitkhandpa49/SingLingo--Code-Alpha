export type SpeechLanguage = "en" | "hi";

export class TTSNotSupportedError extends Error {
  constructor() {
    super("Browser speech synthesis is not supported.");
    this.name = "TTSNotSupportedError";
  }
}

export interface TTSProvider {
  speak(text: string, language: SpeechLanguage, voiceName?: string): Promise<void>;
  cancel(): void;
}

export class BrowserSpeechSynthesisProvider implements TTSProvider {
  speak(text: string, language: SpeechLanguage, voiceName?: string): Promise<void> {
    if (
      typeof window === "undefined" ||
      !("speechSynthesis" in window) ||
      typeof window.speechSynthesis?.speak !== "function" ||
      !("SpeechSynthesisUtterance" in window)
    ) {
      return Promise.reject(new TTSNotSupportedError());
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = language === "hi" ? "hi-IN" : "en-IN";
    if (voiceName) {
      utterance.voice =
        window.speechSynthesis.getVoices().find((voice) => voice.name === voiceName) ?? null;
    }
    return new Promise<void>((resolve, reject) => {
      utterance.onend = () => resolve();
      utterance.onerror = () => reject(new Error("Speech synthesis could not play the text."));
      window.speechSynthesis.speak(utterance);
    });
  }

  cancel(): void {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }
}

export class TextToSpeechService {
  constructor(private readonly provider: TTSProvider = new BrowserSpeechSynthesisProvider()) {}

  speak(text: string, language: SpeechLanguage, voiceName?: string): Promise<void> {
    const content = text.trim();
    if (!content) {
      return Promise.reject(new Error("There is no text to speak."));
    }
    this.provider.cancel();
    return this.provider.speak(content, language, voiceName);
  }

  cancel(): void {
    this.provider.cancel();
  }
}
