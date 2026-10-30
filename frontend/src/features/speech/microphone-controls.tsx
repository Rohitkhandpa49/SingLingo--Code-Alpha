"use client";

import { Mic, Pause, RotateCcw } from "lucide-react";
import { useAudioRecorder, type AudioRecorderStatus } from "./use-audio-recorder";
import type { TranscriptionLanguage } from "@/lib/speech-api";

const STATUS_LABELS: Record<AudioRecorderStatus, string> = {
  idle: "Microphone inactive",
  permission_requested: "Requesting microphone permission",
  recording: "Recording",
  processing: "Processing audio",
  transcription_complete: "Transcription complete",
  error: "Speech recognition error",
  unsupported: "Microphone recording unsupported"
};

type Props = Readonly<{
  language: TranscriptionLanguage;
  onTranscript: (text: string, language: "en" | "hi") => void;
}>;

export function MicrophoneControls({ language, onTranscript }: Props) {
  const recorder = useAudioRecorder();
  const transcription = recorder.transcription;

  async function stopRecording() {
    await recorder.stop(language);
  }

  return (
    <div className="microphone-controls">
      <div aria-live="polite" className="speech-status" role="status">
        <strong>{STATUS_LABELS[recorder.status]}</strong>
        {recorder.status === "recording" ? (
          <span>Stop within 60 seconds. Audio is not saved by SignLingo.</span>
        ) : null}
      </div>
      {recorder.status === "recording" ? (
        <button className="button button-secondary" onClick={stopRecording} type="button">
          <Pause aria-hidden="true" /> Stop and transcribe
        </button>
      ) : (
        <button
          className="button button-secondary"
          disabled={recorder.status === "permission_requested" || recorder.status === "processing"}
          onClick={() => void recorder.start(language)}
          type="button"
        >
          <Mic aria-hidden="true" /> Record speech
        </button>
      )}
      {recorder.status === "recording" ? (
        <button className="button button-quiet" onClick={recorder.cancel} type="button">
          <RotateCcw aria-hidden="true" /> Cancel
        </button>
      ) : null}
      {transcription ? (
        <div aria-live="polite" className="live-transcript" role="status">
          <strong>Review transcript before continuing</strong>
          <p>{transcription.normalized_text}</p>
          <span>
            {transcription.language === "hi" ? "Hindi" : "English"} · {transcription.method}{" "}
            transcription
          </span>
          {transcription.language !== language && language !== "auto" ? (
            <p className="field-hint">
              The detected transcript language differs from the requested language.
            </p>
          ) : null}
          <button
            className="button button-quiet"
            onClick={() => onTranscript(transcription.normalized_text, transcription.language)}
            type="button"
          >
            Use transcript
          </button>
        </div>
      ) : null}
      {recorder.error ? (
        <p aria-live="assertive" className="form-status form-error" role="alert">
          {recorder.error}
        </p>
      ) : null}
    </div>
  );
}
