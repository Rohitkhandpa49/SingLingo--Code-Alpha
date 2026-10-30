export interface LandmarkPoint {
  x: number;
  y: number;
  z: number;
}

export interface HandLandmarks {
  handedness: "Left" | "Right";
  points: LandmarkPoint[];
  wrist?: LandmarkPoint;
  confidence?: number;
}

export interface LandmarkFrame {
  hands: HandLandmarks[];
  hands_detected?: number;
}

export const LANDMARK_SCHEMA_VERSION = "1.0" as const;

export interface ISLTranslationResult {
  type: "isl_translation";
  translation_id: string;
  status:
    | "success"
    | "partial"
    | "unknown_gesture"
    | "low_confidence"
    | "unsupported"
    | "processing_error";
  session_id: string | null;
  sequence_id: string;
  recognized_signs: Array<{
    sign_id: string;
    sign_name: string;
    category: string;
    confidence: number;
    translation: string | null;
  }>;
  interpreted_text: string;
  language: "en" | "hi";
  confidence: number | null;
  translation_level:
    | "single_sign"
    | "fingerspelling"
    | "number"
    | "phrase"
    | "sentence"
    | "partial";
  unsupported_segments: Array<{ sign_id: string | null; reason: string }>;
  model_version: string | null;
  vocabulary_version: string | null;
  timestamp: string;
}

export interface GestureRecognitionResult {
  type: "gesture_result";
  sequence_id: string;
  status: "classified" | "unknown" | "model_unavailable";
  label: string | null;
  confidence: number | null;
  model_version?: string | null;
  translation?: ISLTranslationResult;
}

export interface RawLandmarkPoint {
  x: number;
  y: number;
  z: number;
}

function isValidConfidence(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

function isISLTranslationResult(value: unknown): value is ISLTranslationResult {
  if (
    typeof value !== "object" ||
    value === null ||
    !("type" in value) ||
    value.type !== "isl_translation" ||
    !("translation_id" in value) ||
    typeof value.translation_id !== "string" ||
    !("sequence_id" in value) ||
    typeof value.sequence_id !== "string" ||
    !("status" in value) ||
    !(
      value.status === "success" ||
      value.status === "partial" ||
      value.status === "unknown_gesture" ||
      value.status === "low_confidence" ||
      value.status === "unsupported" ||
      value.status === "processing_error"
    ) ||
    !("interpreted_text" in value) ||
    typeof value.interpreted_text !== "string" ||
    !("language" in value) ||
    (value.language !== "en" && value.language !== "hi") ||
    !("recognized_signs" in value) ||
    !Array.isArray(value.recognized_signs) ||
    !("unsupported_segments" in value) ||
    !Array.isArray(value.unsupported_segments) ||
    !("translation_level" in value) ||
    !(
      value.translation_level === "single_sign" ||
      value.translation_level === "fingerspelling" ||
      value.translation_level === "number" ||
      value.translation_level === "phrase" ||
      value.translation_level === "sentence" ||
      value.translation_level === "partial"
    ) ||
    !("confidence" in value) ||
    (value.confidence !== null && !isValidConfidence(value.confidence)) ||
    !("session_id" in value) ||
    (value.session_id !== null && typeof value.session_id !== "string") ||
    !("model_version" in value) ||
    (value.model_version !== null && typeof value.model_version !== "string") ||
    !("vocabulary_version" in value) ||
    (value.vocabulary_version !== null && typeof value.vocabulary_version !== "string") ||
    !("timestamp" in value) ||
    typeof value.timestamp !== "string"
  ) {
    return false;
  }
  return (
    value.recognized_signs.every(
      (sign) =>
        typeof sign === "object" &&
        sign !== null &&
        "sign_id" in sign &&
        typeof sign.sign_id === "string" &&
        "sign_name" in sign &&
        typeof sign.sign_name === "string" &&
        "category" in sign &&
        typeof sign.category === "string" &&
        "confidence" in sign &&
        isValidConfidence(sign.confidence) &&
        "translation" in sign &&
        (typeof sign.translation === "string" || sign.translation === null)
    ) &&
    value.unsupported_segments.every(
      (segment) =>
        typeof segment === "object" &&
        segment !== null &&
        "sign_id" in segment &&
        (typeof segment.sign_id === "string" || segment.sign_id === null) &&
        "reason" in segment &&
        typeof segment.reason === "string"
    )
  );
}

export function normalizeHandLandmarks(
  landmarks: readonly RawLandmarkPoint[]
): LandmarkPoint[] | null {
  if (
    landmarks.length !== 21 ||
    landmarks.some(
      ({ x, y, z }) => !Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)
    )
  ) {
    return null;
  }

  const wrist = landmarks[0];
  const scale = Math.max(
    ...landmarks.map(({ x, y, z }) => {
      const dx = x - wrist.x;
      const dy = y - wrist.y;
      const dz = z - wrist.z;
      return Math.sqrt(dx * dx + dy * dy + dz * dz);
    })
  );
  if (scale <= Number.EPSILON) {
    return null;
  }

  return landmarks.map(({ x, y, z }) => ({
    x: (x - wrist.x) / scale,
    y: (y - wrist.y) / scale,
    z: (z - wrist.z) / scale
  }));
}

export function isGestureRecognitionResult(
  value: unknown
): value is GestureRecognitionResult {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  if (
    !("type" in value) ||
    value.type !== "gesture_result" ||
    !("sequence_id" in value) ||
    typeof value.sequence_id !== "string" ||
    !("status" in value) ||
    !("label" in value) ||
    !("confidence" in value)
  ) {
    return false;
  }
  if (
    "translation" in value &&
    !isISLTranslationResult(value.translation)
  ) {
    return false;
  }
  if (
    "model_version" in value &&
    value.model_version !== null &&
    typeof value.model_version !== "string"
  ) {
    return false;
  }

  if (value.status === "classified") {
    return (
      typeof value.label === "string" &&
      isValidConfidence(value.confidence)
    );
  }
  if (value.status === "unknown") {
    return value.label === null &&
      (value.confidence === null || isValidConfidence(value.confidence));
  }
  return value.status === "model_unavailable" && value.label === null && value.confidence === null;
}

export function createGestureWebSocket(): WebSocket {
  const baseUrl = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000";
  const socketUrl = new URL("/api/v1/ws/gestures", `${baseUrl.replace(/\/+$/, "")}/`);
  socketUrl.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return new WebSocket(socketUrl);
}
