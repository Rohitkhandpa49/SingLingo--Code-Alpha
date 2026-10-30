import type { Metadata } from "next";
import { AuthForm } from "@/features/authentication/auth-form";
import { Notice } from "@/components/ui/notice";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <section className="page-container auth-layout">
      <div className="auth-aside">
        <p className="eyebrow">Your accessible workspace</p>
        <h1>Good to see you again.</h1>
        <p className="muted">
          Sign in to your SignLingo account. Your session is managed with a protected,
          HTTP-only cookie.
        </p>
        <Notice title="Secure session handling">
          Credentials are sent to the configured backend over HTTP and are never stored in
          browser local storage.
        </Notice>
      </div>
      <AuthForm mode="login" />
    </section>
  );
}
