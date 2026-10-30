import { afterEach, describe, expect, it, vi } from "vitest";
import { AudioCaptureService } from "./audio-capture-service";

const stopTrack = vi.fn();
const getUserMedia = vi.fn();
const originalMediaDevices = Object.getOwnPropertyDescriptor(navigator, "mediaDevices");
const originalBlobArrayBuffer = Object.getOwnPropertyDescriptor(Blob.prototype, "arrayBuffer");

class FixtureMediaRecorder {
  static isTypeSupported = vi.fn(() => false);
  state: RecordingState = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: BlobEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onstop: (() => void) | null = null;

  constructor() {}

  start() {
    this.state = "recording";
  }

  stop() {
    this.state = "inactive";
    this.ondataavailable?.({ data: new Blob(["recorded"]) } as BlobEvent);
    this.onstop?.();
  }
}

class FixtureAudioContext {
  async decodeAudioData() {
    const channel = new Float32Array(16_000).fill(0.1);
    return {
      duration: 1,
      numberOfChannels: 1,
      sampleRate: 16_000,
      length: channel.length,
      getChannelData: () => channel
    };
  }

  async close() {}
}

function configureBrowserMocks() {
  Object.defineProperty(Blob.prototype, "arrayBuffer", {
    configurable: true,
    value(this: Blob) {
      return new Promise<ArrayBuffer>((resolve, reject) => {
        const reader = new FileReader();
        reader.onerror = () => reject(reader.error);
        reader.onload = () => {
          if (reader.result instanceof ArrayBuffer) {
            resolve(reader.result);
          } else {
            reject(new Error("FileReader returned an invalid buffer."));
          }
        };
        reader.readAsArrayBuffer(this);
      });
    }
  });
  getUserMedia.mockResolvedValue({
    getTracks: () => [{ stop: stopTrack }]
  });
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia }
  });
  vi.stubGlobal("MediaRecorder", FixtureMediaRecorder);
  vi.stubGlobal("AudioContext", FixtureAudioContext);
}

describe("AudioCaptureService", () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
    if (originalMediaDevices) {
      Object.defineProperty(navigator, "mediaDevices", originalMediaDevices);
    } else {
      Reflect.deleteProperty(navigator, "mediaDevices");
    }
    if (originalBlobArrayBuffer) {
      Object.defineProperty(Blob.prototype, "arrayBuffer", originalBlobArrayBuffer);
    } else {
      Reflect.deleteProperty(Blob.prototype, "arrayBuffer");
    }
  });

  it("encodes temporary microphone audio as 16 kHz PCM WAV and releases the stream", async () => {
    configureBrowserMocks();
    const service = new AudioCaptureService();
    await service.start();

    const wav = await service.stop();
    const bytes = new Uint8Array(await wav.arrayBuffer());

    expect(wav.type).toBe("audio/wav");
    expect(new TextDecoder().decode(bytes.slice(0, 4))).toBe("RIFF");
    expect(new DataView(bytes.buffer).getUint32(24, true)).toBe(16_000);
    expect(stopTrack).toHaveBeenCalledOnce();
  });

  it("reports microphone permission denial with a safe error", async () => {
    configureBrowserMocks();
    getUserMedia.mockRejectedValue(new DOMException("denied", "NotAllowedError"));
    const service = new AudioCaptureService();

    await expect(service.start()).rejects.toMatchObject({
      code: "permission",
      message: "Microphone permission was denied."
    });
  });

  it("releases the stream and stops recording when cancelled", async () => {
    configureBrowserMocks();
    const service = new AudioCaptureService();
    await service.start();

    service.dispose();

    expect(stopTrack).toHaveBeenCalledOnce();
  });
});
