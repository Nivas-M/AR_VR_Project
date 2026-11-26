import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import * as THREE from "three";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ArViewerPage from "../pages/ArViewerPage";
import { exportSceneToUsdzBlob, exportSceneToUsdzBuffer } from "../utils/usdzExport";

describe("True-Scale AR Viewer and USDZExporter", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => "blob:mock-usdz-url");
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
    globalThis.fetch = vi.fn(async (url) => {
      if (url === "/api/models/demo123/meta") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({
            model_id: "demo123",
            title: "Nordic Tufted Accent Armchair",
            scale_report: {
              bounding_box_m: { width: 0.78, height: 0.84, depth: 0.74, min_y: 0.0 },
            },
          }),
        };
      }
      return {
        ok: false,
        status: 404,
        headers: { get: () => "text/plain" },
        text: async () => "Not found",
      };
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("exports a Three.js scene to a valid USDZ archive blob", async () => {
    const scene = new THREE.Scene();
    const box = new THREE.Mesh(
      new THREE.BoxGeometry(0.78, 0.84, 0.74),
      new THREE.MeshStandardMaterial({ color: 0x2d6c84 })
    );
    scene.add(box);

    const buffer = await exportSceneToUsdzBuffer(scene);
    const header = new Uint8Array(buffer.slice(0, 2));
    // USDZ is an uncompressed ZIP archive whose magic header starts with 'PK' (0x50, 0x4B)
    expect(header[0]).toBe(0x50);
    expect(header[1]).toBe(0x4b);

    const blob = await exportSceneToUsdzBlob(scene);
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe("model/vnd.usdz+zip");
    expect(blob.size).toBeGreaterThan(200);
  });

  it("renders model-viewer with locked 1:1 AR scale and opens QR handoff modal", async () => {
    render(
      <MemoryRouter initialEntries={["/ar/demo123"]}>
        <Routes>
          <Route path="/ar/:id" element={<ArViewerPage />} />
        </Routes>
      </MemoryRouter>
    );

    const viewer = screen.getByTestId("ar-model-viewer");
    expect(viewer).toHaveAttribute("src", "/api/models/demo123.glb");
    expect(viewer).toHaveAttribute("ar-scale", "fixed");
    expect(viewer).toHaveAttribute("ar-modes", "webxr scene-viewer quick-look");
    expect(viewer).toHaveAttribute("ar-placement", "floor");
    expect(viewer).toHaveAttribute("ar");

    await waitFor(() =>
      expect(screen.getByText(/Nordic Tufted Accent Armchair/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/78\.0 × 84\.0 × 74\.0 cm/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Scan QR to Place from Phone/i }));
    expect(screen.getByRole("dialog", { name: /QR Code Phone Handoff/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Mobile AR URL/i)).toBeInTheDocument();
  });
});
