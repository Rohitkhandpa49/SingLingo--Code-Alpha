import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SignCamera } from "./sign-camera";

const mediaPipeMocks = vi.hoisted(() => ({
  resolveVision: vi.fn(),
  createDetector: vi.fn()
}));

vi.mock("@mediapipe/tasks-vision", () => ({
  FilesetResolver: { forVisionTasks: mediaPipeMocks.resolveVision },
  HandLandmarker: {
    createFromOptions: mediaPipeMocks.createDetector,
    HAND_CONNECTIONS: []
  }
}));

class MockWebSocket {
  static OPEN = 1;
  static instances: MockWebSocket[] = [];
  readyState = MockWebSocket.OPEN;
  bufferedAmount = 0;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<unknown>) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  send = vi.fn();

  constructor() {
    MockWebSocket.instances.push(this);
    queueMicrotask(() => this.onopen?.(new Event("open")));
  }

  close(code = 1000): void {
    this.readyState = 3;
    this.onclose?.({ code } as CloseEvent);
  }
}

describe("SignCamera", () => {
  const stopTrack = vi.fn();
  const getUserMedia = vi.fn();
  const enumerateDevices = vi.fn();
  const detectorClose = vi.fn();
  const frameCallbacks: FrameRequestCallback[] = [];
  let detectionResult: {
    landmarks: { x: number; y: number; z: number }[][];
    handedness: { categoryName: string; score: number }[][];
  };

  beforeEach(() => {
    vi.clearAllMocks();
    frameCallbacks.length = 0;
    MockWebSocket.instances.length = 0;
    mediaPipeMocks.resolveVision.mockResolvedValue({});
    mediaPipeMocks.createDetector.mockResolvedValue({
      detectForVideo: vi.fn(() => detectionResult),
      close: detectorClose
    });
    detectionResult = { landmarks: [], handedness: [] };
    stopTrack.mockReset();
    enumerateDevices.mockResolvedValue([]);
    getUserMedia.mockReset();
    const track = {
      stop: stopTrack,
      getSettings: () => ({ deviceId: "camera-1" }),
      addEventListener: vi.fn()
    };
    const stream = {
      getTracks: () => [track],
      getVideoTracks: () => [track]
    } as unknown as MediaStream;
    getUserMedia.mockResolvedValue(stream);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia, enumerateDevices }
    });
    vi.stubGlobal("WebSocket", MockWebSocket);
    vi.stubGlobal("crypto", { randomUUID: () => "00000000-0000-0000-0000-000000000001" });
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      frameCallbacks.push(callback);
      return frameCallbacks.length;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
    Object.defineProperty(HTMLMediaElement.prototype, "readyState", {
      configurable: true,
      get: () => HTMLMediaElement.HAVE_CURRENT_DATA
    });
    Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
      configurable: true,
      get: () => 640
    });
    Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
      configurable: true,
      get: () => 480
    });
    const context = {
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn()
    } as unknown as CanvasRenderingContext2D;
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(context);
  });

  it("requests camera permission, starts local detection, and stops every track", async () => {
    render(<SignCamera onRecognition={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Start hand tracking" }));
    await screen.findByRole("button", { name: "Stop camera" });

    expect(getUserMedia).toHaveBeenCalledWith({
      audio: false,
      video: { facingMode: "user" }
    });
    expect(mediaPipeMocks.createDetector).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Stop camera" }));
    expect(stopTrack).toHaveBeenCalledOnce();
    expect(detectorClose).toHaveBeenCalledOnce();
  });

  it("reports denied camera permission and allows retry", async () => {
    getUserMedia.mockRejectedValueOnce(new DOMException("Denied", "NotAllowedError"));
    render(<SignCamera onRecognition={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Start hand tracking" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/permission was denied/i);
    expect(screen.getByRole("button", { name: "Retry camera" })).toBeEnabled();
  });

  it("reports an unavailable camera", async () => {
    getUserMedia.mockRejectedValueOnce(new DOMException("Missing", "NotFoundError"));
    render(<SignCamera onRecognition={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Start hand tracking" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/No camera matched/i);
  });

  it("cleans up the stream and reports MediaPipe initialization failure", async () => {
    mediaPipeMocks.resolveVision.mockRejectedValueOnce(new Error("MediaPipe asset load failed"));
    render(<SignCamera onRecognition={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Start hand tracking" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/MediaPipe could not initialize/i);
    await waitFor(() => expect(stopTrack).toHaveBeenCalledOnce());
  });

  it("shows a no-hands status when the detector returns no hands", async () => {
    render(<SignCamera onRecognition={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Start hand tracking" }));
    await screen.findByRole("button", { name: "Stop camera" });

    act(() => frameCallbacks.at(-1)?.(100));

    expect(await screen.findByText(/No hands detected/)).toBeInTheDocument();
  });

  it("reports the count and confidence of detected hands", async () => {
    const makeHand = (offset: number) =>
      Array.from({ length: 21 }, (_, index) => ({
        x: offset + index * 0.01,
        y: 0.5 + index * 0.005,
        z: 0
      }));
    detectionResult = {
      landmarks: [makeHand(0.1), makeHand(0.3)],
      handedness: [
        [{ categoryName: "Left", score: 0.8 }],
        [{ categoryName: "Right", score: 0.9 }]
      ]
    };
    render(<SignCamera onRecognition={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Start hand tracking" }));
    await screen.findByRole("button", { name: "Stop camera" });

    act(() => frameCallbacks.at(-1)?.(100));

    expect(await screen.findByText(/2 hands detected/)).toBeInTheDocument();
    expect(screen.getByText(/Average detection confidence 85%/)).toBeInTheDocument();
  });

  it("stops the stream and closes MediaPipe when unmounted", async () => {
    const { unmount } = render(<SignCamera onRecognition={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Start hand tracking" }));
    await screen.findByRole("button", { name: "Stop camera" });

    unmount();

    expect(stopTrack).toHaveBeenCalledOnce();
    expect(detectorClose).toHaveBeenCalledOnce();
  });

  it("reconnects the gesture WebSocket after an unexpected disconnect", async () => {
    render(<SignCamera onRecognition={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Start hand tracking" }));
    await screen.findByRole("button", { name: "Stop camera" });
    expect(MockWebSocket.instances).toHaveLength(1);

    act(() => MockWebSocket.instances[0].close(1006));
    expect(screen.getByText(/Connecting to the gesture service/)).toBeInTheDocument();

    await new Promise((resolve) => setTimeout(resolve, 600));

    expect(MockWebSocket.instances).toHaveLength(2);
  });
});
