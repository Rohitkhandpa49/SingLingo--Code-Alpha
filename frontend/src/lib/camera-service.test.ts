import { beforeEach, describe, expect, it, vi } from "vitest";
import { CameraService } from "@/lib/camera-service";

describe("CameraService", () => {
  const getUserMedia = vi.fn();
  const enumerateDevices = vi.fn();
  const stopTrack = vi.fn();
  let stream: MediaStream;

  beforeEach(() => {
    vi.clearAllMocks();
    stopTrack.mockReset();
    stream = {
      getTracks: () => [{ readyState: "live", stop: stopTrack }] as unknown as MediaStreamTrack[],
      getVideoTracks: () => [{
        readyState: "live",
        getSettings: () => ({ deviceId: "camera-1" }),
        stop: stopTrack
      }] as unknown as MediaStreamTrack[]
    } as MediaStream;
    getUserMedia.mockResolvedValue(stream);
    enumerateDevices.mockResolvedValue([
      { kind: "videoinput", deviceId: "camera-1" },
      { kind: "audioinput", deviceId: "microphone-1" }
    ]);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia, enumerateDevices }
    });
  });

  it("reuses one active stream and stops every track", async () => {
    const service = new CameraService();

    const first = await service.start();
    const second = await service.start();

    expect(first).toBe(stream);
    expect(second).toBe(stream);
    expect(getUserMedia).toHaveBeenCalledOnce();
    service.stop();
    expect(stopTrack).toHaveBeenCalledOnce();
  });

  it("shares a pending camera request between callers", async () => {
    let resolveRequest!: (value: MediaStream) => void;
    getUserMedia.mockReturnValueOnce(
      new Promise<MediaStream>((resolve) => {
        resolveRequest = resolve;
      })
    );
    const service = new CameraService();

    const first = service.start("camera-1");
    const second = service.start("camera-1");
    resolveRequest(stream);

    await expect(first).resolves.toBe(stream);
    await expect(second).resolves.toBe(stream);
    expect(getUserMedia).toHaveBeenCalledOnce();
    expect(getUserMedia).toHaveBeenCalledWith({
      audio: false,
      video: { deviceId: { exact: "camera-1" } }
    });
  });

  it("stops a stream that resolves after cancellation", async () => {
    let resolveRequest!: (value: MediaStream) => void;
    getUserMedia.mockReturnValueOnce(
      new Promise<MediaStream>((resolve) => {
        resolveRequest = resolve;
      })
    );
    const service = new CameraService();
    const start = service.start();
    service.stop();
    resolveRequest(stream);

    await expect(start).rejects.toMatchObject({ name: "AbortError" });
    expect(stopTrack).toHaveBeenCalledOnce();
  });

  it("lists only video devices", async () => {
    const devices = await new CameraService().enumerateVideoDevices();

    expect(devices).toEqual([{ kind: "videoinput", deviceId: "camera-1" }]);
  });
});
