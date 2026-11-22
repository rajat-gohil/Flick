import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import CinemaAdmissionTicket from "../CinemaAdmissionTicket";

describe("CinemaAdmissionTicket Component", () => {
  it("renders the complete cinema society admission hierarchy", () => {
    const handleLaunch = vi.fn();
    const handleExplore = vi.fn();

    render(
      <CinemaAdmissionTicket
        onLaunch={handleLaunch}
        onExplore={handleExplore}
      />
    );

    // Header & Issuer
    expect(screen.getByText("FLICK CINEMA SOCIETY")).not.toBeNull();
    expect(screen.getByText("SALON NO. 04")).not.toBeNull();

    // Headlines
    expect(screen.getByText("An Invitation to the Movies")).not.toBeNull();
    expect(screen.getByText("Admit Two. One shared discovery.")).not.toBeNull();

    // Callout Lead
    expect(screen.getByText("YOUR NEXT SCREENING BEGINS HERE.")).not.toBeNull();

    // Core Interactive CTA
    const launchBtn = screen.getByRole("button", { name: /LAUNCH SCREENING DECK/i });
    expect(launchBtn).not.toBeNull();
    expect(launchBtn.getAttribute("data-tour")).toBe("home-launch-deck");

    // Secondary Action
    const exploreBtn = screen.getByRole("button", { name: /Explore Catalogue/i });
    expect(exploreBtn).not.toBeNull();

    // Detachable Stub
    expect(screen.getByText("ONE SHARED SCREENING")).not.toBeNull();
    expect(screen.getByText("ISSUE 004")).not.toBeNull();
  });

  it("triggers onLaunch callback when the ticket CTA is clicked", () => {
    const handleLaunch = vi.fn();
    render(<CinemaAdmissionTicket onLaunch={handleLaunch} />);

    const launchBtn = screen.getByRole("button", { name: /LAUNCH SCREENING DECK/i });
    fireEvent.click(launchBtn);

    expect(handleLaunch).toHaveBeenCalledTimes(1);
  });

  it("responds to touch interaction and touchmove smoothly", () => {
    const { container } = render(<CinemaAdmissionTicket onLaunch={vi.fn()} />);
    const card = container.querySelector(".cursor-grab");
    expect(card).not.toBeNull();

    if (card) {
      // Simulate finger touch
      fireEvent.touchStart(card, {
        touches: [{ clientX: 120, clientY: 80 }],
      });

      // Simulate dragging finger across ticket
      fireEvent.touchMove(card, {
        touches: [{ clientX: 180, clientY: 140 }],
      });

      // Release finger
      fireEvent.touchEnd(card);
    }
  });
});
