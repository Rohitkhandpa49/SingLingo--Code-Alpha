const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export interface User {
  id: string;
  full_name: string;
  email: string;
  created_at: string;
  preferred_language: "en" | "hi" | null;
  preferred_sign_language: string | null;
  accessibility_preferences: AccessibilityPreferences;
}

export interface AccessibilityPreferences {
  live_captions: boolean;
  visual_alerts: boolean;
  vibration_enabled: boolean;
  reduced_motion: boolean;
  theme: "light" | "dark" | "system";
  camera_enabled: boolean;
}

export interface AuthResponse {
  user: User;
}

export interface HistoryEntry {
  id: string;
  direction: "sign_to_speech" | "speech_to_sign";
  source_language: "isl" | "hi" | "en";
  target_language: "isl" | "hi" | "en";
  input_text: string;
  output_text: string;
  confidence: number | null;
  created_at: string;
}

export interface CreateHistoryRequest {
  direction: HistoryEntry["direction"];
  source_language: HistoryEntry["source_language"];
  target_language: HistoryEntry["target_language"];
  input_text: string;
  output_text: string;
  confidence?: number | null;
}

export interface HistoryListResponse {
  items: HistoryEntry[];
  limit: number;
  skip: number;
}

export interface HistoryFilters {
  search?: string;
  language?: string;
  createdAfter?: string;
  createdBefore?: string;
}

function getErrorMessage(payload: unknown): string {
  if (
    typeof payload === "object" &&
    payload !== null &&
    "detail" in payload &&
    typeof payload.detail === "string"
  ) {
    return payload.detail;
  }
  return "The request could not be completed.";
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (
    init.body !== undefined &&
    !(typeof FormData !== "undefined" && init.body instanceof FormData)
  ) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: "include",
      headers
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new ApiError(0, "Could not connect to SignLingo. Check that the backend is running.");
    }
    throw error;
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (error) {
    if (!(error instanceof SyntaxError)) {
      throw error;
    }
    payload = null;
  }

  if (!response.ok) {
    throw new ApiError(response.status, getErrorMessage(payload));
  }

  return payload as T;
}

export async function getCurrentUser(): Promise<User> {
  const response = await apiRequest<AuthResponse>("/auth/me");
  return response.user;
}

export async function getTranslationHistory(
  filters: HistoryFilters = {}
): Promise<HistoryListResponse> {
  const query = new URLSearchParams({ limit: "50", skip: "0" });
  if (filters.search) {
    query.set("search", filters.search);
  }
  if (filters.language) {
    query.set("language", filters.language);
  }
  if (filters.createdAfter) {
    query.set("created_after", filters.createdAfter);
  }
  if (filters.createdBefore) {
    query.set("created_before", filters.createdBefore);
  }
  return apiRequest<HistoryListResponse>(`/history?${query.toString()}`);
}

export async function createTranslationHistory(
  payload: CreateHistoryRequest
): Promise<HistoryEntry> {
  return apiRequest<HistoryEntry>("/history", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function deleteTranslationHistoryEntry(id: string): Promise<void> {
  await apiRequest<void>(`/history/${encodeURIComponent(id)}`, { method: "DELETE" });
}
