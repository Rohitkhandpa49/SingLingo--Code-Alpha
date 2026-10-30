import type { Metadata } from "next";
import { AuthForm } from "@/features/authentication/auth-form";

export const metadata: Metadata = { title: "Reset password" };

export default function ForgotPasswordPage() {
  return (
    <section className="page-container auth-layout">
      <div className="auth-aside">
        <p className="eyebrow">Account help</p>
        <h1>We’ll help you get back in.</h1>
        <p className="muted">
          Request a one-time email link to choose a new password.
        </p>
      </div>
      <AuthForm mode="forgot-password" />
    </section>
  );
}
