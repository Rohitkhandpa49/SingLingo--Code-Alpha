import type { Metadata } from "next";
import { AuthForm } from "@/features/authentication/auth-form";
import { Notice } from "@/components/ui/notice";

export const metadata: Metadata = { title: "Create account" };

export default function RegisterPage() {
  return (
    <section className="page-container auth-layout">
      <div className="auth-aside">
        <p className="eyebrow">A more inclusive conversation</p>
        <h1>Make room for every voice.</h1>
        <p className="muted">
          Create an account to access your profile and saved translation history.
        </p>
        <Notice title="Protected account data">
          Your password is hashed by the backend and is never returned to the frontend.
        </Notice>
      </div>
      <AuthForm mode="register" />
    </section>
  );
}
