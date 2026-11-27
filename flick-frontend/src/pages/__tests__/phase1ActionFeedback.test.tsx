import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import WatchlistPage from "../WatchlistPage";
import CreateSessionPage from "../CreateSessionPage";
import SessionPage from "../SessionPage";
import DiscoverPage from "../DiscoverPage";
import HomePage from "../HomePage";
import SalonPassShareModal from "../../components/session/SalonPassShareModal";
import { CurtainCallMatchModal } from "../../components/session/CurtainCallMatchModal";
import RecoveryCodeModal from "../../components/RecoveryCodeModal";
import * as salonPassCanvas from "../../lib/salonPassCanvas";
import * as api from "../../lib/api";

const MOTION_PROPS = new Set([
  "initial",
  "animate",
  "exit",
  "transition",
  "variants",
  "whileTap",
  "whileHover",
  "whileFocus",
  "whileDrag",
  "layout",
  "layoutId",
  "drag",
  "dragConstraints",
  "dragElastic",
  "onDragEnd",
  "onDragStart",
  "custom",
]);

function stripMotion(props: Record<string, unknown>) {
  const clean: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (!MOTION_PROPS.has(k)) clean[k] = v;
  }
  return clean;
}

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: Record<string, unknown>) => (
      <div {...stripMotion(props)}>{children as ReactNode}</div>
    ),
    button: ({ children, ...props }: Record<string, unknown>) => (
      <button
        {...stripMotion(props)}
        data-motion-animate={props.animate ? JSON.stringify(props.animate) : undefined}
      >
        {children as ReactNode}
      </button>
    ),
    span: ({ children, ...props }: Record<string, unknown>) => (
      <span {...stripMotion(props)}>{children as ReactNode}</span>
    ),
    main: ({ children, ...props }: Record<string, unknown>) => (
      <main {...stripMotion(props)}>{children as ReactNode}</main>
    ),
  },
  AnimatePresence: ({ children }: { children: ReactNode }) => <>{children}</>,
  useMotionValue: () => ({ get: () => 0, set: () => {}, on: vi.fn() }),
  useTransform: () => ({ get: () => 0 }),
  useSpring: () => ({ get: () => 0 }),
  animate: vi.fn(),
}));

vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
  identifyUser: vi.fn(),
  resetAnalyticsIdentity: vi.fn(),
}));

vi.mock("../../lib/tutorial", () => ({
  hasSeenTour: vi.fn(() => true),
  markTourFinished: vi.fn(),
  useSpotlightTour: vi.fn(() => ({
    isOpen: false,
    currentStep: 0,
    steps: [],
    next: vi.fn(),
    prev: vi.fn(),
    skip: vi.fn(),
    finish: vi.fn(),
  })),
}));

vi.mock("../../lib/auth", () => ({
  isGuest: vi.fn(() => false),
  isLoggedIn: vi.fn(() => true),
  getToken: vi.fn(() => "mock-token-xyz"),
  getUser: vi.fn(() => ({ id: 42, username: "cinephile", display_name: "Auteur" })),
  logout: vi.fn(),
}));

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  constructor() {
    setTimeout(() => this.onopen?.(), 0);
  }
  send() {}
  close() {
    this.readyState = MockWebSocket.CLOSED;
  }
}

