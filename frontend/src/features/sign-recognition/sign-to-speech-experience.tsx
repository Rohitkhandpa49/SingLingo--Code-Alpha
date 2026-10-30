"use client";

import { useEffect, useRef, useState } from "react";
import { AudioLines, Hand, Info } from "lucide-react";
import { SignCamera } from "@/features/sign-recognition/sign-camera";
import type { GestureRecognitionResult } from "@/lib/landmarks";
import { TextToSpeechService } from "@/lib/tts-service";

function recognitionMessage(result: GestureRecognitionResult | null): string {
  if (!result) {
    return "Start hand tracking to collect landmark sequences.";
  }
  if (result.status === "model_unavailable") {
    return "Hand landmarks are being collected. A gesture model is not configured.";
  }
  if (result.status === "unknown") {
    return "No supported gesture was recognized with sufficient confidence.";
  }
  if (result.translation?.status === "success") {
    return `Verified vocabulary mapping: ${result.translation.interpreted_text}`;
  }
  if (result.translation?.status === "partial") {
    return "A gesture was recognized, but the available vocabulary cannot produce a complete translation.";
  }
  return "A model label was returned, but it has no compatible verified vocabulary mapping.";
}

export function SignToSpeechExperience() {
  const [recognition, setRecognition] = useState<GestureRecognitionResult | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<"en" | "hi">("en");
  const [speechError, setSpeechError] = useState("");
  const ttsService = useRef(new TextToSpeechService());

  useEffect(() => {
    const service = ttsService.current;
    return () => {
      service.cancel();
    };
  }, []);

  async function speakResult(): Promise<void> {
    const translation = recognition?.translation;
    if (
      recognition?.status !== "classified" ||
      translation?.status !== "success" ||
      translation.language !== targetLanguage ||
      !translation.interpreted_text.trim()
    ) {
      return;
    }
    setSpeechError("");
    try {
      await ttsService.current.speak(translation.interpreted_text, translation.language);
    } catch (error) {
      setSpeechError(
        error instanceof Error ? error.message : "Speech output could not be played. Try again."
      );
    }
  }

  return (
    <>
      <div className="workspace-grid">
        <SignCamera onRecognition={setRecognition} targetLanguage={targetLanguage} />
        <section
          aria-labelledby="recognition-heading"
          className="card workspace-panel recognition-panel"
        >
          <div className="panel-heading">
            <div>
              <h2 id="recognition-heading">Your translation</h2>
              <p>Hand pose <span aria-hidden="true">→</span> label <span aria-hidden="true">→</span> speech</p>
            </div>
          </div>
          <div aria-live="polite" className="output-box" role="status">
            {recognition?.status === "classified" ? (
              <div className="recognition-result">
                <span className="recognition-result-caption">Model gesture label</span>
                <strong className="recognition-label">{recognition.label}</strong>
                <p>{Math.round((recognition.confidence ?? 0) * 100)}% model confidence</p>
                {recognition.translation?.status === "success" ? (
                  <p>
                    <strong>Interpreted text:</strong>{" "}
                    {recognition.translation.interpreted_text}
                  </p>
                ) : (
                  <p>No compatible verified vocabulary translation is available.</p>
                )}
              </div>
            ) : (
              <div className="recognition-empty">
                <span aria-hidden="true" className="recognition-icon">
                  <Hand />
                </span>
                <div>
                  <strong>{recognition ? "No sign recognized" : "Ready when you are"}</strong>
                  <p>{recognitionMessage(recognition)}</p>
                </div>
                {!recognition ? <span className="status-pill">Model not configured</span> : null}
              </div>
            )}
          </div>
          <div className="speech-controls">
            <div className="field">
              <label htmlFor="speech-language">Translation language</label>
              <select
                id="speech-language"
                onChange={(event) => {
                  const language = event.target.value;
                  if (language === "en" || language === "hi") {
                    setTargetLanguage(language);
                    setRecognition(null);
                  }
                }}
                value={targetLanguage}
              >
                <option value="en">English</option>
                <option value="hi">Hindi</option>
              </select>
            </div>
            <button
              className="button full-width"
              disabled={
                recognition?.status !== "classified" ||
                recognition.translation?.status !== "success" ||
                recognition.translation.language !== targetLanguage ||
                !recognition.translation.interpreted_text.trim()
              }
              onClick={() => void speakResult()}
              type="button"
            >
              <AudioLines aria-hidden="true" /> Speak interpreted text
            </button>
          </div>
          {speechError ? (
            <p aria-live="polite" className="form-status form-error" role="alert">
              {speechError}
            </p>
          ) : null}
        </section>
      </div>
      <aside className="model-notice" role="note">
        <Info aria-hidden="true" />
        <div className="model-notice-content">
          <strong>Experimental recognition · limited vocabulary</strong>
          <p>
            A result depends on a configured, validated model. Static models recognize held poses;
            dynamic models require labeled motion sequences. Neither provides complete ISL translation.
          </p>
          <details>
            <summary>Dataset, licensing &amp; privacy details</summary>
            <p>
              No training dataset is bundled with this repository. Supply a consented, licensed
              dataset before training; do not commit private samples or checkpoints. Camera frames
              stay in your browser; only validated landmarks are sent for inference.
            </p>
          </details>
        </div>
      </aside>
    </>
  );
}
