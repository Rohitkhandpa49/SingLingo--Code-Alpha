"use client";

import { useEffect, useRef, useState } from "react";
import type {
  HandLandmarker as HandLandmarkerInstance,
  HandLandmarkerResult
} from "@mediapipe/tasks-vision";
import { Camera, CircleStop, Pause, Play, ShieldCheck } from "lucide-react";
import {
  createGestureWebSocket,
  isGestureRecognitionResult,
  LANDMARK_SCHEMA_VERSION,
  normalizeHandLandmarks,
  type GestureRecognitionResult,
  type HandLandmarks,
  type LandmarkFrame
} from "@/lib/landmarks";
import { LandmarkSequenceBuilder } from "@/lib/landmark-sequence";
import { CameraService } from "@/lib/camera-service";

type CameraState = "idle" | "loading" | "live" | "paused";
type ConnectionState = "idle" | "connecting" | "connected" | "disconnected" | "unauthorized";
type Props = Readonly<{
  onRecognition: (result: GestureRecognitionResult | null) => void;
  targetLanguage?: "en" | "hi";
}>;

const MEDIAPIPE_WASM_URL =
  process.env.NEXT_PUBLIC_MEDIAPIPE_WASM_URL ??
  "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@1.2.0/wasm";
const HAND_LANDMARKER_MODEL_URL =
  process.env.NEXT_PUBLIC_HAND_LANDMARKER_MODEL_URL ??
  "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task";
const SAMPLE_INTERVAL_MS = 100;
const SEQUENCE_LENGTH = 30;
const SEQUENCE_STRIDE = 10;
const MAX_SOCKET_BUFFERED_BYTES = 250_000;
const MAX_RECONNECT_ATTEMPTS = 5;

function normalizeDetectedHands(result: HandLandmarkerResult): HandLandmarks[] {
  return result.landmarks.flatMap((landmarks, index) => {
    const category = result.handedness[index]?.[0];
    const handedness = category?.categoryName;
    if (handedness !== "Left" && handedness !== "Right") {
      return [];
    }

    const points = normalizeHandLandmarks(landmarks);
    const wrist = landmarks[0];
    if (
      !points ||
      !wrist ||
      !Number.isFinite(category.score) ||
      category.score < 0 ||
      category.score > 1
    ) {
      return [];
    }
    return [{
      handedness,
      points,
      wrist: { x: wrist.x, y: wrist.y, z: wrist.z },
      confidence: category.score
    }];
  });
}

function drawLandmarks(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  hands: readonly (readonly { x: number; y: number }[])[],
  connections: readonly { start: number; end: number }[]
) {
  const context = canvas.getContext("2d");
  if (!context || video.videoWidth === 0 || video.videoHeight === 0) {
    return;
  }

  if (canvas.width !== video.videoWidth || canvas.height !== video.videoHeight) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
  }
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.lineWidth = Math.max(2, canvas.width / 240);
  context.strokeStyle = "#69f0c2";
  context.fillStyle = "#ffffff";

  for (const hand of hands) {
    context.beginPath();
    for (const connection of connections) {
      const start = hand[connection.start];
      const end = hand[connection.end];
      if (!start || !end) {
        continue;
      }
      context.moveTo(start.x * canvas.width, start.y * canvas.height);
      context.lineTo(end.x * canvas.width, end.y * canvas.height);
    }
    context.stroke();

    for (const point of hand) {
      context.beginPath();
      context.arc(
        point.x * canvas.width,
        point.y * canvas.height,
        Math.max(3, canvas.width / 160),
        0,
        Math.PI * 2
      );
      context.fill();
    }
  }
}

function connectionMessage(state: ConnectionState): string {
  switch (state) {
    case "connecting":
      return "Connecting to the gesture service…";
    case "connected":
      return "Landmark sequences are connected to SignLingo.";
    case "unauthorized":
      return "Sign in to send landmark sequences for inference.";
    case "disconnected":
      return "Gesture service is unavailable. Landmark detection remains local.";
    default:
      return "Gesture service is not connected.";
  }
}