describe("Phase 1 Motion & Action Feedback Integration", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "test-token");

    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia;

    if (!window.IntersectionObserver) {
      window.IntersectionObserver = class MockIntersectionObserver {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof IntersectionObserver;
    }

    (globalThis as unknown as { WebSocket: typeof MockWebSocket }).WebSocket = MockWebSocket;
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe("WatchlistPage action lifecycle", () => {
    const initialWatchlist = [
      {
        id: 10,
        movie_id: 55,
        movie_title: "Solaris",
        poster_url: "https://example.com/solaris.jpg",
        rating: 8.1,
        release_year: 1972,
        trailer_url: null,
        session_id: 101,
        added_at: "2026-11-19T10:00:00Z",
        watched: false,
      },
    ];

    it("does NOT celebrate while PATCH is pending and only pulses after API confirmation", async () => {
      const deferredPatch = createDeferred<{ success: boolean }>();
      vi.spyOn(api, "apiRequest").mockImplementation((url, opts) => {
        if (url === "/api/watchlist/" && !opts?.method) {
          return Promise.resolve({ watchlist: initialWatchlist });
        }
        if (url === "/api/watchlist/55/" && opts?.method === "PATCH") {
          return deferredPatch.promise;
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/watchlist"]}>
          <WatchlistPage />
        </MemoryRouter>
      );

      const toggleBtn = await screen.findByRole("button", { name: /mark viewed/i });
      fireEvent.click(toggleBtn);

      // Pending state: busy, does not claim Rewatch yet, no confirmation pulse
      await waitFor(() => {
        const pendingBtn = screen.getByRole("button", { name: /saving/i });
        expect(pendingBtn.getAttribute("data-action-status")).toBe("pending");
        expect(pendingBtn.getAttribute("aria-busy")).toBe("true");
        expect(pendingBtn.hasAttribute("disabled")).toBe(true);
      });
      expect(screen.queryByRole("button", { name: /rewatch/i })).toBeNull();
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();

      // Now confirm API request
      await act(async () => {
        deferredPatch.resolve({ success: true });
      });

      await waitFor(() => {
        const confirmedBtn = screen.getByRole("button", { name: /rewatch/i });
        expect(confirmedBtn.getAttribute("data-action-status")).toBe("confirmed");
        expect(screen.getByTestId("action-confirmed-pulse")).not.toBeNull();
      });
    });

    it("surfaces inline error & Retry repeats the failed PATCH and confirms on retry success", async () => {
      let patchAttempts = 0;
      const apiSpy = vi.spyOn(api, "apiRequest").mockImplementation((url, opts) => {
        if (url === "/api/watchlist/" && !opts?.method) {
          return Promise.resolve({ watchlist: initialWatchlist });
        }
        if (url === "/api/watchlist/55/" && opts?.method === "PATCH") {
          patchAttempts += 1;
          if (patchAttempts === 1) {
            return Promise.reject(new Error("PATCH failed"));
          }
          return Promise.resolve({ success: true, watched: true });
        }
        if (url === "/api/watchlist/55/" && opts?.method === "DELETE") {
          return Promise.reject(new Error("DELETE failed"));
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/watchlist"]}>
          <WatchlistPage />
        </MemoryRouter>
      );

      const toggleBtn = await screen.findByRole("button", { name: /mark viewed/i });
      fireEvent.click(toggleBtn);

      await waitFor(() => {
        const errorBtn = screen.getByRole("button", { name: /retry/i });
        expect(errorBtn.getAttribute("data-action-status")).toBe("error");
        expect(screen.getByRole("alert").textContent).toContain("Couldn't update viewing status");
      });
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();
      expect(screen.queryByRole("button", { name: /rewatch/i })).toBeNull();

      // Clicking Retry actually repeats PATCH /api/watchlist/55/ and succeeds cleanly
      fireEvent.click(screen.getByRole("button", { name: /retry/i }));

      await waitFor(() => {
        expect(patchAttempts).toBe(2);
        const confirmedBtn = screen.getByRole("button", { name: /rewatch/i });
        expect(confirmedBtn.getAttribute("data-action-status")).toBe("confirmed");
        expect(screen.getByTestId("action-confirmed-pulse")).not.toBeNull();
      });
      expect(screen.queryByRole("alert")).toBeNull();
      expect(apiSpy).toHaveBeenCalledWith(
        "/api/watchlist/55/",
        expect.objectContaining({ method: "PATCH" })
      );

      // Remove failure preserves item card and renders error alert
      const removeBtn = screen.getByLabelText("Remove from watchlist");
      fireEvent.click(removeBtn);

      await waitFor(() => {
        expect(screen.getByRole("alert").textContent).toContain("Couldn't remove film");
        expect(removeBtn.getAttribute("data-action-status")).toBe("error");
      });
      expect(screen.getByText("Solaris")).not.toBeNull();
    });

    it("communicates View/Rewatch confirmation clearly under prefers-reduced-motion without decorative pulse", async () => {
      window.matchMedia = vi.fn().mockImplementation((query: string) => ({
        matches: query.includes("prefers-reduced-motion"),
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })) as unknown as typeof window.matchMedia;

      vi.spyOn(api, "apiRequest").mockImplementation((url, opts) => {
        if (url === "/api/watchlist/" && !opts?.method) {
          return Promise.resolve({ watchlist: initialWatchlist });
        }
        if (url === "/api/watchlist/55/" && opts?.method === "PATCH") {
          return Promise.resolve({ success: true });
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/watchlist"]}>
          <WatchlistPage />
        </MemoryRouter>
      );

      const toggleBtn = await screen.findByRole("button", { name: /mark viewed/i });
      fireEvent.click(toggleBtn);

      await waitFor(() => {
        const confirmedBtn = screen.getByRole("button", { name: /rewatch/i });
        expect(confirmedBtn.getAttribute("data-action-status")).toBe("confirmed");
      });
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();
    });
  });

  describe("CreateSessionPage independent clipboard states & error feedback", () => {
    const preseedMovie = {
      id: 42,
      tmdb_id: 9942,
      title: "Past Lives",
      original_language: "en",
      genres: ["Drama"],
      genre_ids: [7],
      overview: "Nora and Hae Sung...",
      poster_url: "https://example.com/pastlives.jpg",
      rating: 8.2,
      release_year: 2023,
    };

    function renderCreatedSession() {
      vi.spyOn(api, "apiRequest").mockImplementation((url) => {
        if (url === "/api/sessions/create/") {
          return Promise.resolve({ success: true, id: 999, code: "PLV42X" });
        }
        if (url === "/api/sessions/genre/") {
          return Promise.resolve({ success: true, session_id: 999 });
        }
        return Promise.resolve({});
      });

      return render(
        <MemoryRouter
          initialEntries={[{ pathname: "/session/create", state: { preseedMovie } }]}
        >
          <Routes>
            <Route path="/session/create" element={<CreateSessionPage />} />
          </Routes>
        </MemoryRouter>
      );
    }

    it("tracks Copy Code and Copy Link independently so copying link does not mark Copy Code as Copied!", async () => {
      const writeTextMock = vi.fn().mockResolvedValue(undefined);
      Object.assign(navigator, { clipboard: { writeText: writeTextMock } });

      renderCreatedSession();
      await screen.findByText("PLV42X");

      const copyLinkBtn = screen.getByRole("button", { name: /^copy$/i });
      expect(copyLinkBtn.className).toContain("min-h-11");
      fireEvent.click(copyLinkBtn);

      await waitFor(() => {
        expect(writeTextMock).toHaveBeenCalledWith(expect.stringContaining("/join/PLV42X"));
        expect(copyLinkBtn.getAttribute("data-action-status")).toBe("confirmed");
        expect(copyLinkBtn.textContent).toContain("Copied!");
      });

      // Copy Code must remain idle and un-copied
      const copyCodeBtn = screen.getByRole("button", { name: /copy code/i });
      expect(copyCodeBtn.getAttribute("data-action-status")).toBe("idle");
      expect(copyCodeBtn.textContent).toContain("Copy Code");
    });

    it("surfaces error state and alert when clipboard write fails or clipboard is unsupported", async () => {
      const writeTextMock = vi.fn().mockRejectedValue(new Error("Permission denied"));
      Object.assign(navigator, { clipboard: { writeText: writeTextMock } });

      const { unmount } = renderCreatedSession();
      await screen.findByText("PLV42X");

      const copyCodeBtn = screen.getByRole("button", { name: /copy code/i });
      fireEvent.click(copyCodeBtn);

      await waitFor(() => {
        expect(copyCodeBtn.getAttribute("data-action-status")).toBe("error");
        expect(copyCodeBtn.textContent).toContain("Copy Failed");
        expect(screen.getByRole("alert").textContent).toContain("Couldn't copy code");
      });
      expect(copyCodeBtn.textContent).not.toContain("Copied");
      unmount();

      // Now test completely unsupported navigator.clipboard
      Object.defineProperty(navigator, "clipboard", {
        value: undefined,
        configurable: true,
      });

      renderCreatedSession();
      await screen.findByText("PLV42X");

      const copyLinkBtn = screen.getByRole("button", { name: /^copy$/i });
      fireEvent.click(copyLinkBtn);

      await waitFor(() => {
        expect(copyLinkBtn.getAttribute("data-action-status")).toBe("error");
        expect(copyLinkBtn.textContent).toContain("Failed");
        expect(screen.getByRole("alert").textContent).toContain("Couldn't copy invite link");
      });
      expect(copyLinkBtn.textContent).not.toContain("Copied");
    });

    it("covers manual Create Session error, retry, and completion flow", async () => {
      let createCalls = 0;
      vi.spyOn(api, "apiRequest").mockImplementation((url) => {
        if (url.startsWith("/api/genres/")) {
          return Promise.resolve({ genres: [{ id: 18, name: "Drama" }] });
        }
        if (url === "/api/sessions/create/") {
          createCalls += 1;
          if (createCalls === 1) {
            return Promise.reject(new Error("Server unavailable"));
          }
          return Promise.resolve({ success: true, id: 777, code: "MAN77X" });
        }
        if (url === "/api/sessions/genre/") {
          return Promise.resolve({ success: true, session_id: 777 });
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/session/create"]}>
          <Routes>
            <Route path="/session/create" element={<CreateSessionPage />} />
          </Routes>
        </MemoryRouter>
      );

      // Step 1: Industry
      const hollywoodBtn = await screen.findByRole("button", { name: /hollywood/i });
      fireEvent.click(hollywoodBtn);
      const continueLangBtn = await screen.findByRole("button", { name: /continue to languages/i });
      fireEvent.click(continueLangBtn);

      // Step 2: Language
      const englishBtn = await screen.findByRole("button", { name: /english/i });
      fireEvent.click(englishBtn);
      fireEvent.click(await screen.findByRole("button", { name: /continue to genres/i }));

      // Step 3: Genre -> first attempt fails -> Retry succeeds
      const dramaBtn = await screen.findByRole("button", { name: /drama/i });
      fireEvent.click(dramaBtn);

      const createBtn = screen.getByRole("button", { name: /create session/i });
      fireEvent.click(createBtn);

      await waitFor(() => {
        expect(createCalls).toBe(1);
        expect(screen.getByText(/failed to create session/i)).not.toBeNull();
      });

      fireEvent.click(screen.getByRole("button", { name: /create session/i }));

      await waitFor(() => {
        expect(createCalls).toBe(2);
        expect(screen.getByText("MAN77X")).not.toBeNull();
        expect(screen.getByText("Screening Ready")).not.toBeNull();
      });
    });
  });

  describe("SessionPage waiting room async clipboard & error handling", () => {
    it("awaits clipboard promise and reports failure instead of faking Copied", async () => {
      const deferredClipboard = createDeferred<void>();
      Object.assign(navigator, {
        clipboard: { writeText: vi.fn().mockReturnValue(deferredClipboard.promise) },
      });

      vi.spyOn(api, "apiRequest").mockImplementation((url) => {
        if (url.includes("/api/sessions/101/deck/card/")) {
          return Promise.resolve({ success: true, is_legacy: false });
        }
        if (url.includes("/api/sessions/101/")) {
          return Promise.resolve({
            session: {
              id: 101,
              code: "WAIT99",
              host_joined: true,
              guest_joined: false,
              preferences_set: true,
              user_preferences_set: true,
              user_role: "host",
              ended: false,
              matched_count: 0,
              reviewed_count: 0,
              affinity_percent: 0,
            },
          });
        }
        if (url.includes("/api/watchlist/")) {
          return Promise.resolve({ watchlist: [] });
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/session/101"]}>
          <Routes>
            <Route path="/session/:id" element={<SessionPage />} />
          </Routes>
        </MemoryRouter>
      );

      const copyCodeBtn = await screen.findByRole("button", { name: /copy code/i });
      expect(copyCodeBtn.className).toContain("min-h-11");
      fireEvent.click(copyCodeBtn);

      // Must NOT report "Copied" before clipboard promise resolves
      expect(copyCodeBtn.getAttribute("data-action-status")).toBe("pending");
      expect(copyCodeBtn.textContent).not.toContain("Copied");

      await act(async () => {
        deferredClipboard.reject(new Error("Blocked"));
      });

      await waitFor(() => {
        expect(copyCodeBtn.getAttribute("data-action-status")).toBe("error");
        expect(copyCodeBtn.textContent).toContain("Copy failed");
        expect(screen.getByRole("alert").textContent).toContain("Couldn't copy code");
      });
    });
  });

  describe("DiscoverPage deferred watchlist toggle, detail sheet & retry", () => {
    it("keeps watchlist unmodified while pending, surfaces error in detail sheet, and retries cleanly", async () => {
      let postCalls = 0;
      const deferredPost = createDeferred<unknown>();
      vi.spyOn(api, "apiRequest").mockImplementation((url, opts) => {
        if (url.includes("/api/discover/")) {
          return Promise.resolve({
            success: true,
            movies: [
              {
                id: 1,
                tmdb_id: 101,
                title: "In the Mood for Love",
                overview: "...",
                poster_url: "https://example.com/itmf.jpg",
                rating: 8.1,
                release_year: 2000,
                original_language: "zh",
              },
            ],
            has_more: false,
          });
        }
        if (url === "/api/watchlist/" && opts?.method === "POST") {
          postCalls += 1;
          if (postCalls === 1) return deferredPost.promise;
          return Promise.resolve({ success: true });
        }
        if (url.includes("/api/watchlist/")) {
          return Promise.resolve({ watchlist: [] });
        }
        if (url.includes("/api/genres/")) {
          return Promise.resolve({ genres: [] });
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      const bookmarkBtn = await screen.findByRole("button", { name: "Add to watchlist" });
      fireEvent.click(bookmarkBtn);

      await waitFor(() => {
        expect(bookmarkBtn.getAttribute("data-action-status")).toBe("pending");
      });
      // Label should still reflect not yet confirmed in watchlist
      expect(screen.queryByRole("button", { name: "Remove from watchlist" })).toBeNull();

      await act(async () => {
        deferredPost.reject(new Error("Save failed"));
      });

      await waitFor(() => {
        expect(bookmarkBtn.getAttribute("data-action-status")).toBe("error");
        expect(screen.getByRole("alert").textContent).toContain("Couldn't update watchlist");
      });

      // Open MovieDetailSheet and retry Watchlist save directly from inside detail modal
      const titleEl = screen.getByText("In the Mood for Love");
      fireEvent.click(titleEl.closest(".cursor-pointer")!);

      const dialog = await screen.findByRole("dialog");
      const retryBtn = within(dialog).getByRole("button", { name: /^retry$/i });
      expect(within(dialog).getByRole("alert").textContent).toContain("Couldn't update watchlist");

      fireEvent.click(retryBtn);

      await waitFor(() => {
        expect(postCalls).toBe(2);
        const savedBtn = within(dialog).getByRole("button", { name: /saved in watchlist/i });
        expect(savedBtn.getAttribute("data-action-status")).toBe("confirmed");
        expect(within(dialog).getByTestId("action-confirmed-pulse")).not.toBeNull();
      });
    });
  });

  describe("SessionPage match watchlist retry & share/recovery clipboard error flows", () => {
    it("covers Match conclusion watchlist failure and Retry saving to watchlist", async () => {
      let postAttempts = 0;
      vi.spyOn(api, "apiRequest").mockImplementation((url, opts) => {
        if (url.includes("/api/matches/")) {
          return Promise.resolve({
            matches: [
              {
                session_id: 101,
                movie_id: 55,
                movie_title: "Solaris",
                rating: 8.1,
                release_year: 1972,
                poster_url: "https://example.com/solaris.jpg",
              },
            ],
          });
        }
        if (url.includes("/api/sessions/101/")) {
          return Promise.resolve({
            session: {
              id: 101,
              code: "MATCH99",
              state: "concluded",
              host_joined: true,
              guest_joined: true,
              preferences_set: true,
              user_preferences_set: true,
              user_role: "host",
              ended: true,
              matched_count: 1,
              reviewed_count: 3,
              affinity_percent: 33,
            },
          });
        }
        if (url === "/api/watchlist/" && opts?.method === "POST") {
          postAttempts += 1;
          if (postAttempts === 1) {
            return Promise.reject(new Error("Watchlist unavailable"));
          }
          return Promise.resolve({ success: true });
        }
        if (url.includes("/api/watchlist/")) {
          return Promise.resolve({ watchlist: [] });
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/session/101"]}>
          <Routes>
            <Route path="/session/:id" element={<SessionPage />} />
          </Routes>
        </MemoryRouter>
      );

      await screen.findByText("Screening Concluded");
      fireEvent.click(screen.getByRole("button", { name: /film details/i }));

      const saveLabel = await screen.findByText("Save to Watchlist");
      const saveBtn = saveLabel.closest("button")!;
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(postAttempts).toBe(1);
        expect(saveBtn.getAttribute("data-action-status")).toBe("error");
        expect(saveBtn.textContent).toContain("Retry Save");
        expect(screen.getByRole("alert").textContent).toContain("Couldn't update watchlist");
      });

      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(postAttempts).toBe(2);
        expect(saveBtn.getAttribute("data-action-status")).toBe("confirmed");
        expect(saveBtn.textContent).toContain("Saved in Watchlist");
        expect(within(saveBtn).getByTestId("action-confirmed-pulse")).not.toBeNull();
      });
    });

    it("surfaces Watchlist error and Retry recovery inside CurtainCallMatchModal", () => {
      const onToggleWatchlist = vi.fn();
      const baseProps = {
        matchedMovie: {
          id: 55,
          title: "Solaris",
          overview: "Space station psychologist",
          rating: 8.1,
          release_year: 1972,
          superlike_attribution: "none" as const,
          match_type: "ordinary" as const,
        },
        renderMode: "full" as const,
        shouldReduceMotion: false,
        userRole: "host" as const,
        isWatchlisted: false,
        watchlistLoading: false,
        onToggleWatchlist,
        savedBurstId: null,
        onDismiss: vi.fn(),
        onEndSession: vi.fn().mockResolvedValue(undefined),
        endSessionLoading: false,
        sessionLocked: false,
        sessionEnded: false,
        onFetchMetadata: vi.fn(),
        onTrailerClick: vi.fn(),
      };

      const { rerender } = render(
        <CurtainCallMatchModal
          {...baseProps}
          watchlistStatus="error"
          watchlistError="Couldn't update watchlist. Please try again."
        />
      );

      const retryBtn = screen.getByRole("button", { name: /^retry$/i });
      expect(retryBtn.getAttribute("data-action-status")).toBe("error");
      expect(screen.getByRole("alert").textContent).toContain("Couldn't update watchlist");
      expect(screen.queryByTestId("action-confirmed-pulse")).toBeNull();

      fireEvent.click(retryBtn);
      expect(onToggleWatchlist).toHaveBeenCalledTimes(1);

      rerender(
        <CurtainCallMatchModal
          {...baseProps}
          isWatchlisted={true}
          watchlistStatus="confirmed"
          watchlistError={null}
        />
      );

      const savedBtn = screen.getByRole("button", { name: /saved/i });
      expect(savedBtn.getAttribute("data-action-status")).toBe("confirmed");
      expect(screen.getByTestId("action-confirmed-pulse")).not.toBeNull();
      expect(screen.queryByRole("alert")).toBeNull();
    });

    it("surfaces accurate clipboard errors in SalonPassShareModal & RecoveryCodeModal when denied or unsupported", async () => {
      vi.spyOn(salonPassCanvas, "renderSalonPassToCanvas").mockResolvedValue(undefined);
      vi.spyOn(salonPassCanvas, "getCanvasBlob").mockResolvedValue(
        new Blob(["mock-image-bytes"], { type: "image/png" })
      );
      global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
      global.URL.revokeObjectURL = vi.fn();

      // Permission denied in SalonPassShareModal
      Object.assign(navigator, {
        clipboard: { writeText: vi.fn().mockRejectedValue(new Error("Denied")) },
      });

      const { unmount } = render(
        <SalonPassShareModal
          isOpen={true}
          onClose={vi.fn()}
          data={{
            movieTitle: "Solaris",
            releaseYear: 1972,
            rating: 8.1,
            posterUrl: "https://example.com/solaris.jpg",
            sessionCode: "SOL99",
            userRole: "host",
          }}
        />
      );

      const passCopyBtn = screen.getByRole("button", { name: /copy link/i });
      fireEvent.click(passCopyBtn);

      await waitFor(() => {
        expect(passCopyBtn.getAttribute("data-action-status")).toBe("error");
        expect(passCopyBtn.textContent).toContain("Copy Failed");
        expect(screen.getByRole("alert").textContent).toContain("Could not copy link");
      });
      expect(passCopyBtn.textContent).not.toContain("Copied!");
      unmount();

      // Unsupported clipboard in RecoveryCodeModal
      Object.defineProperty(navigator, "clipboard", {
        value: undefined,
        configurable: true,
      });

      render(
        <RecoveryCodeModal
          isOpen={true}
          recoveryCode="4F9K-2M8P-7Q1X-0R5T"
          onConfirm={vi.fn()}
        />
      );

      const recCopyBtn = screen.getByRole("button", { name: /copy recovery code/i });
      expect(recCopyBtn.className).toContain("min-h-11");
      fireEvent.click(recCopyBtn);

      await waitFor(() => {
        expect(recCopyBtn.getAttribute("data-action-status")).toBe("error");
        expect(recCopyBtn.textContent).toContain("Copy Failed");
        expect(screen.getByRole("alert").textContent).toContain("manually highlight and copy");
      });
      expect(recCopyBtn.textContent).not.toContain("Copied to Clipboard");
    });
  });

  describe("HomePage deferred curator watchlist confirmation", () => {
    it("shows ticket stamp ONLY after POST /api/watchlist/ resolves", async () => {
      const deferredPost = createDeferred<unknown>();
      vi.spyOn(api, "apiRequest").mockImplementation((url, opts) => {
        if (url.includes("curators-selection") || url.includes("/movies/recommendations/curators/")) {
          return Promise.resolve({
            movies: [
              {
                id: 101,
                tmdb_id: 101,
                title: "Stalker",
                overview: "A guide leads two men through an area known as the Zone.",
                poster_url: "https://example.com/stalker.jpg",
                rating: 8.2,
                release_year: 1979,
                original_language: "ru",
              },
            ],
          });
        }
        if (url === "/api/watchlist/" && opts?.method === "POST") {
          return deferredPost.promise;
        }
        if (url.includes("/api/watchlist/")) {
          return Promise.resolve({ watchlist: [] });
        }
        if (url.includes("/api/sessions/")) {
          return Promise.resolve({ sessions: [] });
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter initialEntries={["/home"]}>
          <HomePage />
        </MemoryRouter>
      );

      const saveBtn = await screen.findByRole("button", { name: /save to watchlist/i });
      fireEvent.click(saveBtn);

      // Pending: Saving..., NO ticket stamp prematurely
      await waitFor(() => {
        expect(saveBtn.getAttribute("data-action-status")).toBe("pending");
        expect(saveBtn.textContent).toContain("Saving");
      });
      expect(screen.queryByText(/STAMPED · WATCHLIST/i)).toBeNull();

      await act(async () => {
        deferredPost.resolve({ success: true });
      });

      await waitFor(() => {
        expect(saveBtn.getAttribute("data-action-status")).toBe("confirmed");
        expect(screen.getByText(/STAMPED · WATCHLIST/i)).not.toBeNull();
      });
    });
  });
});
