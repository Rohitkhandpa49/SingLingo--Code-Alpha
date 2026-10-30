"use client";

import { useEffect } from "react";

export default function ErrorPage({
  error,
  reset
}: Readonly<{
  error: Error & { digest?: string };
  reset: () => void;
}>) {
  useEffect(() => {
    console.error("SignLingo page error:", error);
  }, [error]);

  return (
    <section className="page-container">
      <div className="card empty-state">
        <div>
          <p className="eyebrow">Something went wrong</p>
          <h1>This page could not be loaded.</h1>
          <p>An unexpected error occurred. Your information has not been submitted.</p>
          <button className="button" onClick={() => reset()} style={{ marginTop: "1rem" }} type="button">
            Try again
          </button>
        </div>
      </div>
    </section>
  );
}
