import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";

const MOCK_PRODUCTS = [
  {
    id: "nordic-armchair",
    title: "Nordic Tufted Accent Armchair",
    brand: "FjordHome",
    category: "Living Room",
    price_usd: 289.0,
    rating: 4.7,
    review_count: 1284,
    description: "Mid-century reading armchair.",
    material: "Woven Polyester Linen & Solid Ash Wood",
    color: "Slate Teal / Natural Oak",
    width_cm: 78,
    height_cm: 84,
    depth_cm: 74,
    weight_kg: 16.5,
    dimensions_in: { width: 30.7, height: 33.1, depth: 29.1 },
    highlights: ["True-scale dimensions: 78 × 84 × 74 cm"],
    images: [
      { angle: "front", filename: "front.png", label: "Front View", url: "/api/products/nordic-armchair/images/front.png" },
      { angle: "side", filename: "side.png", label: "Side Profile", url: "/api/products/nordic-armchair/images/side.png" },
    ],
  },
  {
    id: "studio-bluetooth-speaker",
    title: "Acoustic Fabric Tabletop Bluetooth Speaker",
    brand: "SoundForm",
    category: "Audio",
    price_usd: 129.0,
    rating: 4.9,
    review_count: 2140,
    description: "Compact wireless speaker.",
    material: "Acoustic Textile",
    color: "Charcoal Mesh",
    width_cm: 28,
    height_cm: 18,
    depth_cm: 16,
    weight_kg: 2.1,
    dimensions_in: { width: 11.0, height: 7.1, depth: 6.3 },
    highlights: ["Compact footprint"],
    images: [
      { angle: "front", filename: "front.png", label: "Front View", url: "/api/products/studio-bluetooth-speaker/images/front.png" },
    ],
  },
];

describe("ShopScale Storefront -> Generate 3D -> True-Scale AR Viewer flow", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    if (!URL.createObjectURL) {
      URL.createObjectURL = vi.fn(() => "blob:mock-usdz-url");
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = vi.fn();
    }
    globalThis.fetch = vi.fn(async (url) => {
      if (url === "/api/health") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({ status: "ok", default_engine: "local_cpu" }),
        };
      }
      if (url === "/api/products") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({ products: MOCK_PRODUCTS, count: 2 }),
        };
      }
      if (url === "/api/products/nordic-armchair") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => MOCK_PRODUCTS[0],
        };
      }
      if (url === "/api/reconstruct") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({
            job_id: "job_shop_1",
            model_id: "mdl_shop_1",
            status: "queued",
            progress: 10,
            stage_message: "Queued",
          }),
        };
      }
      if (url === "/api/jobs/job_shop_1") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({
            job_id: "job_shop_1",
            model_id: "mdl_shop_1",
            title: "Nordic Tufted Accent Armchair",
            status: "done",
            progress: 100,
            stage_message: "True-scale 3D model ready",
            model_url: "/api/models/mdl_shop_1.glb",
            scale_report: {
              bounding_box_m: { width: 0.78, height: 0.84, depth: 0.74, min_y: 0.0 },
            },
          }),
        };
      }
      if (url === "/api/models/mdl_shop_1/meta") {
        return {
          ok: true,
          headers: { get: () => "application/json" },
          json: async () => ({
            model_id: "mdl_shop_1",
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

  it("filters storefront products, inspects detail page, generates 3D, and opens AR viewer", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    await waitFor(() =>
      expect(screen.getByText(/Nordic Tufted Accent Armchair/i)).toBeInTheDocument()
    );
    expect(screen.getByText(/Acoustic Fabric Tabletop Bluetooth Speaker/i)).toBeInTheDocument();

    // Filter by category
    fireEvent.click(screen.getByRole("button", { name: "Audio" }));
    expect(screen.queryByText(/Nordic Tufted Accent Armchair/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Acoustic Fabric Tabletop Bluetooth Speaker/i)).toBeInTheDocument();

    // Reset filter and search
    fireEvent.click(screen.getByRole("button", { name: "All" }));
    fireEvent.change(screen.getByLabelText(/Search ShopScale products/i), {
      target: { value: "Armchair" },
    });
    expect(screen.getByText(/Nordic Tufted Accent Armchair/i)).toBeInTheDocument();

    // Open Product Detail Page
    fireEvent.click(screen.getAllByRole("link", { name: /Nordic Tufted Accent Armchair/i })[0]);
    await waitFor(() =>
      expect(screen.getByText(/Product Specifications & Dimensions/i)).toBeInTheDocument()
    );

    // Switch gallery photo angle
    fireEvent.click(screen.getByRole("tab", { name: /Side Profile/i }));
    expect(screen.getByAltText(/Nordic Tufted Accent Armchair Side Profile/i)).toBeInTheDocument();

    // Generate 3D from listing photos, then navigate to AR Viewer
    fireEvent.click(screen.getByRole("button", { name: /Generate 3D from Listing Photos/i }));
    await waitFor(() =>
      expect(screen.getByRole("link", { name: /Launch AR Viewer/i })).toBeInTheDocument()
    );

    fireEvent.click(screen.getByRole("link", { name: /Launch AR Viewer/i }));
    await waitFor(() => expect(screen.getByTestId("ar-model-viewer")).toBeInTheDocument());
    expect(screen.getByTestId("ar-model-viewer")).toHaveAttribute(
      "src",
      "/api/models/mdl_shop_1.glb"
    );
    expect(screen.getByTestId("ar-model-viewer")).toHaveAttribute("ar-scale", "fixed");
  });
});
