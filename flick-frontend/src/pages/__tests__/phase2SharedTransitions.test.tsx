import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import DiscoverPage from "../DiscoverPage";
import CreateSessionPage from "../CreateSessionPage";
import SessionPage from "../SessionPage";
import { CurtainCallMatchModal } from "../../components/session/CurtainCallMatchModal";
import SalonPassShareModal from "../../components/session/SalonPassShareModal";
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

function stripMotionWithCapture(props: Record<string, unknown>) {
  const clean: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(props)) {
    if (!MOTION_PROPS.has(k)) clean[k] = v;
  }
  if (props.layoutId !== undefined) clean["data-layout-id"] = String(props.layoutId);
  if (props.layout !== undefined) clean["data-layout"] = String(props.layout);
  if (typeof props.initial === "string") clean["data-motion-initial"] = props.initial;
  if (props.initial && typeof props.initial === "object") {
    clean["data-motion-initial"] = JSON.stringify(props.initial);
  }
  if (typeof props.animate === "string") clean["data-motion-animate"] = props.animate;
  if (props.variants && typeof props.variants === "object") {
    const v = props.variants as { initial?: unknown };
    clean["data-variants-initial"] = JSON.stringify(v.initial ?? null);
  }
  return clean;
}

vi.mock("framer-motion", () => ({
  motion: {
    div: ({ children, ...props }: Record<string, unknown>) => (
      <div {...stripMotionWithCapture(props)}>{children as ReactNode}</div>
    ),
    button: ({ children, ...props }: Record<string, unknown>) => (
      <button {...stripMotionWithCapture(props)}>{children as ReactNode}</button>
    ),
    span: ({ children, ...props }: Record<string, unknown>) => (
      <span {...stripMotionWithCapture(props)}>{children as ReactNode}</span>
    ),
    main: ({ children, ...props }: Record<string, unknown>) => (
      <main {...stripMotionWithCapture(props)}>{children as ReactNode}</main>
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

vi.mock("../../lib/auth", () => ({
  isGuest: vi.fn(() => false),
  isLoggedIn: vi.fn(() => true),
  getToken: vi.fn(() => "mock-token-xyz"),
  getUser: vi.fn(() => ({ id: 42, username: "cinephile", display_name: "Auteur" })),
  logout: vi.fn(),
}));

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

function mockMatchMedia(reduced: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: reduced && query.includes("prefers-reduced-motion"),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

describe("Phase 2 Shared-Element & Expand-in-Place Transitions", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    localStorage.setItem("auth_token", "test-token");
    mockMatchMedia(false);

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

  describe("DiscoverPage shared-element card -> MovieDetailSheet", () => {
    const sharedMovie = {
      id: 1,
      tmdb_id: 101,
      title: "In the Mood for Love",
      overview: "Two neighbors form an intimate bond.",
      poster_url: "https://example.com/itmf.jpg",
      backdrop_url: "https://example.com/itmf-bg.jpg",
      rating: 8.1,
      release_year: 2000,
      original_language: "zh",
    };

    function setupDiscoverMocks() {
      vi.spyOn(api, "apiRequest").mockImplementation((url) => {
        if (url.includes("/api/your-archive/")) {
          return Promise.resolve({
            success: true,
            spotlight: sharedMovie,
            shelves: [
              { id: "recommended_for_you", title: "Recommended For You", icon: "auto_awesome", movies: [sharedMovie] },
              { id: "late_night", title: "Late Night Essentials", icon: "dark_mode", movies: [sharedMovie] },
            ],
          });
        }
        if (url.includes("/api/discover/")) {
          return Promise.resolve({ success: true, movies: [sharedMovie], has_more: false });
        }
        if (url.includes("/api/watchlist/")) {
          return Promise.resolve({ watchlist: [] });
        }
        if (url.includes("/api/genres/")) {
          return Promise.resolve({ genres: [] });
        }
        return Promise.resolve({});
      });
    }

    it("assigns collision-free per-source layoutIds and morphs only the clicked shelf card poster into MovieDetailSheet", async () => {
      setupDiscoverMocks();
      const { container } = render(
        <MemoryRouter initialEntries={["/discover?view=archive"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      await screen.findByText("Recommended For You");

      // Spotlight + 2 shelves all display the same movie with distinct layoutIds (zero duplicate layoutIds in grid)
      const layoutElements = Array.from(container.querySelectorAll("[data-layout-id]"));
      const initialIds = layoutElements.map((el) => el.getAttribute("data-layout-id"));
      expect(initialIds).toContain("discover-hero-101");
      expect(initialIds).toContain("discover-shelf-recommended_for_you-0-101");
      expect(initialIds).toContain("discover-shelf-late_night-0-101");
      expect(new Set(initialIds).size).toBe(initialIds.length);

      // Click the first shelf card
      const firstShelfPoster = container.querySelector('[data-layout-id="discover-shelf-recommended_for_you-0-101"]')!;
      fireEvent.click(firstShelfPoster.closest(".cursor-pointer")!);

      const dialog = await screen.findByRole("dialog");
      expect(dialog.getAttribute("data-motion-initial")).toBe("initial");
      expect(dialog.getAttribute("data-motion-animate")).toBe("animate");

      // Should use expandModalVariants (opacity/scale), NOT bottomSheetVariants (y: "100%")
      expect(JSON.parse(dialog.getAttribute("data-variants-initial")!)).toEqual({
        opacity: 0,
        scale: 0.96,
      });

      // Only the clicked shelf poster layoutId is shared inside the detail modal
      const modalPoster = dialog.querySelector('[data-layout-id="discover-shelf-recommended_for_you-0-101"]');
      expect(modalPoster).not.toBeNull();
      expect(dialog.querySelector('[data-layout-id="discover-hero-101"]')).toBeNull();
    });

    it("links Spotlight HeroCard backdrop layoutId when opened from HeroCard", async () => {
      setupDiscoverMocks();
      const { container } = render(
        <MemoryRouter initialEntries={["/discover?view=archive"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      await screen.findByText("Spotlight Selection");
      const heroBackdrop = container.querySelector('[data-layout-id="discover-hero-101"]')!;
      fireEvent.click(heroBackdrop.closest(".cursor-pointer")!);

      const dialog = await screen.findByRole("dialog");
      expect(dialog.querySelector('[data-layout-id="discover-hero-101"]')).not.toBeNull();
    });

    it("suppresses layoutId and spatial scaling when prefers-reduced-motion is active", async () => {
      mockMatchMedia(true);
      setupDiscoverMocks();
      const { container } = render(
        <MemoryRouter initialEntries={["/discover?view=catalogue"]}>
          <DiscoverPage />
        </MemoryRouter>
      );

      const title = await screen.findByText("In the Mood for Love");
      expect(container.querySelectorAll("[data-layout-id]").length).toBe(0);

      fireEvent.click(title.closest(".cursor-pointer")!);
      const dialog = await screen.findByRole("dialog");
      expect(dialog.querySelectorAll("[data-layout-id]").length).toBe(0);
      expect(JSON.parse(dialog.getAttribute("data-variants-initial")!)).toEqual({ opacity: 0 });
    });
  });

  describe("SessionPage Match History -> Match Detail poster continuity & Room Invite expansion", () => {
    it("connects Match History row poster layoutId into Match Detail modal and clears reduced-motion transform", async () => {
      vi.spyOn(api, "apiRequest").mockImplementation((url) => {
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
              {
                session_id: 101,
                movie_id: 56,
                movie_title: "Stalker",
                rating: 8.2,
                release_year: 1979,
                poster_url: "https://example.com/stalker.jpg",
              },
            ],
          });
        }
        if (url.includes("/api/sessions/101/")) {
          return Promise.resolve({
            session: {
              id: 101,
              code: "MATCH2",
              state: "concluded",
              host_joined: true,
              guest_joined: true,
              preferences_set: true,
              user_preferences_set: true,
              user_role: "host",
              ended: true,
              matched_count: 2,
              reviewed_count: 4,
              affinity_percent: 50,
            },
          });
        }
        if (url.includes("/api/watchlist/")) {
          return Promise.resolve({ watchlist: [] });
        }
        return Promise.resolve({});
      });

      const { container, unmount } = render(
        <MemoryRouter initialEntries={["/session/101"]}>
          <Routes>
            <Route path="/session/:id" element={<SessionPage />} />
          </Routes>
        </MemoryRouter>
      );

      await screen.findByText("Screening Concluded");

      const row0Poster = container.querySelector('[data-layout-id="match-poster-55-0"]');
      const row1Poster = container.querySelector('[data-layout-id="match-poster-56-1"]');
      expect(row0Poster).not.toBeNull();
      expect(row1Poster).not.toBeNull();

      // Open details for row 1 (Stalker)
      const detailBtns = screen.getAllByRole("button", { name: /film details/i });
      fireEvent.click(detailBtns[1]);

      await waitFor(() => {
        // Two elements now carry match-poster-56-1: list row + expanded detail modal poster
        expect(container.querySelectorAll('[data-layout-id="match-poster-56-1"]').length).toBe(2);
      });
      expect(container.querySelectorAll('[data-layout-id="match-poster-55-0"]').length).toBe(1);

      fireEvent.click(screen.getByText("Close"));
      await waitFor(() => {
        expect(screen.queryByText("Close")).toBeNull();
      });
      unmount();

      // Now verify reduced motion suppresses layoutIds cleanly while modal still opens
      mockMatchMedia(true);
      const { container: reducedContainer } = render(
        <MemoryRouter initialEntries={["/session/101"]}>
          <Routes>
            <Route path="/session/:id" element={<SessionPage />} />
          </Routes>
        </MemoryRouter>
      );
      await screen.findByText("Screening Concluded");
      expect(reducedContainer.querySelectorAll("[data-layout-id]").length).toBe(0);
      fireEvent.click(screen.getAllByRole("button", { name: /film details/i })[0]);
      await screen.findByText("Close");
    });

    it("expands SessionPage Waiting Room Passcode card into inline share drawer on Share Options click", async () => {
      vi.spyOn(api, "apiRequest").mockImplementation((url) => {
        if (url.includes("/api/sessions/101/deck/card/")) {
          return Promise.resolve({ success: true, is_legacy: false });
        }
        if (url.includes("/api/sessions/101/")) {
          return Promise.resolve({
            session: {
              id: 101,
              code: "INVITE9",
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

      const shareToggle = await screen.findByRole("button", { name: /share options/i });
      expect(shareToggle.getAttribute("aria-expanded")).toBe("false");
      expect(screen.queryByTestId("waiting-share-drawer")).toBeNull();
      // Copy code and Copy Link are immediately reachable before expanding
      expect(screen.getByRole("button", { name: /copy code/i })).not.toBeNull();
      expect(screen.getByRole("button", { name: /copy link/i })).not.toBeNull();

      fireEvent.click(shareToggle);

      await waitFor(() => {
        expect(shareToggle.getAttribute("aria-expanded")).toBe("true");
        const drawer = screen.getByTestId("waiting-share-drawer");
        expect(drawer.textContent).toContain("Send via WhatsApp");
        expect(drawer.textContent).toContain("Share Invite");
      });
    });
  });

  describe("CreateSessionPage Room Invitation inline expansion & Match modal presentation", () => {
    it("expands Session Code card into inline share tray and keeps Copy Code/Copy directly accessible", async () => {
      vi.spyOn(api, "apiRequest").mockImplementation((url) => {
        if (url === "/api/sessions/create/") {
          return Promise.resolve({ success: true, id: 999, code: "EXP42X" });
        }
        if (url === "/api/sessions/genre/") {
          return Promise.resolve({ success: true, session_id: 999 });
        }
        return Promise.resolve({});
      });

      render(
        <MemoryRouter
          initialEntries={[
            {
              pathname: "/session/create",
              state: {
                preseedMovie: {
                  id: 42,
                  tmdb_id: 9942,
                  title: "Past Lives",
                  original_language: "en",
                  genres: ["Drama"],
                  genre_ids: [7],
                },
              },
            },
          ]}
        >
          <Routes>
            <Route path="/session/create" element={<CreateSessionPage />} />
          </Routes>
        </MemoryRouter>
      );

      await screen.findByText("EXP42X");

      const shareToggle = screen.getByRole("button", { name: /share options/i });
      expect(shareToggle.getAttribute("aria-expanded")).toBe("false");
      expect(screen.queryByTestId("invite-share-drawer")).toBeNull();

      fireEvent.click(shareToggle);

      await waitFor(() => {
        expect(shareToggle.getAttribute("aria-expanded")).toBe("true");
        const drawer = screen.getByTestId("invite-share-drawer");
        expect(drawer.textContent).toContain("Send via WhatsApp");
      });

      fireEvent.click(shareToggle);
      await waitFor(() => {
        expect(shareToggle.getAttribute("aria-expanded")).toBe("false");
        expect(screen.queryByTestId("invite-share-drawer")).toBeNull();
      });
    });

    it("renders CurtainCallMatchModal & SalonPassShareModal with motion entrance and opacity-only reduced-motion fallback", () => {
      vi.spyOn(salonPassCanvas, "renderSalonPassToCanvas").mockResolvedValue(undefined);
      vi.spyOn(salonPassCanvas, "getCanvasBlob").mockResolvedValue(new Blob(["bytes"], { type: "image/png" }));
      global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
      global.URL.revokeObjectURL = vi.fn();

      const { rerender } = render(
        <CurtainCallMatchModal
          matchedMovie={{
            id: 55,
            title: "Solaris",
            overview: "Psychological sci-fi.",
            rating: 8.1,
            release_year: 1972,
            superlike_attribution: "none",
            match_type: "ordinary",
          }}
          renderMode="full"
          shouldReduceMotion={false}
          userRole="host"
          isWatchlisted={false}
          watchlistLoading={false}
          onToggleWatchlist={vi.fn()}
          savedBurstId={null}
          onDismiss={vi.fn()}
          onEndSession={vi.fn().mockResolvedValue(undefined)}
          endSessionLoading={false}
          sessionLocked={false}
          sessionEnded={false}
          onFetchMetadata={vi.fn()}
          onTrailerClick={vi.fn()}
        />
      );

      const presentation = screen.getByTestId("match-presentation-card");
      const posterStage = screen.getByTestId("match-poster-stage");
      expect(JSON.parse(presentation.getAttribute("data-motion-initial")!)).toEqual({
        opacity: 0,
        scale: 0.94,
        y: 12,
      });
      expect(JSON.parse(posterStage.getAttribute("data-motion-initial")!)).toEqual({
        opacity: 0,
        scale: 0.9,
        y: 8,
      });

      rerender(
        <CurtainCallMatchModal
          matchedMovie={{
            id: 55,
            title: "Solaris",
            overview: "Psychological sci-fi.",
            rating: 8.1,
            release_year: 1972,
            superlike_attribution: "none",
            match_type: "ordinary",
          }}
          renderMode="full"
          shouldReduceMotion={true}
          userRole="host"
          isWatchlisted={false}
          watchlistLoading={false}
          onToggleWatchlist={vi.fn()}
          savedBurstId={null}
          onDismiss={vi.fn()}
          onEndSession={vi.fn().mockResolvedValue(undefined)}
          endSessionLoading={false}
          sessionLocked={false}
          sessionEnded={false}
          onFetchMetadata={vi.fn()}
          onTrailerClick={vi.fn()}
        />
      );

      expect(JSON.parse(screen.getByTestId("match-presentation-card").getAttribute("data-motion-initial")!)).toEqual({
        opacity: 0,
      });

      mockMatchMedia(true);
      render(
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

      const passDialogCard = screen.getByText("Cinéma Salon Pass").closest("[data-variants-initial]")!;
      expect(JSON.parse(passDialogCard.getAttribute("data-variants-initial")!)).toEqual({ opacity: 0 });
    });
  });
});
