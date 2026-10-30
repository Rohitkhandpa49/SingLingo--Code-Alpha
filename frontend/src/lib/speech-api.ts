import { apiRequest } from "@/lib/api";

export type TranscriptionLanguage = "auto" | "en" | "hi";

export interface SpeechTranscriptionResponse {
  transcription_id: string;
  session_id: string;
  status: "final";
  original_text: string;
  normalized_text: string;
  language: "en" | "hi";
  language_detection: "selected" | "whisper";
  segments: Array<{ start: number; end: number; text: string }>;
  model_name: string;
  method: "chunked";
  timestamp: string;
}

export function transcribeAudio(
  audio: Blob,
  language: TranscriptionLanguage,
  sessionId: string
): Promise<SpeechTranscriptionResponse> {
  const form = new FormData();
  form.append("audio", audio, "speech.wav");
  form.append("language", language);
  form.append("session_id", sessionId);
  return apiRequest<SpeechTranscriptionResponse>("/speech/transcribe", {
    method: "POST",
    body: form
  });
}
