"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { ApiError, deleteTranslationHistoryEntry, getTranslationHistory, type HistoryEntry, type HistoryFilters } from "@/lib/api";

function toUtcDateBoundary(value: string, endOfDay: boolean): string | undefined {
  if (!value) {
    return undefined;
  }
  const date = new Date(`${value}T${endOfDay ? "23:59:59.999" : "00:00:00"}`);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

function formatLanguage(language: HistoryEntry["source_language"]): string {
  return language === "isl" ? "Indian Sign Language" : language === "hi" ? "Hindi" : "English";
}

function formatDirection(direction: HistoryEntry["direction"]): string {
  return direction === "sign_to_speech" ? "Sign to speech" : "Speech to sign";
}

export function HistoryList() {
  const [items, setItems] = useState<HistoryEntry[]>([]);
  const [filters, setFilters] = useState<HistoryFilters>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [language, setLanguage] = useState("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [deletingId, setDeletingId] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    void getTranslationHistory(filters)
      .then((response) => {
        if (active) {
          setItems(response.items);
          setError("");
        }
      })
      .catch((requestError: unknown) => {
        if (!active) {
          return;
        }
        setError(
          requestError instanceof ApiError
            ? requestError.message
            : "Translation history could not be loaded."
        );
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [filters, refreshKey]);

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    setFilters({
      search: search.trim() || undefined,
      language: language || undefined,
      createdAfter: toUtcDateBoundary(fromDate, false),
      createdBefore: toUtcDateBoundary(toDate, true)
    });
  }

  async function deleteEntry(entryId: string) {
    setDeletingId(entryId);
    setError("");
    try {
      await deleteTranslationHistoryEntry(entryId);
      setItems((currentItems) => currentItems.filter((item) => item.id !== entryId));
    } catch (requestError) {
      setError(
        requestError instanceof ApiError
          ? requestError.message
          : "This history entry could not be deleted."
      );
    } finally {
      setDeletingId("");
    }
  }

  const isUnauthenticated = error && /authentication is required/i.test(error);

  return (
    <section aria-label="Translation history filters" className="section">
      <form className="filter-bar history-filters" onSubmit={applyFilters}>
        <label className="sr-only" htmlFor="history-search">Search translations</label>
        <input
          id="history-search"
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Search translations"
          type="search"
          value={search}
        />
        <label className="sr-only" htmlFor="history-language">Filter by language</label>
        <select
          className="toolbar-select"
          id="history-language"
          onChange={(event) => setLanguage(event.target.value)}
          value={language}
        >
          <option value="">All languages</option>
          <option value="isl">Indian Sign Language</option>
          <option value="hi">Hindi</option>
          <option value="en">English</option>
        </select>
        <label className="sr-only" htmlFor="history-from">Start date</label>
        <input id="history-from" onChange={(event) => setFromDate(event.target.value)} type="date" value={fromDate} />
        <label className="sr-only" htmlFor="history-to">End date</label>
        <input id="history-to" onChange={(event) => setToDate(event.target.value)} type="date" value={toDate} />
        <button className="button" type="submit">Apply filters</button>
      </form>

      {error ? (
        <div className="notice" role="alert">
          <div>
            <strong>{isUnauthenticated ? "Sign in to view your history" : "History request failed"}</strong>
            <p>{isUnauthenticated ? "Your saved translations are private to your account." : error}</p>
            {isUnauthenticated ? <Link className="inline-link" href="/login">Sign in</Link> : null}
            {!isUnauthenticated ? (
              <button
                className="button button-secondary"
                onClick={() => {
                  setError("");
                  setLoading(true);
                  setRefreshKey((key) => key + 1);
                }}
                style={{ marginTop: "0.75rem" }}
                type="button"
              >
                Try again
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {loading ? (
        <div aria-live="polite" className="card empty-state" role="status">
          <p>Loading saved translations…</p>
        </div>
      ) : items.length === 0 && !error ? (
        <div className="card empty-state">
          <div>
            <h2>No translations found</h2>
            <p>Completed translations saved to your account will appear here.</p>
          </div>
        </div>
      ) : (
        <div className="history-list">
          {items.map((item) => (
            <article className="card history-entry" key={item.id}>
              <div className="history-entry-heading">
                <div>
                  <p className="eyebrow">{formatDirection(item.direction)}</p>
                  <h2>{formatLanguage(item.source_language)} → {formatLanguage(item.target_language)}</h2>
                </div>
                <time dateTime={item.created_at}>
                  {new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}
                </time>
              </div>
              <div className="history-text-grid">
                <div><h3>Input</h3><p>{item.input_text}</p></div>
                <div><h3>Output</h3><p>{item.output_text}</p></div>
              </div>
              <div className="history-entry-footer">
                {item.confidence === null ? <span className="muted">Confidence not provided</span> : <span className="muted">Confidence: {Math.round(item.confidence * 100)}%</span>}
                <button
                  aria-label={`Delete ${formatDirection(item.direction)} translation`}
                  className="button button-secondary"
                  disabled={deletingId === item.id}
                  onClick={() => void deleteEntry(item.id)}
                  type="button"
                >
                  {deletingId === item.id ? "Deleting…" : "Delete"}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
