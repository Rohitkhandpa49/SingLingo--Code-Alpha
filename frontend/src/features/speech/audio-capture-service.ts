export type AudioCaptureErrorCode =
  | "unsupported"
  | "permission"
  | "unavailable"
  | "recording"
  | "too_long"
  | "too_large"
  | "encoding";

export class AudioCaptureError extends Error {
  constructor(
    readonly code: AudioCaptureErrorCode,
    message: string
  ) {
    super(message);
    this.name = "AudioCaptureError";
  }
}

const MAX_RECORDING_SECONDS = 60;
const MAX_CAPTURE_BYTES = 8_000_000;
const TARGET_SAMPLE_RATE = 16_000;
const RECORDING_MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"];

export class AudioCaptureService {
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: Blob[] = [];
  private byteCount = 0;
  private overflow = false;
  private completion: Promise<Blob> | null = null;
  private resolveCompletion: ((blob: Blob) => void) | null = null;
  private rejectCompletion: ((error: Error) => void) | null = null;
  private maximumDurationTimer: number | null = null;
  private onError: ((error: AudioCaptureError) => void) | null = null;

  async start(onError?: (error: AudioCaptureError) => void): Promise<void> {
    this.onError = onError ?? null;
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      throw new AudioCaptureError("unsupported", "Microphone recording is not supported here.");
    }

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      const name = error instanceof DOMException ? error.name : "";
      this.onError = null;
      if (name === "NotAllowedError" || name === "SecurityError") {
        throw new AudioCaptureError("permission", "Microphone permission was denied.");
      }
      if (name === "NotFoundError" || name === "OverconstrainedError") {
        throw new AudioCaptureError("unavailable", "No usable microphone was found.");
      }
      throw new AudioCaptureError("unavailable", "The microphone could not be started.");
    }

    try {
      const mimeType = RECORDING_MIME_TYPES.find((type) =>
        MediaRecorder.isTypeSupported(type)
      );
      this.recorder = mimeType
        ? new MediaRecorder(this.stream, { mimeType })
        : new MediaRecorder(this.stream);
      this.chunks = [];
      this.byteCount = 0;
      this.overflow = false;
      this.completion = new Promise<Blob>((resolve, reject) => {
        this.resolveCompletion = resolve;
        this.rejectCompletion = reject;
      });
      void this.completion.catch(() => undefined);
      this.recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size === 0 || this.overflow) {
          return;
        }
        this.byteCount += event.data.size;
        if (this.byteCount > MAX_CAPTURE_BYTES) {
          this.overflow = true;
          this.chunks = [];
          if (this.recorder?.state === "recording") {
            this.recorder.stop();
          }
          return;
        }
        this.chunks.push(event.data);
      };
      this.recorder.onerror = () => {
        this.fail(
          new AudioCaptureError("recording", "The browser could not record microphone audio.")
        );
      };
      this.recorder.onstop = () => {
        void this.finishRecording();
      };
      this.recorder.start(500);
      this.maximumDurationTimer = window.setTimeout(() => {
        if (this.recorder?.state === "recording") {
          this.recorder.stop();
        }
      }, MAX_RECORDING_SECONDS * 1000);
    } catch (error) {
      this.cleanup();
      if (error instanceof AudioCaptureError) {
        throw error;
      }
      throw new AudioCaptureError("recording", "The browser could not start audio recording.");
    }
  }

  async stop(): Promise<Blob> {
    if (!this.recorder || !this.completion) {
      throw new AudioCaptureError("recording", "There is no active recording to stop.");
    }
    const completion = this.completion;
    if (this.recorder.state === "recording") {
      this.recorder.stop();
    }
    return completion;
  }

  dispose(): void {
    const recorder = this.recorder;
    if (recorder) {
      recorder.ondataavailable = null;
      recorder.onerror = null;
      recorder.onstop = null;
      if (recorder.state === "recording") {
        recorder.stop();
      }
    }
    this.rejectCompletion?.(
      new AudioCaptureError("recording", "Recording was cancelled.")
    );
    this.cleanup();
  }

  private async finishRecording(): Promise<void> {
    if (this.overflow) {
      this.fail(
        new AudioCaptureError("too_large", "Recording exceeded the browser audio size limit.")
      );
      return;
    }
    try {
      const recorded = new Blob(this.chunks, {
        type: this.recorder?.mimeType || "audio/webm"
      });
      const wav = await encodePcmWav(recorded);
      if (wav.size > 4_000_000) {
        throw new AudioCaptureError("too_large", "Recording exceeds the upload size limit.");
      }
      this.resolveCompletion?.(wav);
    } catch (error) {
      this.fail(
        error instanceof AudioCaptureError
          ? error
          : new AudioCaptureError("encoding", "Recorded audio could not be prepared.")
      );
      return;
    }
    this.cleanup();
  }

  private fail(error: AudioCaptureError): void {
    this.rejectCompletion?.(error);
    this.onError?.(error);
    this.cleanup();
  }

  private cleanup(): void {
    if (this.maximumDurationTimer !== null) {
      window.clearTimeout(this.maximumDurationTimer);
      this.maximumDurationTimer = null;
    }
    for (const track of this.stream?.getTracks() ?? []) {
      track.stop();
    }
    this.stream = null;
    this.recorder = null;
    this.chunks = [];
    this.onError = null;
    this.completion = null;
    this.resolveCompletion = null;
    this.rejectCompletion = null;
  }
}

async function encodePcmWav(recording: Blob): Promise<Blob> {
  let context: AudioContext | null = null;
  try {
    context = new AudioContext();
    const audio = await context.decodeAudioData(await recording.arrayBuffer());
    if (audio.duration <= 0 || audio.duration > MAX_RECORDING_SECONDS) {
      throw new AudioCaptureError("too_long", "Recording must be no longer than 60 seconds.");
    }
    const channelData = Array.from({ length: audio.numberOfChannels }, (_, index) =>
      audio.getChannelData(index)
    );
    const frameCount = Math.ceil(audio.duration * TARGET_SAMPLE_RATE);
    const pcm = new ArrayBuffer(44 + frameCount * 2);
    const view = new DataView(pcm);
    writeAscii(view, 0, "RIFF");
    view.setUint32(4, pcm.byteLength - 8, true);
    writeAscii(view, 8, "WAVE");
    writeAscii(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, TARGET_SAMPLE_RATE, true);
    view.setUint32(28, TARGET_SAMPLE_RATE * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeAscii(view, 36, "data");
    view.setUint32(40, frameCount * 2, true);

    for (let frame = 0; frame < frameCount; frame += 1) {
      const position = (frame * audio.sampleRate) / TARGET_SAMPLE_RATE;
      const left = Math.min(Math.floor(position), audio.length - 1);
      const right = Math.min(left + 1, audio.length - 1);
      const weight = position - left;
      const mono = channelData.reduce((sum, channel) => {
        const sample = channel[left] * (1 - weight) + channel[right] * weight;
        return sum + sample / channelData.length;
      }, 0);
      const clipped = Math.max(-1, Math.min(1, mono));
      view.setInt16(
        44 + frame * 2,
        clipped < 0 ? clipped * 32768 : clipped * 32767,
        true
      );
    }
    return new Blob([pcm], { type: "audio/wav" });
  } catch (error) {
    if (error instanceof AudioCaptureError) {
      throw error;
    }
    throw new AudioCaptureError("encoding", "Recorded audio could not be decoded by this browser.");
  } finally {
    await context?.close();
  }
}

function writeAscii(view: DataView, offset: number, value: string): void {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}
