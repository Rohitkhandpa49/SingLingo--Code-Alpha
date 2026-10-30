export class CameraService {
  private activeStream: MediaStream | null = null;
  private pendingStart: { deviceId: string; promise: Promise<MediaStream> } | null = null;
  private generation = 0;

  async start(deviceId = ""): Promise<MediaStream> {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new DOMException("Camera access is not available in this browser.", "NotSupportedError");
    }

    if (this.activeStream?.getTracks().some((track) => track.readyState === "live")) {
      const currentDevice = this.activeStream.getVideoTracks()[0]?.getSettings().deviceId;
      if (deviceId && currentDevice && deviceId !== currentDevice) {
        throw new Error("Stop the active camera before selecting a different device.");
      }
      return this.activeStream;
    }
    if (this.pendingStart) {
      if (deviceId && this.pendingStart.deviceId && deviceId !== this.pendingStart.deviceId) {
        throw new Error("A camera request for a different device is already in progress.");
      }
      return this.pendingStart.promise;
    }

    const generation = this.generation;
    const video: MediaTrackConstraints = deviceId
      ? { deviceId: { exact: deviceId } }
      : { facingMode: "user" };
    const request = navigator.mediaDevices.getUserMedia({ audio: false, video });
    const promise = request
      .then((stream) => {
        if (generation !== this.generation) {
          stream.getTracks().forEach((track) => track.stop());
          throw new DOMException("Camera request was canceled.", "AbortError");
        }
        this.activeStream = stream;
        return stream;
      })
      .finally(() => {
        if (this.pendingStart?.promise === promise) {
          this.pendingStart = null;
        }
      });
    this.pendingStart = { deviceId, promise };
    return promise;
  }

  async enumerateVideoDevices(): Promise<MediaDeviceInfo[]> {
    if (!navigator.mediaDevices?.enumerateDevices) {
      return [];
    }
    return (await navigator.mediaDevices.enumerateDevices())
      .filter((device) => device.kind === "videoinput");
  }

  stop(): void {
    this.generation += 1;
    const stream = this.activeStream;
    this.activeStream = null;
    stream?.getTracks().forEach((track) => track.stop());
  }
}
