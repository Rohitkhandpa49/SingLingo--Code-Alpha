"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Notice } from "@/components/ui/notice";
import { ApiError, apiRequest, getCurrentUser, type AccessibilityPreferences } from "@/lib/api";

const defaultPreferences: AccessibilityPreferences = {
  live_captions: true,
  visual_alerts: true,
  vibration_enabled: false,
  reduced_motion: false,
  theme: "system",
  camera_enabled: true
};

type SettingsState = "loading" | "signed-out" | "ready" | "unavailable";

export default function SettingsPage() {
  const [preferences, setPreferences] = useState(defaultPreferences);
  const [language, setLanguage] = useState<"en" | "hi">("en");
  const [state, setState] = useState<SettingsState>("loading");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    void getCurrentUser()
      .then((user) => {
        if (active) {
          setPreferences({ ...defaultPreferences, ...user.accessibility_preferences });
          setLanguage(user.preferred_language ?? "en");
          setState("ready");
        }
      })
      .catch((requestError: unknown) => {
        if (!active) {
          return;
        }
        if (requestError instanceof ApiError && requestError.status === 401) {
          setState("signed-out");
        } else {
          setError(
            requestError instanceof ApiError
              ? requestError.message
              : "Preferences could not be loaded."
          );
          setState("unavailable");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    document.documentElement.dataset.reducedMotion = String(preferences.reduced_motion);
    return () => {
      delete document.documentElement.dataset.reducedMotion;
    };
  }, [preferences.reduced_motion]);

  async function savePreferences() {
    setSaving(true);
    setError("");
    setStatus("");
    try {
      await apiRequest("/users/me", {
        method: "PATCH",
        body: JSON.stringify({
          preferred_language: language,
          preferred_sign_language: "ISL",
          accessibility_preferences: preferences
        })
      });
      setStatus("Your preferences have been saved.");
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "Preferences could not be saved. Please try again."
      );
    } finally {
      setSaving(false);
    }
  }

  if (state === "loading") {
    return <section className="page-container"><p aria-live="polite" role="status">Loading your preferences…</p></section>;
  }
  if (state === "signed-out") {
    return (
      <section className="page-container">
        <div className="page-heading"><h1>Accessibility & preferences</h1></div>
        <Notice title="Sign in to manage preferences">
          Your accessibility and language preferences are saved to your account.
        </Notice>
        <Link className="button section" href="/login">Sign in</Link>
      </section>
    );
  }
  if (state === "unavailable") {
    return (
      <section className="page-container">
        <div className="page-heading"><h1>Accessibility & preferences</h1></div>
        <p aria-live="polite" className="form-status form-error" role="alert">{error}</p>
      </section>
    );
  }

  return (
    <section className="page-container">
      <div className="page-heading">
        <p className="eyebrow">Make it yours</p>
        <h1>Accessibility & preferences</h1>
        <p>These preferences are saved to your SignLingo account.</p>
      </div>
      <section aria-label="Accessibility preferences" className="settings-list section">
        <label className="setting-row" htmlFor="captions">
          <span>
            <strong>Show captions when available</strong>
            <p>Keep text visible alongside audio output in translation flows.</p>
          </span>
          <input
            checked={preferences.live_captions}
            id="captions"
            onChange={(event) => setPreferences((current) => ({ ...current, live_captions: event.target.checked }))}
            type="checkbox"
          />
        </label>
        <label className="setting-row" htmlFor="visual-alerts">
          <span>
            <strong>Visual alerts</strong>
            <p>Prefer visual notifications for important updates.</p>
          </span>
          <input
            checked={preferences.visual_alerts}
            id="visual-alerts"
            onChange={(event) => setPreferences((current) => ({ ...current, visual_alerts: event.target.checked }))}
            type="checkbox"
          />
        </label>
        <label className="setting-row" htmlFor="vibration">
          <span>
            <strong>Vibration feedback</strong>
            <p>Allow supported devices to provide haptic feedback.</p>
          </span>
          <input
            checked={preferences.vibration_enabled}
            id="vibration"
            onChange={(event) => setPreferences((current) => ({ ...current, vibration_enabled: event.target.checked }))}
            type="checkbox"
          />
        </label>
        <label className="setting-row" htmlFor="reduced-motion">
          <span>
            <strong>Reduce motion</strong>
            <p>Limit non-essential animation in the interface.</p>
          </span>
          <input
            checked={preferences.reduced_motion}
            id="reduced-motion"
            onChange={(event) => setPreferences((current) => ({ ...current, reduced_motion: event.target.checked }))}
            type="checkbox"
          />
        </label>
        <label className="setting-row" htmlFor="camera-enabled">
          <span>
            <strong>Enable camera features</strong>
            <p>Camera access is still requested only when you start a camera feature.</p>
          </span>
          <input
            checked={preferences.camera_enabled}
            id="camera-enabled"
            onChange={(event) => setPreferences((current) => ({ ...current, camera_enabled: event.target.checked }))}
            type="checkbox"
          />
        </label>
        <div className="field">
          <label htmlFor="language">Preferred interface language</label>
          <select id="language" onChange={(event) => setLanguage(event.target.value as "en" | "hi")} value={language}>
            <option value="en">English</option>
            <option value="hi">Hindi</option>
          </select>
        </div>
        {error ? <p aria-live="polite" className="form-status form-error" role="alert">{error}</p> : null}
        <div aria-live="polite" className="form-status" role="status">{status}</div>
        <button className="button" disabled={saving} onClick={savePreferences} type="button">
          {saving ? "Saving…" : "Save preferences"}
        </button>
      </section>
      <div className="card workspace-panel">
        <div className="panel-heading">
          <div>
            <h2>Sign language</h2>
            <p>Preferred sign language for future translation services.</p>
          </div>
        </div>
        <p className="muted">Indian Sign Language (ISL)</p>
      </div>
    </section>
  );
}
