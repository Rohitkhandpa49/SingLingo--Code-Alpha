import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MicrophoneControls } from "./microphone-controls";

const mocked = vi.hoisted(() => ({
  start: vi.fn(),
  stop: vi.fn(),
  cancel: vi.fn(),
  status: "idle" as
    | "idle"
    | "recording"
    | "processing"
    | "transcription_complete"
    | "error",
  transcript: {
    transcription_id: "transcription-1",
    session_id: "session-1",
    status: "final" as const,
    original_text: "review this text",
    normalized_text: "review this text",
    language: "en" as const,
    language_detection: "whisper" as const,
    segments: [],
    model_name: "tiny",
    method: "chunked" as const,
    timestamp: "2026-10-30T00:00:00Z"
  }
}));

vi.mock("./use-audio-recorder", () => ({
  useAudioRecorder: () => ({
    status: mocked.status,
    error: "",
    transcription: mocked.status === "transcription_complete" ? mocked.transcript : null,
    start: mocked.start,
    stop: mocked.stop,
    cancel: mocked.cancel
  })
}));

describe("MicrophoneControls", () => {
  afterEach(() => {
    vi.clearAllMocks();
    mocked.status = "idle";
  });

  it("starts and stops recording with explicit visual status", async () => {
    const view = render(<MicrophoneControls language="en" onTranscript={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Record speech" }));
    expect(mocked.start).toHaveBeenCalledWith("en");
    expect(screen.getByRole("status")).toHaveTextContent("Microphone inactive");

    mocked.status = "recording";
    view.rerender(<MicrophoneControls language="en" onTranscript={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Stop and transcribe" }));
    await waitFor(() => expect(mocked.stop).toHaveBeenCalledWith("en"));
  });

  it("lets users review and choose the transcript before replacing typed text", () => {
    const onTranscript = vi.fn();
    mocked.status = "transcription_complete";
    render(<MicrophoneControls language="auto" onTranscript={onTranscript} />);

    expect(screen.getByText("Review transcript before continuing")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Use transcript" }));
    expect(onTranscript).toHaveBeenCalledWith("review this text", "en");
  });
});
