"use client";

import { Component, Suspense, useCallback, useEffect, useState, type ReactNode } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, useAnimations, useGLTF } from "@react-three/drei";
import { LoopOnce } from "three";
import type { ISLTextSequenceItem } from "@/lib/isl-api";

type Props = Readonly<{
  sequence: ISLTextSequenceItem[];
}>;

type RegisteredAvatarSequenceItem = ISLTextSequenceItem & {
  animation_asset: string;
  animation_clip: string;
};

export function isRegisteredAvatarAsset(
  item: ISLTextSequenceItem
): item is RegisteredAvatarSequenceItem {
  const safeId = /^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/;
  const safeClip = /^[A-Za-z0-9][A-Za-z0-9 _.-]{0,99}$/;
  return (
    safeId.test(item.sign_id) &&
    item.animation_asset === `/assets/signs/${item.sign_id}.glb` &&
    item.animation_clip !== null &&
    safeClip.test(item.animation_clip)
  );
}

export function useAvatarSequencePlayback(
  sequenceLength: number,
  assetsAvailable: boolean
) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [playbackState, setPlaybackState] = useState<"stopped" | "playing" | "paused">(
    "stopped"
  );

  const finishCurrentSign = useCallback(() => {
    if (currentIndex >= sequenceLength - 1) {
      setPlaybackState("stopped");
    } else {
      setCurrentIndex(currentIndex + 1);
    }
  }, [currentIndex, sequenceLength]);

  const start = useCallback(() => {
    if (assetsAvailable) {
      setPlaybackState("playing");
    }
  }, [assetsAvailable]);

  const stop = useCallback(() => {
    setPlaybackState("stopped");
    setCurrentIndex(0);
  }, []);

  const select = useCallback((index: number) => {
    if (index >= 0 && index < sequenceLength) {
      setPlaybackState("stopped");
      setCurrentIndex(index);
    }
  }, [sequenceLength]);

  const pause = useCallback(() => {
    if (playbackState === "playing") {
      setPlaybackState("paused");
    }
  }, [playbackState]);

  return {
    currentIndex,
    playbackState,
    playing: playbackState === "playing",
    pause,
    finishCurrentSign,
    start,
    stop,
    select
  };
}

function AnimatedSign({
  item,
  playbackState,
  playbackIndex,
  onFinished,
  onError
}: {
  item: RegisteredAvatarSequenceItem;
  playbackState: "stopped" | "playing" | "paused";
  playbackIndex: number;
  onFinished: () => void;
  onError: () => void;
}) {
  const gltf = useGLTF(item.animation_asset);
  const { actions, mixer } = useAnimations(gltf.animations, gltf.scene);
  const action = actions[item.animation_clip];

  useEffect(() => {
    if (!action) {
      if (playbackState === "playing") {
        onError();
      }
      return;
    }
    if (playbackState === "stopped") {
      action.stop();
      return;
    }
    if (playbackState === "paused") {
      action.setEffectiveTimeScale(0);
      return;
    }
    if (action.getEffectiveTimeScale() === 0) {
      action.setEffectiveTimeScale(1);
    } else {
      action.reset();
      action.setLoop(LoopOnce, 1);
      action.play();
    }
  }, [action, onError, playbackIndex, playbackState]);

  useEffect(() => {
    if (!action) {
      return;
    }
    const handleFinished = (event: { action: typeof action }) => {
      if (event.action === action) {
        onFinished();
      }
    };
    mixer.addEventListener("finished", handleFinished);
    return () => {
      mixer.removeEventListener("finished", handleFinished);
    };
  }, [action, mixer, onFinished]);

  return <primitive object={gltf.scene} />;
}

type ErrorBoundaryProps = Readonly<{
  children: ReactNode;
  onError: () => void;
}>;

type ErrorBoundaryState = Readonly<{ failed: boolean }>;

class SceneErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch() {
    this.props.onError();
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

export function AvatarSequencePlayer({ sequence }: Props) {
  const [playbackError, setPlaybackError] = useState("");
  const assetsAvailable =
    sequence.length > 0 && sequence.every(isRegisteredAvatarAsset);
  const playback = useAvatarSequencePlayback(
    sequence.length,
    assetsAvailable
  );
  const { currentIndex, playbackState, playing, stop } = playback;
  const currentItem = sequence[currentIndex] ?? null;

  const reportPlaybackError = useCallback(() => {
    stop();
    setPlaybackError("The registered animation could not be played.");
  }, [stop]);

  return (
    <section aria-label="Signing avatar and sequence playback" className="avatar-sequence-player">
      {assetsAvailable && currentItem && isRegisteredAvatarAsset(currentItem) ? (
        <div aria-label={`3D avatar showing ${currentItem.sign_name}`} className="avatar-canvas" role="img">
          <SceneErrorBoundary key={currentItem.sign_id} onError={reportPlaybackError}>
            <Canvas camera={{ position: [0, 1.4, 3], fov: 40 }}>
              <ambientLight intensity={0.8} />
              <directionalLight position={[3, 5, 2]} intensity={1.2} />
              <Suspense fallback={null}>
                <AnimatedSign
                  item={currentItem}
                  onError={reportPlaybackError}
                  onFinished={playback.finishCurrentSign}
                  playbackIndex={currentIndex}
                  playbackState={playbackState}
                />
              </Suspense>
              <OrbitControls enablePan={false} />
            </Canvas>
          </SceneErrorBoundary>
        </div>
      ) : (
        <div className="avatar-placeholder">
          <div>
            <p className="muted">
              {sequence.length
                ? "Verified signing animation assets are not available for this sequence."
                : "No verified sign sequence is available to preview."}
            </p>
          </div>
        </div>
      )}
      {currentItem ? (
        <div className="avatar-sequence-current" aria-live="polite">
          <strong>
            Sign {currentIndex + 1} of {sequence.length}: {currentItem.sign_name}
          </strong>
          <p>Matched text: {currentItem.matched_text}</p>
        </div>
      ) : null}
      {sequence.length > 0 ? (
        <>
          <ol aria-label="Verified sign sequence" className="avatar-sequence-list">
            {sequence.map((item, index) => (
              <li key={`${item.sign_id}-${index}`}>
                <button
                  aria-current={index === currentIndex ? "step" : undefined}
                  disabled={playbackState !== "stopped"}
                  onClick={() => playback.select(index)}
                  type="button"
                >
                  {index + 1}. {item.sign_name}
                </button>
              </li>
            ))}
          </ol>
          <div className="control-row">
            <button
              className="button button-secondary"
              disabled={!assetsAvailable || playbackState === "playing"}
              onClick={() => {
                setPlaybackError("");
                playback.start();
              }}
              type="button"
            >
              {playbackState === "paused"
                ? "Resume verified sequence"
                : "Play verified sequence"}
            </button>
            <button
              className="button button-secondary"
              disabled={!playing}
              onClick={playback.pause}
              type="button"
            >
              Pause
            </button>
            <button
              className="button button-quiet"
              disabled={playbackState === "stopped" && currentIndex === 0}
              onClick={playback.stop}
              type="button"
            >
              Stop
            </button>
          </div>
        </>
      ) : null}
      {playbackError ? (
        <p aria-live="assertive" className="form-status form-error" role="alert">
          {playbackError}
        </p>
      ) : null}
      {sequence.length > 0 && !assetsAvailable ? (
        <p className="field-hint">
          The sequence is shown for review only. No sign animation is fabricated or played.
        </p>
      ) : null}
    </section>
  );
}
