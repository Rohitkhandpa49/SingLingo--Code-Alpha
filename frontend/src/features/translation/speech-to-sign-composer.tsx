"use client";

import { useState } from "react";
import { Languages, PersonStanding } from "lucide-react";
import { Notice } from "@/components/ui/notice";
import { AvatarSequencePlayer } from "@/features/avatar/avatar-sequence-player";
import { MicrophoneControls } from "@/features/speech/microphone-controls";
import {
  createTranslationHistory,
  type HistoryEntry
} from "@/lib/api";
import {
  translateTextToSigns,
  type ISLTextTranslationResponse
} from "@/lib/isl-api";
import type { TranscriptionLanguage } from "@/lib/speech-api";

export function SpeechToSignComposer() {
  const [text, setText] = useState("");
  const [language, setLanguage] = useState<TranscriptionLanguage>("en");
  const [translation, setTranslation] = useState<ISLTextTranslationResponse | null>(null);
  const [isTranslating, setIsTranslating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [workflowError, setWorkflowError] = useState("");
  const [historyMessage, setHistoryMessage] = useState("");

  async function prepareSigns() {
    setIsTranslating(true);
    setWorkflowError("");
    setHistoryMessage("");
    setTranslation(null);
    try {
      const result = await translateTextToSigns(text, language);
      setTranslation(result);
      if (result.language) {
        setLanguage(result.language);
      }
    } catch (error) {
      setWorkflowError(
        error instanceof Error ? error.message : "The sign sequence could not be prepared."
      );
    } finally {
      setIsTranslating(false);
    }
  }

  async function saveToHistory() {
    if (!translation || translation.status !== "success" || !translation.language) {
      return;
    }
    setIsSaving(true);
    setWorkflowError("");
    setHistoryMessage("");
    try {
      const saved: HistoryEntry = await createTranslationHistory({
        direction: "speech_to_sign",
        source_language: translation.language,
        target_language: "isl",
        input_text: translation.source_text,
        output_text: translation.sequence.map((item) => item.sign_name).join(" → ")
      });
      setHistoryMessage(`Saved translation ${saved.id} to your history.`);
    } catch (error) {
      setWorkflowError(
        error instanceof Error ? error.message : "The translation could not be saved."
      );
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <section className="page-container">
      <div className="page-heading">
        <p className="eyebrow">Speech → text → sign</p>
        <h1>Speech to sign</h1>
        <p>
          Record Hindi or English speech, review the transcript, and edit it before continuing.
        </p>
      </div>
      <div className="workspace-grid">
        <section aria-labelledby="input-heading" className="card workspace-panel">
          <div className="panel-heading">
            <div>
              <h2 id="input-heading">Your message</h2>
              <p>Type a message or record speech, then request exact verified vocabulary matches.</p>
            </div>
            <Languages aria-hidden="true" />
          </div>
          <div className="field">
            <label htmlFor="input-language">Input language</label>
            <select
              id="input-language"
              onChange={(event) => {
                const nextLanguage = event.target.value;
                if (nextLanguage === "auto" || nextLanguage === "en" || nextLanguage === "hi") {
                  setLanguage(nextLanguage);
                  setTranslation(null);
                  setWorkflowError("");
                  setHistoryMessage("");
                }
              }}
              value={language}
            >
              <option value="auto">Detect Hindi or English</option>
              <option value="en">English</option>
              <option value="hi">Hindi</option>
            </select>
          </div>
          <div className="field" style={{ marginTop: "1rem" }}>
            <label htmlFor="message">Transcript or message</label>
            <textarea
              id="message"
              maxLength={5000}
              onChange={(event) => {
                setText(event.target.value);
                setTranslation(null);
                setWorkflowError("");
                setHistoryMessage("");
              }}
              placeholder="Record speech or type a message to review..."
              value={text}
            />
            <p className="field-hint">
              {text.length}/5,000 characters · Not saved unless you choose history.
            </p>
          </div>
          <div className="control-row">
            <button
              className="button"
              disabled={!text.trim() || isTranslating}
              onClick={() => void prepareSigns()}
              type="button"
            >
              <PersonStanding aria-hidden="true" />
              {isTranslating ? "Preparing verified sequence..." : "Prepare sign sequence"}
            </button>
          </div>
          <MicrophoneControls
            language={language}
            onTranscript={(transcript, detectedLanguage) => {
              setText(transcript);
              setLanguage(detectedLanguage);
              setTranslation(null);
              setWorkflowError("");
              setHistoryMessage("");
            }}
          />
          {workflowError ? (
            <p aria-live="assertive" className="form-status form-error" role="alert">
              {workflowError}
            </p>
          ) : null}
          {translation ? (
            <section aria-labelledby="text-translation-heading" className="text-translation-result">
              <h3 id="text-translation-heading">Verified vocabulary match</h3>
              <p aria-live="polite" role="status">
                Status: {translation.status}. Language:{" "}
                {translation.language ?? "not detected"}. Vocabulary:{" "}
                {translation.vocabulary_version ?? "not configured"}.
              </p>
              {translation.sequence.length ? (
                <ol aria-label="Mapped sign sequence">
                  {translation.sequence.map((item, index) => (
                    <li key={`${item.sign_id}-${index}`}>
                      {item.sign_name} <span>({item.matched_text})</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p>No exact verified vocabulary match was found.</p>
              )}
              {translation.unsupported_segments.length ? (
                <div>
                  <strong>Unsupported text</strong>
                  <ul>
                    {translation.unsupported_segments.map((segment, index) => (
                      <li key={`${segment.start_index}-${index}`}>
                        “{segment.text}” — {segment.reason.replaceAll("_", " ")}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <button
                className="button button-secondary"
                disabled={
                  translation.status !== "success" ||
                  !translation.sequence.length ||
                  isSaving
                }
                onClick={() => void saveToHistory()}
                type="button"
              >
                {isSaving ? "Saving..." : "Save to translation history"}
              </button>
              {historyMessage ? (
                <p aria-live="polite" className="form-status" role="status">
                  {historyMessage}
                </p>
              ) : null}
            </section>
          ) : null}
        </section>
        <section aria-labelledby="avatar-heading" className="card workspace-panel">
          <div className="panel-heading">
            <div>
              <h2 id="avatar-heading">Signing avatar</h2>
              <p>Playback uses only registered, verified 3D assets.</p>
            </div>
          </div>
          <AvatarSequencePlayer
            key={translation?.translation_id ?? "no-translation"}
            sequence={translation?.sequence ?? []}
          />
          <p className="field-hint">
            No verified animation assets are bundled. The player remains disabled until verified
            sign assets and animation clips are explicitly registered.
          </p>
        </section>
      </div>
      <div style={{ marginTop: "1rem" }}>
        <Notice title="Limited verified vocabulary only">
          Transcription sends a temporary WAV recording to the authenticated backend for processing;
          the recording is not stored. Text mapping uses exact reviewed vocabulary matches. Unmatched
          words and unsupported sentence grammar are reported rather than guessed. Saving to history
          is explicit; translations are not saved automatically.
        </Notice>
      </div>
    </section>
  );
}
