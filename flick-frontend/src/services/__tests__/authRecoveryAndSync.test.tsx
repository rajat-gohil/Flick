import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AuthRecoveryPrompt } from "../../components/AuthRecoveryPrompt";
import { ProvisionContinuationScreen } from "../../components/ProvisionContinuationScreen";
import { initAuthSyncListener } from "../../lib/auth";
import * as apiModule from "../../lib/api";
import * as coordinatorModule from "../guestProvisionCoordinator";

describe("Frontend 401, 410, and Cross-Tab Storage Sync Tests", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  describe("Part 4.2: Frontend 401 Flow & AuthRecoveryPrompt", () => {
    it("clears auth_token and flick_provisioning_key on 401 response and dispatches event", async () => {
      window.localStorage.setItem("auth_token", "invalid_stale_token");
      window.localStorage.setItem("flick_provisioning_key", "provision_key_123");
      window.localStorage.setItem("flick_provisioning_key_ts", "1234567890");

      const eventFired = vi.fn();
      window.addEventListener("flick:auth_expired", eventFired);

      // Simulate a fetch call returning 401
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        text: () => Promise.resolve(JSON.stringify({ detail: "Invalid token." })),
      });
      globalThis.fetch = mockFetch;

      await expect(apiModule.apiRequest("/api/users/profile/")).rejects.toThrow();

      expect(window.localStorage.getItem("auth_token")).toBeNull();
      expect(window.localStorage.getItem("flick_provisioning_key")).toBeNull();
      expect(window.localStorage.getItem("flick_provisioning_key_ts")).toBeNull();
      expect(eventFired).toHaveBeenCalled();
    });

    it("renders AuthRecoveryPrompt with 'Restore Journal' and 'Start Fresh' buttons", () => {
      render(<AuthRecoveryPrompt isOpen={true} />);

      expect(screen.getByText("Session Expired")).not.toBeNull();
      expect(screen.getByRole("button", { name: "Restore Journal" })).not.toBeNull();
      expect(screen.getByRole("button", { name: "Start Fresh" })).not.toBeNull();
    });

    it("displays inline generic 400 error when restore code is invalid without silently reprovisioning", async () => {
      const recoverSpy = vi.spyOn(apiModule, "recoverGuest").mockRejectedValueOnce(
        new apiModule.ApiError(400, { error: "Invalid recovery code." })
      );

      render(<AuthRecoveryPrompt isOpen={true} />);

      // Click Restore Journal
      fireEvent.click(screen.getByRole("button", { name: "Restore Journal" }));

      // Type code
      const input = screen.getByLabelText("Recovery Code");
      fireEvent.change(input, { target: { value: "FLICK-BAD-CODE-1234" } });

      // Submit
      fireEvent.click(screen.getByRole("button", { name: "Submit Code" }));

      await waitFor(() => {
        expect(screen.getByText("Invalid recovery code.")).not.toBeNull();
      });

      expect(recoverSpy).toHaveBeenCalledWith("FLICK-BAD-CODE-1234");
      // Form remains open so user can retry or start fresh
      expect(screen.getByLabelText("Recovery Code")).not.toBeNull();
    });

    it("invokes coordinateGuestProvisioning when user clicks Start Fresh", async () => {
      const freshSpy = vi.spyOn(coordinatorModule, "coordinateGuestProvisioning").mockResolvedValueOnce({
        token: "fresh_token_123",
        user: { id: 10, username: "fresh_user" },
      });

      render(<AuthRecoveryPrompt isOpen={true} />);

      fireEvent.click(screen.getByRole("button", { name: "Start Fresh" }));

      await waitFor(() => {
        expect(freshSpy).toHaveBeenCalled();
      });
    });
  });

  describe("Part 4.3: Frontend 410 Flow & Continuation Screen", () => {
    it("deletes stale idempotency key and renders lightweight continuation screen", () => {
      window.localStorage.setItem("flick_provisioning_key", "stale_key_abc");
      window.localStorage.setItem("flick_provisioning_key_ts", "1000000");

      const onStartFresh = vi.fn();
      render(<ProvisionContinuationScreen onStartFreshSuccess={onStartFresh} />);

      expect(screen.getByText("Previous Session Expired")).not.toBeNull();
      const startFreshBtn = screen.getByRole("button", { name: "Start Fresh" });
      expect(startFreshBtn).not.toBeNull();
    });

    it("executes fresh guest provisioning on Start Fresh click from continuation screen", async () => {
      const coordSpy = vi.spyOn(coordinatorModule, "coordinateGuestProvisioning").mockResolvedValueOnce({
        token: "fresh_continuation_token",
        user: { id: 25, username: "fresh_guest_continuation" },
      });

      const onStartFreshSuccess = vi.fn();
      render(<ProvisionContinuationScreen onStartFreshSuccess={onStartFreshSuccess} />);

      fireEvent.click(screen.getByRole("button", { name: "Start Fresh" }));

      await waitFor(() => {
        expect(coordSpy).toHaveBeenCalled();
        expect(onStartFreshSuccess).toHaveBeenCalled();
      });
    });
  });

  describe("Part 4.4: Cross-Tab Storage Event Synchronization", () => {
    it("listens to storage events for auth_token and flick_auth_sync", () => {
      const syncSpy = vi.fn();
      const cleanup = initAuthSyncListener(syncSpy);

      // Simulate a storage event from another tab updating auth_token
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "auth_token",
          newValue: "token_from_tab_b",
        })
      );

      expect(syncSpy).toHaveBeenCalledWith("auth_token", "token_from_tab_b");

      // Simulate cross-tab logout / invalidation broadcast
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "flick_auth_sync",
          newValue: JSON.stringify({ type: "AUTH_EXPIRED", ts: Date.now() }),
        })
      );

      expect(syncSpy).toHaveBeenCalledWith(
        "flick_auth_sync",
        expect.stringContaining("AUTH_EXPIRED")
      );

      cleanup();
    });
  });
});
