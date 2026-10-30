import type { Metadata } from "next";
import { PasswordResetForm } from "@/features/authentication/password-reset-form";

export const metadata: Metadata = { title: "Choose a new password" };

export default function ResetPasswordPage() {
  return (
    <section className="page-container auth-layout">
      <div className="auth-aside">
        <p className="eyebrow">Account help</p>
        <h1>Secure your SignLingo account.</h1>
        <p className="muted">
          Reset links are single-use and expire automatically.
        </p>
      </div>
      <PasswordResetForm />
    </section>
  );
}
