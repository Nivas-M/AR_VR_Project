import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import StudioPage from "../pages/StudioPage";

describe("Photo-to-3D StudioPage and ModelScaleInspector", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn(async (url) => {
      if (url === "/api/products") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({
            products: [
              {
                id: "nordic-armchair",
                title: "Nordic Tufted Accent Armchair",
                width_cm: 78,
                height_cm: 84,
                depth_cm: 74,
              },
            ],
          }),
        };
      }
      if (url === "/api/reconstruct") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({
            job_id: "job123",
            model_id: "mdl123",
            status: "queued",
            progress: 10,
            stage_message: "Queued",
          }),
        };
      }
      if (url === "/api/jobs/job123") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({
            job_id: "job123",
            model_id: "mdl123",
            title: "Custom Chair",
            status: "done",
            progress: 100,
            duration_ms: 420,
            stage_message: "True-scale 3D model ready",
            model_url: "/api/models/mdl123.glb",
            scale_report: {
              bounding_box_m: { width: 0.78, height: 0.84, depth: 0.74, min_y: 0.0 },
              max_dimension_error_m: 0.0,
            },
            mesh_stats: {
              vertex_count: 2400,
              face_count: 4800,
              mode_used: "multi_view_visual_hull",
            },
          }),
        };
      }
      return {
        ok: true,
        headers: { get: () => "application/json" },
        json: async () => ({}),
      };
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("converts WxHxD units between cm and in, uploads photos, and renders scale inspector", async () => {
    render(
      <MemoryRouter>
        <StudioPage />
      </MemoryRouter>
    );

    // Verify cm -> in conversion on dimension inputs
    const inBtn = screen.getByRole("button", { name: "in" });
    fireEvent.click(inBtn);
    expect(screen.getByLabelText(/Width \(in\)/i)).toHaveValue(30.7);
    expect(screen.getByLabelText(/Height \(in\)/i)).toHaveValue(33.1);

    // Switch back to cm
    fireEvent.click(screen.getByRole("button", { name: "cm" }));
    expect(screen.getByLabelText(/Width \(cm\)/i)).toHaveValue(78);

    // Upload two photos and check angle selectors appear
    const fileInput = screen.getByLabelText(/Upload product photos/i);
    const frontFile = new File(["png"], "front.png", { type: "image/png" });
    const sideFile = new File(["png"], "side.png", { type: "image/png" });
    fireEvent.change(fileInput, { target: { files: [frontFile, sideFile] } });

    expect(screen.getByLabelText(/Angle for front\.png/i)).toHaveValue("front");
    expect(screen.getByLabelText(/Angle for side\.png/i)).toHaveValue("side");

    // Submit reconstruction
    fireEvent.click(screen.getByRole("button", { name: /Generate True-Scale 3D/i }));

    await waitFor(() =>
      expect(screen.getByText(/Metric Scale Verified/i)).toBeInTheDocument()
    );

    // Inspector reference controls & AR link should be present
    expect(screen.getByRole("button", { name: /175 cm Person/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /200 cm Doorframe/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /75 cm Desk/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open True-Scale AR Viewer/i })).toHaveAttribute(
      "href",
      "/ar/mdl123"
    );
  });
});
