import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SignToSpeechExperience } from "./sign-to-speech-experience";

const speak = vi.fn();
const cancel = vi.fn();
let spokenText = "";
let spokenLanguage = "";

vi.mock("@/features/sign-recognition/sign-camera", () => ({
  SignCamera: ({
    onRecognition
  }: {
    onRecognition: (result: {
      type: "gesture_result";
      sequence_id: string;
      status: "classified";
      label: string;
      confidence: number;
      translation: {
        type: "isl_translation";
        translation_id: string;
        status: "success";
        session_id: string;
        sequence_id: string;
        recognized_signs: [];
        interpreted_text: string;
        language: "en" | "hi";
        confidence: number;
        translation_level: "single_sign";
        unsupported_segments: [];
        model_version: string;
        vocabulary_version: string;
        timestamp: string;
      };
    }) => void;
  }) => (
    <button
      onClick={() =>
        onRecognition({
          type: "gesture_result",
          sequence_id: "sequence-1",
          status: "classified",
          label: "A",
          confidence: 0.92,
          translation: {
            type: "isl_translation",
            translation_id: "translation-1",
            status: "success",
            session_id: "session-1",
            sequence_id: "sequence-1",
            recognized_signs: [],
            interpreted_text: "fixture translation",
            language: "hi",
            confidence: 0.92,
            translation_level: "single_sign",
            unsupported_segments: [],
            model_version: "fixture-model",
            vocabulary_version: "fixture-vocabulary",
            timestamp: "2026-10-30T00:00:00Z"
          }
        })
      }
      type="button"
    >
      Simulate recognition
    </button>
  )
}));

class MockSpeechUtterance {
  onerror: (() => void) | null = null;

  constructor(readonly text: string) {
    spokenText = text;
  }

  get lang() {
    return spokenLanguage;
  }

  set lang(value: string) {
    spokenLanguage = value;
  }
}

describe("SignToSpeechExperience", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("speaks only verified interpreted text in the translation language", () => {
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: { cancel, speak }
    });
    Object.defineProperty(window, "SpeechSynthesisUtterance", {
      configurable: true,
      value: MockSpeechUtterance
    });
    render(<SignToSpeechExperience />);

    const speakButton = screen.getByRole("button", { name: "Speak interpreted text" });
    expect(speakButton).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Translation language"), {
      target: { value: "hi" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Simulate recognition" }));
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("fixture translation")).toBeInTheDocument();
    expect(speakButton).toBeEnabled();

    fireEvent.click(speakButton);

    expect(cancel).toHaveBeenCalledOnce();
    expect(speak).toHaveBeenCalledOnce();
    expect(spokenText).toBe("fixture translation");
    expect(spokenLanguage).toBe("hi-IN");
  });
});
