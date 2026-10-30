"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { ApiError, apiRequest, type AuthResponse } from "@/lib/api";
import { validateRegistrationPassword } from "@/lib/validation";

type AuthMode = "login" | "register" | "forgot-password";

const copy: Record<AuthMode, { title: string; description: string; submit: string }> = {
  login: {
    title: "Welcome back",
    description: "Sign in to continue to your SignLingo workspace.",
    submit: "Sign in"
  },
  register: {
    title: "Create your account",
    description: "Set up an account for your future SignLingo workspace.",
    submit: "Create account"
  },
  "forgot-password": {
    title: "Reset your password",
    description: "Enter the email address associated with your account.",
    submit: "Request reset link"
  }
};

export function AuthForm({ mode }: Readonly<{ mode: AuthMode }>) {
  const router = useRouter();
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("");
    const formData = new FormData(event.currentTarget);

    if (mode === "register") {
      const password = String(formData.get("password") ?? "");
      const confirmation = String(formData.get("confirmPassword") ?? "");
      const validationError = validateRegistrationPassword(password, confirmation);
      if (validationError) {
        setError(validationError);
        setStatus("");
        return;
      }
    }

    if (mode === "forgot-password") {
      try {
        const result = await apiRequest<{ message: string }>("/auth/password-reset/request", {
          method: "POST",
          body: JSON.stringify({ email: String(formData.get("email") ?? "") })
        });
        setStatus(result.message);
      } catch (requestError) {
        setError(
          requestError instanceof ApiError
            ? requestError.message
            : "Password reset could not be requested. Please try again."
        );
      }
      return;
    }

    const body =
      mode === "register"
        ? {
            full_name: String(formData.get("fullName") ?? ""),
            email: String(formData.get("email") ?? ""),
            password: String(formData.get("password") ?? ""),
            password_confirmation: String(formData.get("confirmPassword") ?? "")
          }
        : {
            email: String(formData.get("email") ?? ""),
            password: String(formData.get("password") ?? "")
          };

    try {
      await apiRequest<AuthResponse>(`/auth/${mode}`, {
        method: "POST",
        body: JSON.stringify(body)
      });
      setStatus("Signed in successfully. Opening your workspace.");
      router.push("/dashboard");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "Sign-in could not be completed. Please try again."
      );
    }
  }

  const currentCopy = copy[mode];

  return (
    <form className="card auth-card" onSubmit={handleSubmit}>
      <h2>{currentCopy.title}</h2>
      <p className="muted">{currentCopy.description}</p>
      <div className="form-stack">
        {mode === "register" ? (
          <div className="field">
            <label htmlFor="fullName">Full name</label>
            <input autoComplete="name" id="fullName" name="fullName" required />
          </div>
        ) : null}
        <div className="field">
          <label htmlFor="email">Email address</label>
          <input
            autoComplete="email"
            id="email"
            name="email"
            required
            type="email"
          />
        </div>
        {mode !== "forgot-password" ? (
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              autoComplete={mode === "register" ? "new-password" : "current-password"}
              id="password"
              minLength={8}
              name="password"
              required
              type="password"
            />
            {mode === "register" ? (
              <>
                <p className="field-hint">Use at least 8 characters.</p>
                <label htmlFor="confirmPassword">Confirm password</label>
                <input
                  autoComplete="new-password"
                  id="confirmPassword"
                  minLength={8}
                  name="confirmPassword"
                  required
                  type="password"
                />
              </>
            ) : null}
          </div>
        ) : null}
        <p aria-live="polite" className="form-status form-error" role="alert">
          {error}
        </p>
        <p aria-live="polite" className="form-status" role="status">
          {status}
        </p>
        <button className="button full-width" type="submit">
          {currentCopy.submit}
        </button>
      </div>
      <p className="muted">
        {mode === "login" ? (
          <>
            <Link className="inline-link" href="/forgot-password">
              Forgot password?
            </Link>
            {" · "}
            New here?{" "}
            <Link className="inline-link" href="/register">
              Create an account
            </Link>
          </>
        ) : mode === "register" ? (
          <>
            Already have an account?{" "}
            <Link className="inline-link" href="/login">
              Sign in
            </Link>
          </>
        ) : (
          <>
            Remembered it?{" "}
            <Link className="inline-link" href="/login">
              Return to sign in
            </Link>
          </>
        )}
      </p>
    </form>
  );
}
