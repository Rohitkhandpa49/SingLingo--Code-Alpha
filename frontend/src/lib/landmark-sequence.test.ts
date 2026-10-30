import { describe, expect, it } from "vitest";
import { LandmarkSequenceBuilder, isValidLandmarkFrame } from "@/lib/landmark-sequence";
import type { LandmarkFrame } from "@/lib/landmarks";

function frame(value: number): LandmarkFrame {
  return {
    hands: [{
      handedness: "Right",
      points: Array.from({ length: 21 }, () => ({ x: value, y: 0, z: 0 })),
      wrist: { x: value, y: 0.5, z: 0 },
      confidence: 0.9
    }],
    hands_detected: 1
  };
}

describe("LandmarkSequenceBuilder", () => {
  it("emits bounded overlapping windows at the configured stride", () => {
    const builder = new LandmarkSequenceBuilder(3, 2);

    expect(builder.push(frame(0), 0)).toBeNull();
    expect(builder.push(frame(0.1), 100)).toBeNull();
    expect(builder.push(frame(0.2), 200)?.map((item) => item.hands[0].points[0].x))
      .toEqual([0, 0.1, 0.2]);
    expect(builder.push(frame(0.3), 300)).toBeNull();
    expect(builder.bufferedFrameCount).toBe(3);
    expect(builder.push(frame(0.4), 400)?.map((item) => item.hands[0].points[0].x))
      .toEqual([0.2, 0.3, 0.4]);
  });

  it("drops invalid and out-of-order frames and resets after a long gap", () => {
    const builder = new LandmarkSequenceBuilder(2, 1, 250);
    const invalid = frame(0.1);
    invalid.hands[0].points[4].x = Number.NaN;

    expect(isValidLandmarkFrame(invalid)).toBe(false);
    expect(builder.push(invalid, 10)).toBeNull();
    expect(builder.push(frame(0.1), 10)).toBeNull();
    expect(builder.push(frame(0.2), 9)).toBeNull();
    expect(builder.push(frame(0.3), 20)).toBeNull();
    expect(builder.push(frame(0.4), 30)?.length).toBe(2);
    expect(builder.push(frame(0.4), 400)).toBeNull();
    expect(builder.bufferedFrameCount).toBe(1);
  });

  it("resets sequence state when a session ends", () => {
    const builder = new LandmarkSequenceBuilder(2, 1);
    builder.push(frame(0.1), 10);
    builder.push(frame(0.2), 20);

    builder.reset();

    expect(builder.bufferedFrameCount).toBe(0);
    expect(builder.push(frame(0.3), 30)).toBeNull();
  });
});
