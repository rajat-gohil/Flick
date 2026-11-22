import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  coordinateGuestProvisioning,
  setInvitationCode,
  getInvitationCode,
  clearInvitationCode,
} from "../guestProvisionCoordinator";
import * as apiModule from "../../lib/api";

describe("guestProvisionCoordinator", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  describe("Invitation Code Lifecycle (2-Hour TTL)", () => {
    it("stores and retrieves upper-case invitation code within 2 hours", () => {
      setInvitationCode("xyz123");
      expect(getInvitationCode()).toBe("XYZ123");
      expect(window.localStorage.getItem("flick_invitation_code")).toBe("XYZ123");
      expect(window.localStorage.getItem("pendingSessionCode")).toBe("XYZ123");
    });

    it("invalidates and clears invitation code if older than 2 hours", () => {
      setInvitationCode("expired456");
      // Set timestamp to 2 hours + 1 minute ago
      const twoHoursOneMinAgo = Date.now() - (2 * 60 * 60 * 1000 + 60 * 1000);
      window.localStorage.setItem("flick_invitation_code_ts", String(twoHoursOneMinAgo));

      expect(getInvitationCode()).toBeNull();
      expect(window.localStorage.getItem("flick_invitation_code")).toBeNull();
    });

    it("clears invitation code explicitly", () => {
      setInvitationCode("clearme");
      clearInvitationCode();
      expect(getInvitationCode()).toBeNull();
      expect(window.localStorage.getItem("flick_invitation_code")).toBeNull();
      expect(window.localStorage.getItem("pendingSessionCode")).toBeNull();
    });
  });

  describe("5-Step Web Locks Coordinator", () => {
    it("Step 1: Returns existing session immediately without making API call", async () => {
      window.localStorage.setItem("auth_token", "existing_token_abc");
      window.localStorage.setItem("user_id", "42");
      window.localStorage.setItem("username", "guest_existing");

      const provisionSpy = vi.spyOn(apiModule, "provisionGuest");

      const result = await coordinateGuestProvisioning();
      expect(result.token).toBe("existing_token_abc");
      expect(result.user.username).toBe("guest_existing");
      expect(result.replayed).toBe(true);
      expect(provisionSpy).not.toHaveBeenCalled();
    });

    it("Step 2 & 3: Re-checks auth token after acquiring lock to adopt session from competing tab", async () => {
      const provisionSpy = vi.spyOn(apiModule, "provisionGuest");

      // Mock navigator.locks.request to simulate a competing tab finishing while we wait for lock
      const originalLocks = navigator.locks;
      Object.defineProperty(navigator, "locks", {
        writable: true,
        value: {
          request: vi.fn().mockImplementation(async (_name, callback) => {
            // Simulate competing tab writing to localStorage before we get into callback
            window.localStorage.setItem("auth_token", "competing_tab_token");
            window.localStorage.setItem("username", "guest_competing");
            return callback();
          }),
        },
      });

      try {
        const result = await coordinateGuestProvisioning();
        expect(result.token).toBe("competing_tab_token");
        expect(result.user.username).toBe("guest_competing");
        expect(result.replayed).toBe(true);
        expect(provisionSpy).not.toHaveBeenCalled();
      } finally {
        Object.defineProperty(navigator, "locks", {
          writable: true,
          value: originalLocks,
        });
      }
    });

    it("Step 4 & 5: Generates idempotency key, executes provisioning, and clears key", async () => {
      const provisionSpy = vi.spyOn(apiModule, "provisionGuest").mockResolvedValueOnce({
        success: true,
        token: "fresh_guest_token",
        user: {
          id: 99,
          username: "guest_fresh",
          display_name: "Fresh Cinephile",
          is_guest: true,
        },
      } as any);

      const result = await coordinateGuestProvisioning("Fresh Cinephile");
      expect(result.token).toBe("fresh_guest_token");
      expect(window.localStorage.getItem("auth_token")).toBe("fresh_guest_token");
      expect(window.localStorage.getItem("user_id")).toBe("99");

      // Verify provisionGuest was called with a valid UUID key
      expect(provisionSpy).toHaveBeenCalledTimes(1);
      const passedKey = provisionSpy.mock.calls[0][1];
      expect(passedKey).toBeDefined();
      expect(typeof passedKey).toBe("string");
      expect(passedKey?.length).toBeGreaterThan(10);

      // Verify idempotency key was purged from localStorage upon success
      expect(window.localStorage.getItem("flick_provisioning_key")).toBeNull();
    });

    it("Handles HTTP 410 replay expiration by purging stored key", async () => {
      window.localStorage.setItem("flick_provisioning_key", "old_key_123");
      window.localStorage.setItem("flick_provisioning_key_ts", String(Date.now()));

      vi.spyOn(apiModule, "provisionGuest").mockRejectedValueOnce({
        status: 410,
        message: "Provisioning replay capability is expired or no longer available.",
      });

      await expect(coordinateGuestProvisioning()).rejects.toMatchObject({
        status: 410,
      });

      // Stored provisioning key must be purged
      expect(window.localStorage.getItem("flick_provisioning_key")).toBeNull();
    });
  });
});
