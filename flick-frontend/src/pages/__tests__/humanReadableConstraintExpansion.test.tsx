import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { ConstraintExhaustionNoticeModal } from "../../components/session/ConstraintExhaustionNoticeModal";
import {
  CANONICAL_GENRES,
  CANONICAL_LANGUAGES,
  CANONICAL_ERAS,
  resolveGenreName,
  formatLanguageName,
  formatEraName,
  formatConstraintLabel,
  formatConstraintValue,
  updateGenreCache,
} from "../../lib/formatConstraints";

// Mock analytics
vi.mock("../../lib/analytics", () => ({
  trackEvent: vi.fn(),
}));

const mockApiRequest = vi.fn();
vi.mock("../../lib/api", () => ({
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
  getWsUrl: () => "ws://localhost:8000/ws/session/87/",
}));

describe("Human-Readable Constraint Expansion Proposal Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -------------------------------------------------------------------------
  // 1. Direct Unit Tests for Formatting & Lookup Functions
  // -------------------------------------------------------------------------
  describe("Formatting & Lookup Utility Functions", () => {
    it("resolves canonical genre ID 27 to Horror", () => {
      expect(resolveGenreName(27)).toBe("Horror");
      expect(CANONICAL_GENRES[27]).toBe("Horror");
    });

    it("resolves multiple genre IDs to comma-separated names", () => {
      const formatted = formatConstraintValue("required_genre_ids", [27, 53]);
      expect(formatted).toBe("Horror, Thriller");
    });

    it("converts Gujarati code 'gu' to Gujarati", () => {
      expect(formatLanguageName("gu")).toBe("Gujarati");
      expect(CANONICAL_LANGUAGES["gu"]).toBe("Gujarati");
    });

    it("converts other canonical languages (Hindi, English, Japanese)", () => {
      expect(formatLanguageName("hi")).toBe("Hindi");
      expect(formatLanguageName("en")).toBe("English");
      expect(formatLanguageName("ja")).toBe("Japanese");
    });

    it("converts internal era value 'any' to Any Era", () => {
      expect(formatEraName("any")).toBe("Any Era");
      expect(CANONICAL_ERAS["any"]).toBe("Any Era");
    });

    it("converts other internal era values accurately", () => {
      expect(formatEraName("recent")).toBe("Recent (2020+)");
      expect(formatEraName("2010s")).toBe("2010s");
      expect(formatEraName("2000s")).toBe("2000s");
      expect(formatEraName("90s")).toBe("1990s");
      expect(formatEraName("before_1990")).toBe("Before 1990");
      expect(formatEraName("classic")).toBe("Classic (Before 1990)");
    });

    it("renders null minimum rating as 'No minimum rating'", () => {
      expect(formatConstraintValue("shared_min_rating", null)).toBe("No minimum rating");
      expect(formatConstraintValue("min_rating", null)).toBe("No minimum rating");
      expect(formatConstraintValue("shared_min_rating", undefined)).toBe("No minimum rating");
      expect(formatConstraintValue("shared_min_rating", "")).toBe("No minimum rating");
    });

    it("renders non-null minimum rating formatted with + rating", () => {
      expect(formatConstraintValue("shared_min_rating", 6.5)).toBe("6.5+ rating");
      expect(formatConstraintValue("shared_min_rating", "7.00")).toBe("7.0+ rating");
    });

    it("renders null maximum runtime as 'No runtime limit'", () => {
      expect(formatConstraintValue("shared_max_runtime", null)).toBe("No runtime limit");
      expect(formatConstraintValue("max_runtime", null)).toBe("No runtime limit");
      expect(formatConstraintValue("shared_max_runtime", undefined)).toBe("No runtime limit");
      expect(formatConstraintValue("shared_max_runtime", "")).toBe("No runtime limit");
    });

    it("renders non-null maximum runtime in minutes", () => {
      expect(formatConstraintValue("shared_max_runtime", 140)).toBe("140 minutes");
      expect(formatConstraintValue("shared_max_runtime", "120")).toBe("120 minutes");
    });

    it("renders empty arrays as 'None'", () => {
      expect(formatConstraintValue("excluded_genre_ids", [])).toBe("None");
      expect(formatConstraintValue("required_genre_ids", [])).toBe("None");
      expect(formatConstraintValue("shared_eras", [])).toBe("None");
      expect(formatConstraintValue("shared_languages", [])).toBe("None");
    });

    it("handles unknown IDs and codes defensively without crashing", () => {
      // Unknown genre ID
      expect(resolveGenreName(99999)).toBe("Genre 99999");
      expect(formatConstraintValue("required_genre_ids", [99999])).toBe("Genre 99999");

      // Unknown language code
      expect(formatLanguageName("xyz")).toBe("XYZ");
      expect(formatConstraintValue("shared_languages", ["xyz"])).toBe("XYZ");

      // Unknown era
      expect(formatEraName("space_age")).toBe("Space Age");
      expect(formatConstraintValue("shared_eras", ["space_age"])).toBe("Space Age");
    });

    it("augments genre resolution with dynamic genre cache from /api/genres/", () => {
      updateGenreCache([{ id: 501, tmdb_id: 801, name: "Cyberpunk Noir" }]);
      expect(resolveGenreName(801)).toBe("Cyberpunk Noir");
      expect(resolveGenreName(501)).toBe("Cyberpunk Noir");
    });

    it("formats constraint keys into human-friendly labels", () => {
      expect(formatConstraintLabel("shared_min_rating")).toBe("Min Rating");
      expect(formatConstraintLabel("shared_max_runtime")).toBe("Max Runtime");
      expect(formatConstraintLabel("shared_eras")).toBe("Eras");
      expect(formatConstraintLabel("shared_languages")).toBe("Languages");
      expect(formatConstraintLabel("required_genre_ids")).toBe("Required Genres");
      expect(formatConstraintLabel("excluded_genre_ids")).toBe("Excluded Genres");
    });
  });

  // -------------------------------------------------------------------------
  // 2. Component Integration Tests (ConstraintExhaustionNoticeModal)
  // -------------------------------------------------------------------------
  describe("ConstraintExhaustionNoticeModal Human-Readable Presentation", () => {
    const rawProposalData = {
      id: "prop-human-100",
      session_id: 87,
      status: "pending",
      initiated_by_user_id: 1,
      initiated_by_username: "host_user",
      original_constraints: {
        shared_min_rating: "7.00",
        shared_max_runtime: 120,
        shared_eras: ["any"],
        shared_languages: ["gu"],
        excluded_genre_ids: [],
        required_genre_ids: [27],
      },
      proposed_constraints: {
        shared_min_rating: null,
        shared_max_runtime: null,
        shared_eras: ["any"],
        shared_languages: ["gu"],
        excluded_genre_ids: [],
        required_genre_ids: [27],
      },
      host_decision: { decision: "approve", decided_at: "2026-11-13T23:30:00Z" },
      guest_decision: { decision: "pending", decided_at: null },
      created_at: "2026-11-13T23:30:00Z",
      expires_at: "2026-11-13T23:45:00Z",
      is_expired: false,
      is_mutually_approved: false,
    };

    it("displays human-readable labels instead of developer-facing raw values", async () => {
      mockApiRequest.mockImplementation((url: string) => {
        if (url.includes("/api/sessions/87/expand-constraints/")) {
          return Promise.resolve({
            success: true,
            active_proposal: rawProposalData,
          });
        }
        if (url.includes("/api/genres/")) {
          return Promise.resolve({
            success: true,
            genres: [{ id: 11, tmdb_id: 27, name: "Horror" }],
          });
        }
        return Promise.resolve({});
      });

      render(
        <ConstraintExhaustionNoticeModal
          isOpen={true}
          sessionId="87"
          userRole="guest"
          onClose={vi.fn()}
        />
      );

      // Verify modal is loaded
      await waitFor(() => {
        expect(screen.getByText("Candidate Pool Exhausted")).toBeTruthy();
      });

      // 1. Genre ID 27 renders as "Horror"
      const requiredGenresVal = screen.getByTestId("constraint-val-required_genre_ids");
      expect(requiredGenresVal.textContent).toBe("Horror");

      // 2. Language code "gu" renders as "Gujarati"
      const languagesVal = screen.getByTestId("constraint-val-shared_languages");
      expect(languagesVal.textContent).toBe("Gujarati");

      // 3. Era value "any" renders as "Any Era"
      const erasVal = screen.getByTestId("constraint-val-shared_eras");
      expect(erasVal.textContent).toBe("Any Era");

      // 4. Null minimum rating renders as "No minimum rating"
      const minRatingVal = screen.getByTestId("constraint-val-shared_min_rating");
      expect(minRatingVal.textContent).toBe("No minimum rating");

      // 5. Null maximum runtime renders as "No runtime limit"
      const maxRuntimeVal = screen.getByTestId("constraint-val-shared_max_runtime");
      expect(maxRuntimeVal.textContent).toBe("No runtime limit");

      // 6. Empty excluded genres renders as "None"
      const excludedGenresVal = screen.getByTestId("constraint-val-excluded_genre_ids");
      expect(excludedGenresVal.textContent).toBe("None");

      // 7. Verify raw technical tokens are NEVER visible
      const modalText = screen.getByRole("dialog").textContent || "";
      expect(modalText).not.toContain('["any"]');
      expect(modalText).not.toContain('["gu"]');
      expect(modalText).not.toContain('[27]');
      expect(modalText).not.toContain("null");
      expect(modalText).not.toContain("undefined");
    });

    it("renders multiple genres as comma-separated human-readable names", async () => {
      const multiProposal = {
        ...rawProposalData,
        proposed_constraints: {
          ...rawProposalData.proposed_constraints,
          required_genre_ids: [27, 53, 878],
          shared_languages: ["gu", "hi", "en"],
        },
      };

      mockApiRequest.mockImplementation((url: string) => {
        if (url.includes("/api/sessions/87/expand-constraints/")) {
          return Promise.resolve({
            success: true,
            active_proposal: multiProposal,
          });
        }
        return Promise.resolve({});
      });

      render(
        <ConstraintExhaustionNoticeModal
          isOpen={true}
          sessionId="87"
          userRole="guest"
          onClose={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId("constraint-val-required_genre_ids").textContent).toBe(
          "Horror, Thriller, Science Fiction"
        );
        expect(screen.getByTestId("constraint-val-shared_languages").textContent).toBe(
          "Gujarati, Hindi, English"
        );
      });
    });

    it("handles unknown genre IDs gracefully without crashing", async () => {
      const unknownProposal = {
        ...rawProposalData,
        proposed_constraints: {
          ...rawProposalData.proposed_constraints,
          required_genre_ids: [99999],
          shared_languages: ["xyz"],
        },
      };

      mockApiRequest.mockImplementation((url: string) => {
        if (url.includes("/api/sessions/87/expand-constraints/")) {
          return Promise.resolve({
            success: true,
            active_proposal: unknownProposal,
          });
        }
        return Promise.resolve({});
      });

      render(
        <ConstraintExhaustionNoticeModal
          isOpen={true}
          sessionId="87"
          userRole="guest"
          onClose={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId("constraint-val-required_genre_ids").textContent).toBe(
          "Genre 99999"
        );
        expect(screen.getByTestId("constraint-val-shared_languages").textContent).toBe(
          "XYZ"
        );
      });
    });

    it("ensures both participants see identical human-readable proposal details", async () => {
      mockApiRequest.mockImplementation((url: string) => {
        if (url.includes("/api/sessions/87/expand-constraints/")) {
          return Promise.resolve({
            success: true,
            active_proposal: rawProposalData,
          });
        }
        return Promise.resolve({});
      });

      // Render as Host
      const { unmount } = render(
        <ConstraintExhaustionNoticeModal
          isOpen={true}
          sessionId="87"
          userRole="host"
          onClose={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId("constraint-val-required_genre_ids").textContent).toBe("Horror");
        expect(screen.getByTestId("constraint-val-shared_languages").textContent).toBe("Gujarati");
      });
      unmount();

      // Render as Guest
      render(
        <ConstraintExhaustionNoticeModal
          isOpen={true}
          sessionId="87"
          userRole="guest"
          onClose={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByTestId("constraint-val-required_genre_ids").textContent).toBe("Horror");
        expect(screen.getByTestId("constraint-val-shared_languages").textContent).toBe("Gujarati");
      });
    });

    it("preserves existing approval and rejection voting behaviour intact", async () => {
      let dispatchedAction: Record<string, unknown> | null = null;
      mockApiRequest.mockImplementation((url: string, opts?: { method?: string; body?: string }) => {
        if (url.includes("/api/sessions/87/expand-constraints/")) {
          if (opts?.method === "POST" && opts.body) {
            dispatchedAction = JSON.parse(opts.body) as Record<string, unknown>;
            return Promise.resolve({ success: true });
          }
          return Promise.resolve({
            success: true,
            active_proposal: rawProposalData,
          });
        }
        return Promise.resolve({});
      });

      render(
        <ConstraintExhaustionNoticeModal
          isOpen={true}
          sessionId="87"
          userRole="guest"
          onClose={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /approve/i })).toBeTruthy();
      });

      // Guest approves
      fireEvent.click(screen.getByRole("button", { name: /approve/i }));

      await waitFor(() => {
        expect(dispatchedAction).toEqual({
          action: "respond",
          proposal_id: "prop-human-100",
          decision: "approve",
        });
      });
    });

    it("preserves decline voting behaviour intact", async () => {
      let dispatchedAction: Record<string, unknown> | null = null;
      mockApiRequest.mockImplementation((url: string, opts?: { method?: string; body?: string }) => {
        if (url.includes("/api/sessions/87/expand-constraints/")) {
          if (opts?.method === "POST" && opts.body) {
            dispatchedAction = JSON.parse(opts.body) as Record<string, unknown>;
            return Promise.resolve({ success: true });
          }
          return Promise.resolve({
            success: true,
            active_proposal: rawProposalData,
          });
        }
        return Promise.resolve({});
      });

      render(
        <ConstraintExhaustionNoticeModal
          isOpen={true}
          sessionId="87"
          userRole="guest"
          onClose={vi.fn()}
        />
      );

      await waitFor(() => {
        expect(screen.getByRole("button", { name: /decline/i })).toBeTruthy();
      });

      // Guest declines
      fireEvent.click(screen.getByRole("button", { name: /decline/i }));

      await waitFor(() => {
        expect(dispatchedAction).toEqual({
          action: "respond",
          proposal_id: "prop-human-100",
          decision: "decline",
        });
      });
    });
  });
});
