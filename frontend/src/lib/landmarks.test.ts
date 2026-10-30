import { describe, expect, it } from "vitest";
import {
  isGestureRecognitionResult,
  normalizeHandLandmarks,
  type RawLandmarkPoint
} from "@/lib/landmarks";

describe("normalizeHandLandmarks", () => {
  it("centers points on the wrist and scales the furthest point to unit distance", () => {
    const landmarks: RawLandmarkPoint[] = Array.from({ length: 21 }, (_, index) => ({
      x: index === 1 ? 3 : 2,
      y: index === 1 ? 4 : 2,
      z: 2
    }));

    const normalized = normalizeHandLandmarks(landmarks);

    expect(normalized).not.toBeNull();
    expect(normalized?.[0]).toEqual({ x: 0, y: 0, z: 0 });
    expect(normalized?.[1].x).toBeCloseTo(1 / Math.sqrt(5));
    expect(normalized?.[1].y).toBeCloseTo(2 / Math.sqrt(5));
    expect(Math.hypot(normalized?.[1].x ?? 0, normalized?.[1].y ?? 0)).toBeCloseTo(1);
  });

  it("rejects malformed or degenerate hands", () => {
    const degenerate = Array.from({ length: 21 }, () => ({ x: 0, y: 0, z: 0 }));
    const nonFinite = Array.from({ length: 21 }, () => ({ x: 0, y: 0, z: 0 }));
    nonFinite[4] = { x: Number.NaN, y: 0, z: 0 };

    expect(normalizeHandLandmarks(degenerate)).toBeNull();
    expect(normalizeHandLandmarks(nonFinite)).toBeNull();
    expect(normalizeHandLandmarks(degenerate.slice(0, 20))).toBeNull();
  });
});

describe("isGestureRecognitionResult", () => {
  it("accepts only the documented gesture result shape", () => {
    expect(
      isGestureRecognitionResult({
        type: "gesture_result",
        sequence_id: "sequence-1",
        status: "model_unavailable",
        label: null,
        confidence: null
      })
    ).toBe(true);
    expect(
      isGestureRecognitionResult({
        type: "gesture_result",
        sequence_id: "sequence-2",
        status: "classified",
        label: "hello",
        confidence: 0.9
      })
    ).toBe(true);
    expect(
      isGestureRecognitionResult({
        type: "gesture_result",
        sequence_id: "sequence-no-hands",
        status: "unknown",
        label: null,
        confidence: null
      })
    ).toBe(true);
    expect(
      isGestureRecognitionResult({
        type: "gesture_result",
        sequence_id: "sequence-3",
        status: "classified",
        label: null,
        confidence: null
      })
    ).toBe(false);
    expect(
      isGestureRecognitionResult({
        type: "gesture_result",
        sequence_id: "sequence-4",
        status: "unknown",
        label: null,
        confidence: Number.NaN
      })
    ).toBe(false);
    expect(isGestureRecognitionResult({ type: "gesture_result" })).toBe(false);
  });
});