function cameraStartError(error: unknown): string {
  if (error instanceof DOMException) {
    switch (error.name) {
      case "NotAllowedError":
      case "SecurityError":
        return "Camera permission was denied. Allow camera access in your browser settings, then retry.";
      case "NotFoundError":
      case "OverconstrainedError":
        return "No camera matched the selected device. Choose another camera or reconnect it.";
      case "NotReadableError":
      case "AbortError":
        return "The camera could not start because it may be in use by another application.";
      default:
        return `Camera or hand tracking could not start: ${error.message}`;
    }
  }
  if (
    error instanceof Error &&
    (error.message.includes("MediaPipe") || error.message.includes("FilesetResolver"))
  ) {
    return `MediaPipe could not initialize. Check the configured model and WASM asset URLs. ${error.message}`;
  }
  return error instanceof Error
    ? `Hand tracking could not start: ${error.message}`
    : "Hand tracking could not start. Check camera access and try again.";
}

export function SignCamera({ onRecognition, targetLanguage = "en" }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraServiceRef = useRef(new CameraService());
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<HandLandmarkerInstance | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const connectionsRef = useRef<readonly { start: number; end: number }[]>([]);
  const animationFrameRef = useRef<number | null>(null);
  const sequenceBuilderRef = useRef(new LandmarkSequenceBuilder(SEQUENCE_LENGTH, SEQUENCE_STRIDE));
  const sessionIdRef = useRef("");
  const sequenceNumberRef = useRef(0);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const shouldReconnectRef = useRef(false);
  const recognitionEnabledRef = useRef(false);
  const overlayEnabledRef = useRef(true);
  const targetLanguageRef = useRef(targetLanguage);
  const lastSampleTimeRef = useRef(0);
  const startTokenRef = useRef(0);
  const isMountedRef = useRef(true);
  const [cameraState, setCameraState] = useState<CameraState>("idle");
  const [connectionState, setConnectionState] = useState<ConnectionState>("idle");
  const [detectedHandCount, setDetectedHandCount] = useState(0);
  const [detectionConfidence, setDetectionConfidence] = useState<number | null>(null);
  const [cameraError, setCameraError] = useState("");
  const [cameraDevices, setCameraDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [overlayEnabled, setOverlayEnabled] = useState(true);
  const [recognitionEnabled, setRecognitionEnabled] = useState(true);

  useEffect(() => {
    targetLanguageRef.current = targetLanguage;
  }, [targetLanguage]);

  useEffect(() => {
    const cameraService = cameraServiceRef.current;
    const sequenceBuilder = sequenceBuilderRef.current;
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      startTokenRef.current += 1;
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      detectorRef.current?.close();
      cameraService.stop();
      streamRef.current = null;
      shouldReconnectRef.current = false;
      recognitionEnabledRef.current = false;
      sequenceBuilder.reset();
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
      }
      socketRef.current?.close(1000, "Camera component unmounted");
    };
  }, []);

  function scheduleGestureReconnect() {
    if (
      !shouldReconnectRef.current ||
      !streamRef.current ||
      reconnectTimerRef.current !== null
    ) {
      return;
    }
    if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
      setConnectionState("disconnected");
      return;
    }
    reconnectAttemptsRef.current += 1;
    const delay = Math.min(30_000, 500 * 2 ** (reconnectAttemptsRef.current - 1));
    setConnectionState("connecting");
    reconnectTimerRef.current = setTimeout(() => {
      reconnectTimerRef.current = null;
      if (shouldReconnectRef.current && streamRef.current) {
        connectGestureService();
      }
    }, delay);
  }

  function connectGestureService() {
    try {
      const socket = createGestureWebSocket();
      socketRef.current = socket;
      setConnectionState("connecting");
      socket.onopen = () => {
        if (isMountedRef.current && socketRef.current === socket) {
          setConnectionState("connected");
        }
      };
      socket.onmessage = (event: MessageEvent<unknown>) => {
        if (typeof event.data !== "string") {
          return;
        }
        let message: unknown;
        try {
          message = JSON.parse(event.data);
        } catch (error) {
          if (error instanceof SyntaxError) {
            if (isMountedRef.current) {
              setCameraError("The gesture service returned an invalid response.");
            }
            return;
          }
          throw error;
        }
        if (
          typeof message === "object" &&
          message !== null &&
          "type" in message &&
          message.type === "system.heartbeat" &&
          "action" in message &&
          message.action === "ping" &&
          "nonce" in message &&
          typeof message.nonce === "string"
        ) {
          reconnectAttemptsRef.current = 0;
          try {
            socket.send(JSON.stringify({
              type: "system.heartbeat",
              action: "pong",
              nonce: message.nonce
            }));
          } catch {
            socket.close();
          }
          return;
        }
        if (isGestureRecognitionResult(message) && isMountedRef.current) {
          reconnectAttemptsRef.current = 0;
          onRecognition(message);
        } else if (
          typeof message === "object" &&
          message !== null &&
          "type" in message &&
          message.type === "error" &&
          isMountedRef.current
        ) {
          setCameraError("The gesture service rejected a landmark sequence.");
        }
      };
      socket.onerror = () => {
        if (isMountedRef.current && streamRef.current && socketRef.current === socket) {
          setConnectionState("disconnected");
        }
      };
      socket.onclose = (event) => {
        if (!isMountedRef.current || !streamRef.current || socketRef.current !== socket) {
          return;
        }
        if (event.code === 4401 || event.code === 4403) {
          setConnectionState("unauthorized");
          return;
        }
        if (event.code === 1000 || !shouldReconnectRef.current) {
          setConnectionState("disconnected");
          return;
        }
        scheduleGestureReconnect();
      };
    } catch {
      setConnectionState("disconnected");
      scheduleGestureReconnect();
    }
  }

  function startDetection(detector: HandLandmarkerInstance) {
    const processFrame = (timestamp: number) => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
        animationFrameRef.current = requestAnimationFrame(processFrame);
        return;
      }

      if (timestamp - lastSampleTimeRef.current >= SAMPLE_INTERVAL_MS) {
        lastSampleTimeRef.current = timestamp;
        let result: HandLandmarkerResult;
        try {
          result = detector.detectForVideo(video, timestamp);
        } catch {
          if (isMountedRef.current) {
            setCameraError("Hand landmark detection failed. Stop and restart the camera to retry.");
            setCameraState("paused");
          }
          return;
        }

        const hands = normalizeDetectedHands(result);
        const frame: LandmarkFrame = { hands, hands_detected: hands.length };
        setDetectedHandCount(hands.length);
        const confidenceScores = hands.flatMap((hand) =>
          hand.confidence === undefined ? [] : [hand.confidence]
        );
        setDetectionConfidence(
          confidenceScores.length > 0
            ? confidenceScores.reduce((total, score) => total + score, 0) / confidenceScores.length
            : null
        );
        if (overlayEnabledRef.current) {
          drawLandmarks(canvas, video, result.landmarks, connectionsRef.current);
        } else {
          canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
        }

        const frames = sequenceBuilderRef.current.push(frame, timestamp);
        if (frames && recognitionEnabledRef.current) {
          const socket = socketRef.current;
          if (socket?.readyState === WebSocket.OPEN &&
              socket.bufferedAmount <= MAX_SOCKET_BUFFERED_BYTES) {
            try {
              sequenceNumberRef.current += 1;
              socket.send(
                JSON.stringify({
                  type: "landmark_sequence",
                  sequence_id: crypto.randomUUID(),
                  sequence: sequenceNumberRef.current,
                  timestamp: new Date().toISOString(),
                  schema_version: LANDMARK_SCHEMA_VERSION,
                  session_id: sessionIdRef.current,
                  frame_width: video.videoWidth,
                  frame_height: video.videoHeight,
                  output_language: targetLanguageRef.current,
                  sample_rate_hz: 10,
                  frames
                })
              );
            } catch {
              socket.close();
              if (isMountedRef.current) {
                setConnectionState("disconnected");
              }
            }
          }
        }
      }

      animationFrameRef.current = requestAnimationFrame(processFrame);
    };

    animationFrameRef.current = requestAnimationFrame(processFrame);
  }

  async function refreshCameraDevices(): Promise<MediaDeviceInfo[]> {
    const devices = await cameraServiceRef.current.enumerateVideoDevices();
    if (isMountedRef.current) {
      setCameraDevices(devices);
    }
    return devices;
  }

  async function startCamera(deviceId = selectedDeviceId) {
    const startToken = startTokenRef.current + 1;
    startTokenRef.current = startToken;
    setCameraError("");
    onRecognition(null);
    setCameraState("loading");
    let activeStream: MediaStream | null = null;
    let detector: HandLandmarkerInstance | null = null;

    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraState("idle");
      setCameraError("Camera access is not available in this browser or connection.");
      return;
    }

    try {
      const stream = await cameraServiceRef.current.start(deviceId);
      activeStream = stream;
      if (!isMountedRef.current || startTokenRef.current !== startToken) {
        cameraServiceRef.current.stop();
        return;
      }
      streamRef.current = stream;
      const devices = await refreshCameraDevices();
      if (deviceId && devices.some((device) => device.deviceId === deviceId)) {
        setSelectedDeviceId(deviceId);
      } else {
        const activeDevice = stream.getVideoTracks()[0]?.getSettings().deviceId;
        if (activeDevice) {
          setSelectedDeviceId(activeDevice);
        }
      }
      stream.getVideoTracks().forEach((track) => {
        track.addEventListener("ended", () => {
          if (streamRef.current !== stream || !isMountedRef.current) {
            return;
          }
          if (animationFrameRef.current !== null) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
          }
          shouldReconnectRef.current = false;
          socketRef.current?.close(1000, "Camera disconnected");
          sequenceBuilderRef.current.reset();
          setCameraState("paused");
          setCameraError("The camera was disconnected. Reconnect it or select another camera.");
        }, { once: true });
      });
      const video = videoRef.current;
      if (!video) {
        throw new Error("The camera preview could not be initialized.");
      }
      video.srcObject = stream;
      await video.play();

      const { FilesetResolver, HandLandmarker } = await import("@mediapipe/tasks-vision");
      if (!MEDIAPIPE_WASM_URL || !HAND_LANDMARKER_MODEL_URL) {
        throw new Error("MediaPipe asset URLs are not configured.");
      }
      const vision = await FilesetResolver.forVisionTasks(MEDIAPIPE_WASM_URL);
      detector = await HandLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: HAND_LANDMARKER_MODEL_URL },
        runningMode: "VIDEO",
        numHands: 2,
        minHandDetectionConfidence: 0.5,
        minHandPresenceConfidence: 0.5,
        minTrackingConfidence: 0.5
      });

      if (!isMountedRef.current || startTokenRef.current !== startToken) {
        detector.close();
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      detectorRef.current = detector;
      connectionsRef.current = HandLandmarker.HAND_CONNECTIONS;
      sequenceBuilderRef.current.reset();
      sessionIdRef.current = crypto.randomUUID();
      lastSampleTimeRef.current = 0;
      sequenceNumberRef.current = 0;
      reconnectAttemptsRef.current = 0;
      shouldReconnectRef.current = true;
      recognitionEnabledRef.current = true;
      setRecognitionEnabled(true);
      connectGestureService();
      setCameraState("live");
      startDetection(detector);
    } catch (error) {
      detector?.close();
      if (detectorRef.current === detector) {
        detectorRef.current = null;
      }
      cameraServiceRef.current.stop();
      if (streamRef.current === activeStream) {
        streamRef.current = null;
      }
      if (!isMountedRef.current || startTokenRef.current !== startToken) {
        return;
      }
      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.srcObject = null;
      }
      setCameraState("idle");
      setCameraError(cameraStartError(error));
    }
  }

  async function resumeCamera() {
    setCameraError("");
    try {
      await videoRef.current?.play();
      if (detectorRef.current) {
        setCameraState("live");
        startDetection(detectorRef.current);
      }
    } catch {
      setCameraError("The camera preview could not resume. Stop it and try starting the camera again.");
    }
  }

  function pauseCamera() {
    videoRef.current?.pause();
    sequenceBuilderRef.current.reset();
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    setCameraState("paused");
  }

  function stopCamera() {
    startTokenRef.current += 1;
    shouldReconnectRef.current = false;
    recognitionEnabledRef.current = false;
    setRecognitionEnabled(false);
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    cameraServiceRef.current.stop();
    streamRef.current = null;
    detectorRef.current?.close();
    detectorRef.current = null;
    socketRef.current?.close(1000, "Camera stopped");
    socketRef.current = null;
    sequenceBuilderRef.current.reset();
    sessionIdRef.current = "";
    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }
    const context = canvasRef.current?.getContext("2d");
    if (context && canvasRef.current) {
      context.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
    }
    setCameraState("idle");
    setConnectionState("idle");
    setDetectedHandCount(0);
    setDetectionConfidence(null);
    setCameraError("");
    onRecognition(null);
  }

  return (
    <section aria-label="Camera preview" className="card workspace-panel">
      <div className="panel-heading">
        <div>
          <h2>Camera and hand landmarks</h2>
          <p>Video frames are processed locally in your browser.</p>
        </div>
        <span className="status-pill">
          <span aria-hidden="true" className="status-dot" />
          {cameraState === "live"
            ? "Tracking"
            : cameraState === "loading"
              ? "Starting"
              : cameraState === "paused"
                ? "Paused"
                : "Camera off"}
        </span>
      </div>
      {cameraDevices.length > 0 ? (
        <div className="field">
          <label htmlFor="camera-device">Camera device</label>
          <select
            disabled={cameraState === "loading"}
            id="camera-device"
            onChange={(event) => {
              const nextDeviceId = event.target.value;
              setSelectedDeviceId(nextDeviceId);
              if (cameraState !== "idle" && cameraState !== "loading") {
                stopCamera();
                void startCamera(nextDeviceId);
              }
            }}
            value={selectedDeviceId}
          >
            {cameraDevices.map((device, index) => (
              <option key={device.deviceId} value={device.deviceId}>
                {device.label || `Camera ${index + 1}`}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <div className="camera-stage">
        <video
          aria-label="Mirrored live camera preview"
          autoPlay
          className={cameraState === "idle" ? "camera-video camera-video-idle" : "camera-video"}
          muted
          playsInline
          ref={videoRef}
        />
        <canvas
          aria-hidden="true"
          className="camera-landmark-overlay"
          hidden={cameraState === "idle" || !overlayEnabled}
          ref={canvasRef}
        />
        {cameraState === "idle" ? (
          <div className="camera-empty">
            <Camera aria-hidden="true" />
            <strong>Camera is off</strong>
            <p>Start tracking when you are ready. Your browser will ask for camera permission.</p>
          </div>
        ) : null}
      </div>
      <p aria-live="polite" className="muted" role="status">
        {cameraState === "live"
          ? detectedHandCount > 0
            ? `${detectedHandCount} ${detectedHandCount === 1 ? "hand" : "hands"} detected.`
            : "No hands detected. "
          : "Hand detection is inactive. "}
        {detectionConfidence === null
          ? ""
          : `Average detection confidence ${Math.round(detectionConfidence * 100)}%. `}
        {connectionMessage(connectionState)}
      </p>
      {cameraError ? (
        <p aria-live="polite" className="form-status form-error" role="alert">
          {cameraError}
        </p>
      ) : null}
      <div className="control-row">
        {cameraState === "idle" ? (
          <button className="button" onClick={() => void startCamera()} type="button">
            <Camera aria-hidden="true" /> {cameraError ? "Retry camera" : "Start hand tracking"}
          </button>
        ) : cameraState === "loading" ? (
          <button className="button" disabled type="button">
            Preparing hand tracking…
          </button>
        ) : cameraState === "live" ? (
          <button className="button button-secondary" onClick={pauseCamera} type="button">
            <Pause aria-hidden="true" /> Pause tracking
          </button>
        ) : (
          <button className="button" onClick={resumeCamera} type="button">
            <Play aria-hidden="true" /> Resume tracking
          </button>
        )}
        {cameraState !== "idle" ? (
          <button className="button button-secondary" onClick={stopCamera} type="button">
            <CircleStop aria-hidden="true" /> Stop camera
          </button>
        ) : null}
        {cameraState === "live" ? (
          <button
            className="button button-secondary"
            onClick={() => {
              const enabled = !recognitionEnabledRef.current;
              recognitionEnabledRef.current = enabled;
              sequenceBuilderRef.current.reset();
              setRecognitionEnabled(enabled);
              if (!enabled) {
                onRecognition(null);
              }
            }}
            type="button"
          >
            {recognitionEnabled ? "Stop recognition" : "Start recognition"}
          </button>
        ) : null}
      </div>
      <label className="checkbox-field">
        <input
          checked={overlayEnabled}
          onChange={(event) => {
            overlayEnabledRef.current = event.target.checked;
            setOverlayEnabled(event.target.checked);
          }}
          type="checkbox"
        />
        Show hand landmark overlay
      </label>
      <p className="hero-note">
        <ShieldCheck aria-hidden="true" />
        Camera frames never leave this browser. Only normalized landmark sequences are sent to the
        authenticated SignLingo WebSocket; the service does not persist them.
      </p>
    </section>
  );
}
