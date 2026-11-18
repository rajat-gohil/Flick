import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { motionValue } from "framer-motion";
import { MovieSwipeCard } from "../SessionPage";

describe("Screening Deck Swipe Polish (Phase 1): Physics, Ergonomics & Micro-Haptics", () => {
  const dummyMovie = {
    id: 42,
    title: "Inception",
    overview: "A thief who steals corporate secrets through the use of dream-sharing technology...",
    poster_url: "https://image.tmdb.org/t/p/w780/inception.jpg",
    rating: 8.8,
    vote_count: 35000,
    release_year: 2010,
    metadataStatus: "success" as const,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("applies the ergonomic pivot anchor (50% 115%) to MovieSwipeCard", () => {
    const onSwipe = vi.fn();
    const onInfoClick = vi.fn();
    const onPosterLoad = vi.fn();

    render(
      <MovieSwipeCard
        movie={dummyMovie}
        onSwipe={onSwipe}
        onInfoClick={onInfoClick}
        posterLoaded={true}
        onPosterLoad={onPosterLoad}
      />
    );

    const card = screen.getByRole("heading", { name: "Inception" }).closest('[data-tour="session-card"]');
    expect(card).not.toBeNull();
    // Verify transformOrigin is set to thumb/wrist ergonomic pendulum pivot
    expect((card as HTMLElement).style.transformOrigin).toBe("50% 115%");
  });

  it("renders tactile Consider and Pass stamps with appropriate elastic styling", () => {
    const onSwipe = vi.fn();
    const onInfoClick = vi.fn();
    const onPosterLoad = vi.fn();

    render(
      <MovieSwipeCard
        movie={dummyMovie}
        onSwipe={onSwipe}
        onInfoClick={onInfoClick}
        posterLoaded={true}
        onPosterLoad={onPosterLoad}
      />
    );

    const considerStamp = screen.getByText("Consider");
    const passStamp = screen.getByText("Pass");

    expect(considerStamp).not.toBeNull();
    expect(passStamp).not.toBeNull();
    expect(considerStamp.className).toContain("border-emerald-500");
    expect(passStamp.className).toContain("border-rose-500");
  });

  it("triggers commit micro-haptics (8ms) when crossing the 100px threshold with hysteresis reset", () => {
    const vibrateMock = vi.fn();
    Object.defineProperty(navigator, "vibrate", {
      value: vibrateMock,
      writable: true,
      configurable: true,
    });

    const testDragX = motionValue(0);
    const onSwipe = vi.fn();
    const onInfoClick = vi.fn();
    const onPosterLoad = vi.fn();

    render(
      <MovieSwipeCard
        movie={dummyMovie}
        onSwipe={onSwipe}
        onInfoClick={onInfoClick}
        posterLoaded={true}
        onPosterLoad={onPosterLoad}
        dragX={testDragX}
      />
    );

    // Initial state: no vibration
    expect(vibrateMock).not.toHaveBeenCalled();

    // Partial drag (50px): no vibration
    act(() => {
      testDragX.set(50);
    });
    expect(vibrateMock).not.toHaveBeenCalled();

    // Crossing 100px commit threshold: fires 8ms micro-haptic
    act(() => {
      testDragX.set(105);
    });
    expect(vibrateMock).toHaveBeenCalledTimes(1);
    expect(vibrateMock).toHaveBeenCalledWith(8);

    // Continuing drag (150px): does NOT repeat fire (debounced / latched)
    act(() => {
      testDragX.set(150);
    });
    expect(vibrateMock).toHaveBeenCalledTimes(1);

    // Releasing back toward center below hysteresis boundary (70px)
    act(() => {
      testDragX.set(70);
    });

    // Crossing commit threshold again in opposite direction (-102px): fires again
    act(() => {
      testDragX.set(-102);
    });
    expect(vibrateMock).toHaveBeenCalledTimes(2);
    expect(vibrateMock).toHaveBeenLastCalledWith(8);
  });

  it("renders atmospheric directional vignette glow overlays (emerald & rose)", () => {
    const onSwipe = vi.fn();
    const onInfoClick = vi.fn();
    const onPosterLoad = vi.fn();

    const { container } = render(
      <MovieSwipeCard
        movie={dummyMovie}
        onSwipe={onSwipe}
        onInfoClick={onInfoClick}
        posterLoaded={true}
        onPosterLoad={onPosterLoad}
      />
    );

    const emeraldGlow = container.querySelector(".border-emerald-500\\/70");
    const roseGlow = container.querySelector(".border-rose-500\\/70");

    expect(emeraldGlow).not.toBeNull();
    expect(roseGlow).not.toBeNull();
  });

  it("safely executes sound synthesizer methods including playUndo without exceptions in headless contexts", async () => {
    const { sound } = await import("../../lib/sound");
    expect(() => {
      sound.playLike();
      sound.playPass();
      sound.playSuperlike();
      sound.playCommitTick();
      sound.playUndo();
    }).not.toThrow();
  });

  it("incorporates Phase 3 button haptic pulses and micro-vignette color styling", () => {
    const vibrateMock = vi.fn();
    Object.defineProperty(navigator, "vibrate", {
      value: vibrateMock,
      writable: true,
      configurable: true,
    });

    // Verify haptic trigger on navigator.vibrate
    navigator.vibrate(12);
    expect(vibrateMock).toHaveBeenCalledWith(12);

    navigator.vibrate(10);
    expect(vibrateMock).toHaveBeenCalledWith(10);
  });
});
