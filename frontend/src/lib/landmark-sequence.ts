import type { HandLandmarks, LandmarkFrame, LandmarkPoint } from "@/lib/landmarks";

function isValidPoint(point: unknown): point is LandmarkPoint {
  if (typeof point !== "object" || point === null) {
    return false;
  }
  if (!("x" in point) || !("y" in point) || !("z" in point)) {
    return false;
  }
  const { x, y, z } = point;
  return (
    typeof x === "number" &&
    typeof y === "number" &&
    typeof z === "number" &&
    Number.isFinite(x) &&
    Number.isFinite(y) &&
    Number.isFinite(z) &&
    Math.abs(x) <= 1 &&
    Math.abs(y) <= 1 &&
    Math.abs(z) <= 1
  );
}

function isValidHand(hand: unknown): hand is HandLandmarks {
  if (
    typeof hand !== "object" ||
    hand === null ||
    !("handedness" in hand) ||
    !("points" in hand)
  ) {
    return false;
  }
  const handedness = hand.handedness;
  const points = hand.points;
  if (
    (handedness !== "Left" && handedness !== "Right") ||
    !Array.isArray(points) ||
    points.length !== 21 ||
    !points.every(isValidPoint)
  ) {
    return false;
  }
  const wrist = "wrist" in hand ? hand.wrist : undefined;
  const confidence = "confidence" in hand ? hand.confidence : undefined;
  return (wrist === undefined || isValidPoint(wrist)) &&
    (confidence === undefined ||
      (typeof confidence === "number" &&
        Number.isFinite(confidence) &&
        confidence >= 0 &&
        confidence <= 1));
}

export function isValidLandmarkFrame(frame: unknown): frame is LandmarkFrame {
  if (
    typeof frame !== "object" ||
    frame === null ||
    !("hands" in frame)
  ) {
    return false;
  }
  const hands = frame.hands;
  if (!Array.isArray(hands) || hands.length > 2 || !hands.every(isValidHand)) {
    return false;
  }
  const handedness = hands.map(({ handedness: side }) => side);
  const handsDetected = "hands_detected" in frame ? frame.hands_detected : undefined;
  return (
    new Set(handedness).size === handedness.length &&
    (handsDetected === undefined ||
      (typeof handsDetected === "number" && handsDetected === hands.length))
  );
}

export class LandmarkSequenceBuilder {
  private readonly frames: LandmarkFrame[] = [];
  private lastCaptureTime: number | null = null;
  private framesSinceSequence = 0;
  private hasEmittedSequence = false;

  constructor(
    private readonly windowLength = 30,
    private readonly stride = 10,
    private readonly maxFrameGapMs = 1000
  ) {
    if (!Number.isInteger(windowLength) || windowLength < 1) {
      throw new RangeError("windowLength must be a positive integer");
    }
    if (!Number.isInteger(stride) || stride < 1) {
      throw new RangeError("stride must be a positive integer");
    }
    if (!Number.isFinite(maxFrameGapMs) || maxFrameGapMs <= 0) {
      throw new RangeError("maxFrameGapMs must be positive");
    }
  }

  push(frame: LandmarkFrame, captureTimeMs: number): LandmarkFrame[] | null {
    if (!isValidLandmarkFrame(frame) || !Number.isFinite(captureTimeMs)) {
      this.reset();
      return null;
    }
    if (this.lastCaptureTime !== null && captureTimeMs <= this.lastCaptureTime) {
      this.reset();
      return null;
    }
    if (
      this.lastCaptureTime !== null &&
      captureTimeMs - this.lastCaptureTime > this.maxFrameGapMs
    ) {
      this.reset();
    }

    this.lastCaptureTime = captureTimeMs;
    this.frames.push({
      hands: frame.hands.map((hand) => ({
        ...hand,
        points: hand.points.map((point) => ({ ...point })),
        ...(hand.wrist ? { wrist: { ...hand.wrist } } : {})
      })),
      hands_detected: frame.hands_detected
    });
    if (this.frames.length > this.windowLength) {
      this.frames.shift();
    }
    if (this.frames.length < this.windowLength) {
      return null;
    }
    if (this.hasEmittedSequence) {
      this.framesSinceSequence += 1;
      if (this.framesSinceSequence < this.stride) {
        return null;
      }
    }
    this.hasEmittedSequence = true;
    this.framesSinceSequence = 0;
    return this.frames.map((value) => ({
      hands: value.hands.map((hand) => ({
        ...hand,
        points: hand.points.map((point) => ({ ...point })),
        ...(hand.wrist ? { wrist: { ...hand.wrist } } : {})
      })),
      hands_detected: value.hands_detected
    }));
  }

  reset(): void {
    this.frames.length = 0;
    this.lastCaptureTime = null;
    this.framesSinceSequence = 0;
    this.hasEmittedSequence = false;
  }

  get bufferedFrameCount(): number {
    return this.frames.length;
  }
}
