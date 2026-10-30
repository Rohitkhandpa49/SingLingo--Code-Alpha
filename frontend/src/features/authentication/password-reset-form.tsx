"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ApiError, apiRequest } from "@/lib/api";
import { validateRegistrationPassword } from "@/lib/validation";

export function PasswordResetForm() {
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [complete, setComplete] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("");
    const formData = new FormData(event.currentTarget);
    const password = String(formData.get("password") ?? "");
    const confirmation = String(formData.get("confirmPassword") ?? "");
    const validationError = validateRegistrationPassword(password, confirmation);
    if (validationError) {
      setError(validationError);
      return;
    }

    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setError("This reset link is invalid or incomplete. Request a new link.");
      return;
    }

    try {
      const result = await apiRequest<{ message: string }>("/auth/password-reset/confirm", {
        method: "POST",
        body: JSON.stringify({
          token,
          password,
          password_confirmation: confirmation
        })
      });
      setStatus(result.message);
      setComplete(true);
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "Password could not be updated. Please try again."
      );
    }
  }

  return (
    <form className="card auth-card" onSubmit={handleSubmit}>
      <h2>Choose a new password</h2>
      <p className="muted">Use at least 8 characters and confirm the new password.</p>
      <div className="form-stack">
        <div className="field">
          <label htmlFor="password">New password</label>
          <input
            autoComplete="new-password"
            id="password"
            minLength={8}
            name="password"
            required
            type="password"
          />
        </div>
        <div className="field">
          <label htmlFor="confirmPassword">Confirm new password</label>
          <input
            autoComplete="new-password"
            id="confirmPassword"
            minLength={8}
            name="confirmPassword"
            required
            type="password"
          />
        </div>
        {error ? <p aria-live="polite" className="form-status form-error" role="alert">{error}</p> : null}
        {status ? <p aria-live="polite" className="form-status" role="status">{status}</p> : null}
        {complete ? (
          <Link className="button full-width" href="/login">Return to sign in</Link>
        ) : (
          <button className="button full-width" type="submit">Update password</button>
        )}
      </div>
    </form>
  );
}
