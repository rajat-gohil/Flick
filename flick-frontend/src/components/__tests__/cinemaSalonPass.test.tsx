import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import CinemaSalonPass from "../CinemaSalonPass";

describe("CinemaSalonPass Component", () => {
  it("renders the salon pass hierarchy and elements", () => {
    const handleJoin = vi.fn();
    const setJoinCode = vi.fn();

    render(
      <CinemaSalonPass
        joinCode=""
        setJoinCode={setJoinCode}
        onJoin={handleJoin}
        loading={false}
      />
    );

    expect(screen.getByText("Direct Salon Entry")).not.toBeNull();
    expect(screen.getByText("ROOM INVITATION")).not.toBeNull();
    expect(screen.getByPlaceholderText("ENTER 6-DIGIT CODE")).not.toBeNull();
    expect(screen.getByLabelText("Enter session")).not.toBeNull();
    expect(screen.getByText("No account needed for guests")).not.toBeNull();
    expect(screen.getByText("Synced Live")).not.toBeNull();
  });

  it("sanitizes input to uppercase alphanumeric characters capped at 6 chars", () => {
    const setJoinCode = vi.fn();

    render(
      <CinemaSalonPass
        joinCode=""
        setJoinCode={setJoinCode}
        onJoin={vi.fn()}
        loading={false}
      />
    );

    const input = screen.getByPlaceholderText("ENTER 6-DIGIT CODE");
    // Enter lowercase with special characters and > 6 chars
    fireEvent.change(input, { target: { value: "abc-123_xyz" } });

    // Should sanitize to ABC123 (6 chars uppercase alphanumeric only)
    expect(setJoinCode).toHaveBeenCalledWith("ABC123");
  });

  it("triggers onJoin when button is clicked or Enter is pressed with valid code", () => {
    const handleJoin = vi.fn();

    render(
      <CinemaSalonPass
        joinCode="ABC123"
        setJoinCode={vi.fn()}
        onJoin={handleJoin}
        loading={false}
      />
    );

    const button = screen.getByLabelText("Enter session");
    fireEvent.click(button);
    expect(handleJoin).toHaveBeenCalledTimes(1);

    const input = screen.getByPlaceholderText("ENTER 6-DIGIT CODE");
    fireEvent.keyDown(input, { key: "Enter" });
    expect(handleJoin).toHaveBeenCalledTimes(2);
  });

  it("displays error message in an accessible alert role", () => {
    render(
      <CinemaSalonPass
        joinCode="BADCOD"
        setJoinCode={vi.fn()}
        onJoin={vi.fn()}
        loading={false}
        error="Invalid or expired session code"
      />
    );

    const alert = screen.getByRole("alert");
    expect(alert).not.toBeNull();
    expect(screen.getByText("Invalid or expired session code")).not.toBeNull();
  });

  it("handles mobile touch interaction and pointer move smoothly", () => {
    const { container } = render(
      <CinemaSalonPass
        joinCode=""
        setJoinCode={vi.fn()}
        onJoin={vi.fn()}
        loading={false}
      />
    );

    const card = container.querySelector(".cursor-grab");
    expect(card).not.toBeNull();

    if (card) {
      fireEvent.touchStart(card, {
        touches: [{ clientX: 100, clientY: 50 }],
      });
      fireEvent.touchMove(card, {
        touches: [{ clientX: 150, clientY: 90 }],
      });
      fireEvent.touchEnd(card);
    }
  });
});
