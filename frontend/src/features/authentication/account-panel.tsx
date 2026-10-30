"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, apiRequest, getCurrentUser, type User } from "@/lib/api";

type SessionState =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "unavailable"; message: string }
  | { kind: "signed-in"; user: User };

function useSessionState(): SessionState {
  const [session, setSession] = useState<SessionState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    void getCurrentUser()
      .then((user) => {
        if (active) {
          setSession({ kind: "signed-in", user });
        }
      })
      .catch((error: unknown) => {
        if (!active) {
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          setSession({ kind: "signed-out" });
        } else {
          setSession({
            kind: "unavailable",
            message:
              error instanceof ApiError
                ? error.message
                : "Your account could not be loaded. Please try again."
          });
        }
      });
    return () => {
      active = false;
    };
  }, []);

  return session;
}

export function SessionGreeting() {
  const session = useSessionState();

  if (session.kind === "loading") {
    return <p aria-live="polite" className="muted" role="status">Checking your account…</p>;
  }
  if (session.kind === "signed-out") {
    return (
      <p className="muted">
        You are not signed in. <Link className="inline-link" href="/login">Sign in</Link>
      </p>
    );
  }
  if (session.kind === "unavailable") {
    return <p aria-live="polite" className="form-status form-error" role="alert">{session.message}</p>;
  }
  return <p className="muted">Signed in as {session.user.full_name}.</p>;
}

export function AccountProfile() {
  const session = useSessionState();

  if (session.kind === "loading") {
    return <p aria-live="polite" role="status">Loading your profile…</p>;
  }
  if (session.kind === "signed-out") {
    return (
      <div>
        <p className="muted">You are not signed in.</p>
        <Link className="button" href="/login">Sign in</Link>
      </div>
    );
  }
  if (session.kind === "unavailable") {
    return <p aria-live="polite" className="form-status form-error" role="alert">{session.message}</p>;
  }
  return <SignedInAccountProfile user={session.user} />;
}

function SignedInAccountProfile({ user }: Readonly<{ user: User }>) {
  const router = useRouter();
  const [fullName, setFullName] = useState(user.full_name);
  const [displayName, setDisplayName] = useState(user.full_name);
  const [deletePassword, setDeletePassword] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function updateProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("");
    setSaving(true);
    try {
      const updatedUser = await apiRequest<User>("/users/me", {
        method: "PATCH",
        body: JSON.stringify({ full_name: fullName })
      });
      setFullName(updatedUser.full_name);
      setDisplayName(updatedUser.full_name);
      setStatus("Profile updated.");
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "Profile could not be updated. Please try again."
      );
    } finally {
      setSaving(false);
    }
  }

  async function deleteAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setStatus("");
    setSaving(true);
    try {
      await apiRequest<{ message: string }>("/users/me", {
        method: "DELETE",
        body: JSON.stringify({ password: deletePassword })
      });
      router.push("/login");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "Account could not be deleted. Please try again."
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <dl className="profile-details">
        <div><dt>Name</dt><dd>{displayName}</dd></div>
        <div><dt>Email</dt><dd>{user.email}</dd></div>
      </dl>
      <form className="form-stack section" onSubmit={updateProfile}>
        <div className="field">
          <label htmlFor="profile-name">Update display name</label>
          <input
            autoComplete="name"
            id="profile-name"
            maxLength={120}
            minLength={1}
            onChange={(event) => setFullName(event.target.value)}
            required
            value={fullName}
          />
        </div>
        <button className="button button-secondary" disabled={saving} type="submit">
          Save profile
        </button>
      </form>
      <section aria-labelledby="delete-account-heading" className="section">
        <h3 id="delete-account-heading">Delete account</h3>
        <p className="muted">
          This permanently removes your account, translation history, notifications,
          feedback, audio events, and preferences. Shared conversations keep other
          participants but remove your account from their participant list.
        </p>
        <form className="form-stack" onSubmit={deleteAccount}>
          <div className="field">
            <label htmlFor="delete-password">Confirm with your password</label>
            <input
              autoComplete="current-password"
              id="delete-password"
              minLength={8}
              onChange={(event) => setDeletePassword(event.target.value)}
              required
              type="password"
              value={deletePassword}
            />
          </div>
          <button className="button button-secondary" disabled={saving} type="submit">
            Delete my account
          </button>
        </form>
      </section>
      {error ? <p aria-live="polite" className="form-status form-error" role="alert">{error}</p> : null}
      {status ? <p aria-live="polite" className="form-status" role="status">{status}</p> : null}
      <LogoutButton />
    </div>
  );
}

export function LogoutButton() {
  const router = useRouter();
  const [error, setError] = useState("");

  async function signOut() {
    setError("");
    try {
      await apiRequest<{ message: string }>("/auth/logout", { method: "POST" });
      router.push("/login");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "Sign-out could not be completed. Please try again."
      );
    }
  }

  return (
    <div>
      <button className="button button-secondary" onClick={signOut} type="button">
        Sign out
      </button>
      {error ? <p aria-live="polite" className="form-status form-error" role="alert">{error}</p> : null}
    </div>
  );
}
