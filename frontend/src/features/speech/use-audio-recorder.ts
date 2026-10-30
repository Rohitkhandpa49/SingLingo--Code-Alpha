"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  transcribeAudio,
  type SpeechTranscriptionResponse,
  type TranscriptionLanguage
} from "@/lib/speech-api";
import { AudioCaptureError, AudioCaptureService } from "./audio-capture-service";

export type AudioRecorderStatus =
  | "idle"
  | "permission_requested"
  | "recording"
  | "processing"
  | "transcription_complete"
  | "error"
  | "unsupported";

const MAX_RECORDING_SECONDS = 60;

export function useAudioRecorder() {
  const [service] = useState(() => new AudioCaptureService());
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sessionIdRef = useRef("");
  const [status, setStatus] = useState<AudioRecorderStatus>("idle");
  const [error, setError] = useState("");
  const [transcription, setTranscription] = useState<SpeechTranscriptionResponse | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        clearTimeout(timeoutRef.current);
      }
      service.dispose();
    };
  }, [service]);

  async function stop(language: TranscriptionLanguage): Promise<void> {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setStatus("processing");
    setError("");
    try {
      const wav = await service.stop();
      const result = await transcribeAudio(wav, language, sessionIdRef.current);
      setTranscription(result);
      setStatus("transcription_complete");
    } catch (caught) {
      setError(errorMessage(caught));
      setStatus(caught instanceof AudioCaptureError && caught.code === "unsupported"
        ? "unsupported"
        : "error");
    } finally {
      sessionIdRef.current = "";
    }
  }

  async function start(language: TranscriptionLanguage): Promise<void> {
    setError("");
    setTranscription(null);
    setStatus("permission_requested");
    sessionIdRef.current = crypto.randomUUID();
    try {
      await service.start((captureError) => {
        if (timeoutRef.current !== null) {
          clearTimeout(timeoutRef.current);
          timeoutRef.current = null;
        }
        setError(captureError.message);
        setStatus("error");
        sessionIdRef.current = "";
      });
      setStatus("recording");
      timeoutRef.current = setTimeout(() => {
        void stop(language);
      }, MAX_RECORDING_SECONDS * 1000);
    } catch (caught) {
      setError(errorMessage(caught));
      setStatus(caught instanceof AudioCaptureError && caught.code === "unsupported"
        ? "unsupported"
        : "error");
      sessionIdRef.current = "";
    }
  }

  function cancel(): void {
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    service.dispose();
    sessionIdRef.current = "";
    setTranscription(null);
    setError("");
    setStatus("idle");
  }

  return { status, error, transcription, start, stop, cancel };
}

function errorMessage(error: unknown): string {
  if (error instanceof AudioCaptureError || error instanceof ApiError) {
    return error.message;
  }
  return "Speech transcription failed. Try again.";
}
