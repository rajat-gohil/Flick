import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import SalonPassShareModal from "../SalonPassShareModal";
import * as salonPassCanvas from "../../../lib/salonPassCanvas";

describe("SalonPassShareModal Component", () => {
  const defaultData: salonPassCanvas.SalonPassData = {
    movieTitle: "Inception",
    releaseYear: 2010,
    rating: 8.8,
    posterUrl: "https://image.tmdb.org/t/p/w500/test.jpg",
    sessionCode: "ABC123",
    userRole: "host",
    partnerNames: "Rajat & Priya",
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(salonPassCanvas, "renderSalonPassToCanvas").mockResolvedValue(undefined);
    vi.spyOn(salonPassCanvas, "getCanvasBlob").mockResolvedValue(
      new Blob(["mock-image-bytes"], { type: "image/png" })
    );

    // Mock URL.createObjectURL and revokeObjectURL in jsdom
    if (!global.URL.createObjectURL) {
      global.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    } else {
      vi.spyOn(global.URL, "createObjectURL").mockReturnValue("blob:mock-url");
    }
    if (!global.URL.revokeObjectURL) {
      global.URL.revokeObjectURL = vi.fn();
    } else {
      vi.spyOn(global.URL, "revokeObjectURL").mockImplementation(() => {});
    }
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not render when isOpen is false", () => {
    render(<SalonPassShareModal isOpen={false} onClose={vi.fn()} data={defaultData} />);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders modal with header and buttons when isOpen is true", async () => {
    render(<SalonPassShareModal isOpen={true} onClose={vi.fn()} data={defaultData} />);
    expect(screen.getByRole("dialog")).not.toBeNull();
    expect(screen.getByText("Cinéma Salon Pass")).not.toBeNull();
    expect(screen.getByText(/Instagram Story & WhatsApp Status ready/i)).not.toBeNull();
    expect(screen.getByText("Share to Instagram / WhatsApp")).not.toBeNull();
    expect(screen.getByText("Save PNG")).not.toBeNull();
    expect(screen.getByText("Copy Link")).not.toBeNull();
  });

  it("calls onClose when close button is clicked", () => {
    const handleClose = vi.fn();
    render(<SalonPassShareModal isOpen={true} onClose={handleClose} data={defaultData} />);
    const closeBtn = screen.getByLabelText("Close modal");
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it("handles copy link to clipboard", async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    render(<SalonPassShareModal isOpen={true} onClose={vi.fn()} data={defaultData} />);
    const copyBtn = screen.getByText("Copy Link");
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalledWith("https://flick-kappa.vercel.app");
    });
  });

  it("calls shareOrDownloadSalonPass when Share button is clicked", async () => {
    const shareSpy = vi
      .spyOn(salonPassCanvas, "shareOrDownloadSalonPass")
      .mockResolvedValue({ success: true, method: "share" });

    render(<SalonPassShareModal isOpen={true} onClose={vi.fn()} data={defaultData} />);

    // Wait for generator to finish
    await waitFor(() => {
      const btn = screen.getByText("Share to Instagram / WhatsApp").closest("button");
      expect(btn?.disabled).toBe(false);
    });

    const shareBtn = screen.getByText("Share to Instagram / WhatsApp");
    fireEvent.click(shareBtn);

    await waitFor(() => {
      expect(shareSpy).toHaveBeenCalled();
    });
  });

  it("calls triggerFileDownload when Save PNG button is clicked", async () => {
    const downloadSpy = vi.spyOn(salonPassCanvas, "triggerFileDownload").mockImplementation(() => {});

    render(<SalonPassShareModal isOpen={true} onClose={vi.fn()} data={defaultData} />);

    await waitFor(() => {
      const btn = screen.getByText("Save PNG").closest("button");
      expect(btn?.disabled).toBe(false);
    });

    const saveBtn = screen.getByText("Save PNG");
    fireEvent.click(saveBtn);

    expect(downloadSpy).toHaveBeenCalledWith(expect.anything(), "flick-match-inception.png");
  });
});
