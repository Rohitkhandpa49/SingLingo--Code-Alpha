import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  isRegisteredAvatarAsset,
  useAvatarSequencePlayback
} from "./avatar-sequence-player";

describe("avatar sequence playback", () => {
  it("plays each verified item in order, pauses at completion, and resets on stop", () => {
    const { result } = renderHook(() => useAvatarSequencePlayback(2, true));

    act(() => result.current.start());
    expect(result.current.playing).toBe(true);

    act(() => result.current.finishCurrentSign());
    expect(result.current.currentIndex).toBe(1);
    expect(result.current.playing).toBe(true);

    act(() => result.current.finishCurrentSign());
    expect(result.current.currentIndex).toBe(1);
    expect(result.current.playing).toBe(false);

    act(() => result.current.start());
    act(() => result.current.stop());
    expect(result.current.currentIndex).toBe(0);
    expect(result.current.playing).toBe(false);
  });

  it("refuses playback without an explicitly registered GLB and clip", () => {
    const { result } = renderHook(() => useAvatarSequencePlayback(1, false));

    act(() => result.current.start());

    expect(result.current.playing).toBe(false);
    expect(
      isRegisteredAvatarAsset({
        sign_id: "hello",
        sign_name: "Hello",
        matched_text: "hello",
        animation_asset: null,
        animation_clip: null
      })
    ).toBe(false);
  });

  it("pauses and resumes the current sign without advancing the sequence", () => {
    const { result } = renderHook(() => useAvatarSequencePlayback(2, true));

    act(() => result.current.start());
    act(() => result.current.pause());

    expect(result.current.playbackState).toBe("paused");
    expect(result.current.currentIndex).toBe(0);

    act(() => result.current.start());

    expect(result.current.playbackState).toBe("playing");
    expect(result.current.currentIndex).toBe(0);
  });
});
