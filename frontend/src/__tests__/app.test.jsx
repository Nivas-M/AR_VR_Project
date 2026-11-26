import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../App";
import { formatDimensions, getHealth, listProducts, startReconstruction } from "../api/client";

describe("Frontend routing and API client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: async () => ({ status: "ok", default_engine: "local_cpu", products: [] }),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it("renders navigation links and routes to Storefront, Studio, and AR Viewer", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    expect(screen.getByText(/ShopScale Demo Storefront/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /^Photo-to-3D Studio$/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/API Ready \(local_cpu\)/i)).toBeInTheDocument());

    cleanup();
    render(
      <MemoryRouter initialEntries={["/studio"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    expect(screen.getByRole("heading", { name: /Photo-to-3D True-Scale Studio/i })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/API Ready \(local_cpu\)/i)).toBeInTheDocument());

    cleanup();
    render(
      <MemoryRouter initialEntries={["/ar/demo-model"]}>
        <AppRoutes />
      </MemoryRouter>
    );
    expect(screen.getByText(/True-Scale AR Placement Viewer: demo-model/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/API Ready \(local_cpu\)/i)).toBeInTheDocument());
  });

  it("calls backend API endpoints and formats metric dimensions", async () => {
    await getHealth();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/health", {});

    await listProducts();
    expect(globalThis.fetch).toHaveBeenCalledWith("/api/products", {});

    await startReconstruction({
      productId: "nordic-armchair",
      width: 78,
      height: 84,
      depth: 74,
      unit: "cm",
    });
    const postCall = globalThis.fetch.mock.calls.at(-1);
    expect(postCall[0]).toBe("/api/reconstruct");
    expect(postCall[1].method).toBe("POST");
    expect(postCall[1].body).toBeInstanceOf(FormData);

    const formatted = formatDimensions({ width: 0.78, height: 0.84, depth: 0.74 });
    expect(formatted.cmLabel).toBe("78.0 × 84.0 × 74.0 cm");
    expect(formatted.mLabel).toBe("0.780 × 0.840 × 0.740 m");
  });
});
