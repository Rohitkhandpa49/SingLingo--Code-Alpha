import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SpeechToSignComposer } from "./speech-to-sign-composer";

const mocked = vi.hoisted(() => ({
  translateTextToSigns: vi.fn(),
  createTranslationHistory: vi.fn()
}));

vi.mock("@/features/speech/microphone-controls", () => ({
  MicrophoneControls: ({
    language,
    onTranscript
  }: {
    language: string;
    onTranscript: (text: string, language: "en" | "hi") => void;
  }) => (
    <button
    onClick={() => onTranscript("नमस्ते", "hi")}
      type="button"
    >
      Provide fixture transcript ({language})
    </button>
  )
}));

vi.mock("@/lib/isl-api", () => ({
  translateTextToSigns: mocked.translateTextToSigns
}));

vi.mock("@/lib/api", () => ({
  createTranslationHistory: mocked.createTranslationHistory
}));

describe("SpeechToSignComposer", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("uses the reviewed transcript as editable text and updates the detected language", () => {
    render(<SpeechToSignComposer />);

    fireEvent.click(screen.getByRole("button", { name: /Provide fixture transcript/ }));

    expect(screen.getByLabelText("Transcript or message")).toHaveValue(
      "नमस्ते"
    );
    expect(screen.getByLabelText("Input language")).toHaveValue("hi");
    expect(screen.getByRole("button", { name: "Prepare sign sequence" })).toBeEnabled();
    expect(screen.getByText(/Text mapping uses exact reviewed vocabulary matches/))
      .toBeInTheDocument();
  });

  it("uses exact backend mappings and saves history only after explicit confirmation", async () => {
    mocked.translateTextToSigns.mockResolvedValue({
      type: "isl_text_translation",
      translation_id: "translation-1",
      status: "success",
      source_text: "hello",
      normalized_text: "hello",
      language: "en",
      sequence: [
        {
          sign_id: "hello",
          sign_name: "Verified hello",
          matched_text: "hello",
          animation_asset: null,
          animation_clip: null
        }
      ],
      unsupported_segments: [],
      translation_level: "single_sign",
      vocabulary_version: "fixture-v1",
      sentence_grammar_available: false,
      timestamp: "2026-10-30T00:00:00Z"
    });
    mocked.createTranslationHistory.mockResolvedValue({ id: "history-1" });
    render(<SpeechToSignComposer />);

    fireEvent.change(screen.getByLabelText("Transcript or message"), {
      target: { value: "hello" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Prepare sign sequence" }));

    await screen.findByText(/Status: success/);
    expect(mocked.translateTextToSigns).toHaveBeenCalledWith("hello", "en");
    expect(mocked.createTranslationHistory).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Play verified sequence" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Save to translation history" }));
    await waitFor(() => expect(mocked.createTranslationHistory).toHaveBeenCalledWith({
      direction: "speech_to_sign",
      source_language: "en",
      target_language: "isl",
      input_text: "hello",
      output_text: "Verified hello"
    }));
    expect(await screen.findByText("Saved translation history-1 to your history."))
      .toBeInTheDocument();
  });

  it("runs a mocked microphone-transcript-to-sign-history flow", async () => {
    mocked.translateTextToSigns.mockResolvedValue({
      type: "isl_text_translation",
      translation_id: "translation-hi",
      status: "success",
      source_text: "नमस्ते",
      normalized_text: "नमस्ते",
      language: "hi",
      sequence: [
        {
          sign_id: "fixture-sign",
          sign_name: "Reviewed Hindi sign",
          matched_text: "नमस्ते",
          animation_asset: null,
          animation_clip: null
        }
      ],
      unsupported_segments: [],
      translation_level: "single_sign",
      vocabulary_version: "fixture-v1",
      sentence_grammar_available: false,
      timestamp: "2026-10-30T00:00:00Z"
    });
    mocked.createTranslationHistory.mockResolvedValue({ id: "history-hi" });
    render(<SpeechToSignComposer />);

    fireEvent.click(screen.getByRole("button", { name: /Provide fixture transcript/ }));
    fireEvent.click(screen.getByRole("button", { name: "Prepare sign sequence" }));

    await screen.findByText(/Status: success/);
    expect(mocked.translateTextToSigns).toHaveBeenCalledWith(
      "नमस्ते",
      "hi"
    );
    fireEvent.click(screen.getByRole("button", { name: "Save to translation history" }));
    await waitFor(() =>
      expect(mocked.createTranslationHistory).toHaveBeenCalledWith({
        direction: "speech_to_sign",
        source_language: "hi",
        target_language: "isl",
        input_text: "नमस्ते",
        output_text: "Reviewed Hindi sign"
      })
    );
  });

  it("shows unsupported spans and does not claim a sentence translation", async () => {
    mocked.translateTextToSigns.mockResolvedValue({
      type: "isl_text_translation",
      translation_id: "translation-2",
      status: "partial",
      source_text: "hello unknown",
      normalized_text: "hello unknown",
      language: "en",
      sequence: [],
      unsupported_segments: [
        {
          start_index: 6,
          end_index: 13,
          text: "unknown",
          reason: "no_verified_mapping"
        }
      ],
      translation_level: "partial",
      vocabulary_version: "fixture-v1",
      sentence_grammar_available: false,
      timestamp: "2026-10-30T00:00:00Z"
    });
    render(<SpeechToSignComposer />);
    fireEvent.change(screen.getByLabelText("Transcript or message"), {
      target: { value: "hello unknown" }
    });
    fireEvent.click(screen.getByRole("button", { name: "Prepare sign sequence" }));

    expect(await screen.findByText(/“unknown” — no verified mapping/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save to translation history" })).toBeDisabled();
  });
});
