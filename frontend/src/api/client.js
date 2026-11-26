/**
 * Shared REST API client and metric unit helpers for TrueScale AR backend.
 */

export const API_BASE = "";

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const message =
      (isJson && payload && (payload.detail || payload.error || payload.message)) ||
      (typeof payload === "string" && payload) ||
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

export function getHealth() {
  return requestJson("/api/health");
}

export function listProducts() {
  return requestJson("/api/products");
}

export function getProduct(productId) {
  return requestJson(`/api/products/${encodeURIComponent(productId)}`);
}

export function getJob(jobId) {
  return requestJson(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function getModelMeta(modelId) {
  return requestJson(`/api/models/${encodeURIComponent(modelId)}/meta`);
}

export function getModelGlbUrl(modelId) {
  return `${API_BASE}/api/models/${encodeURIComponent(modelId)}.glb`;
}

export function startReconstruction({
  files = [],
  angles = [],
  productId = null,
  width,
  height,
  depth,
  unit = "cm",
  scaleMode = "exact_fit",
  engine = "local_cpu",
  title = "",
}) {
  const form = new FormData();
  if (files && files.length > 0) {
    for (const file of files) {
      form.append("files", file);
    }
    if (angles && angles.length > 0) {
      form.append("angles", JSON.stringify(angles));
    }
  }
  if (productId) {
    form.append("product_id", productId);
  }
  if (width !== undefined && width !== null && width !== "") {
    form.append("width", String(width));
  }
  if (height !== undefined && height !== null && height !== "") {
    form.append("height", String(height));
  }
  if (depth !== undefined && depth !== null && depth !== "") {
    form.append("depth", String(depth));
  }
  form.append("unit", unit);
  form.append("scale_mode", scaleMode);
  form.append("engine", engine);
  if (title) {
    form.append("title", title);
  }

  return requestJson("/api/reconstruct", {
    method: "POST",
    body: form,
  });
}

export async function pollJob(jobId, { onProgress, intervalMs = 500, timeoutMs = 120000 } = {}) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const job = await getJob(jobId);
    if (onProgress) {
      onProgress(job);
    }
    if (job.status === "done") {
      return job;
    }
    if (job.status === "failed") {
      throw new Error(job.error || "Reconstruction job failed");
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("Reconstruction timed out while waiting for backend job");
}

export function metersToCm(meters) {
  return Number(meters || 0) * 100;
}

export function metersToIn(meters) {
  return Number(meters || 0) / 0.0254;
}

export function formatDimensions(bboxMeters) {
  if (!bboxMeters) return null;
  const wCm = metersToCm(bboxMeters.width).toFixed(1);
  const hCm = metersToCm(bboxMeters.height).toFixed(1);
  const dCm = metersToCm(bboxMeters.depth).toFixed(1);

  const wIn = metersToIn(bboxMeters.width).toFixed(1);
  const hIn = metersToIn(bboxMeters.height).toFixed(1);
  const dIn = metersToIn(bboxMeters.depth).toFixed(1);

  return {
    cmLabel: `${wCm} × ${hCm} × ${dCm} cm`,
    inLabel: `${wIn} × ${hIn} × ${dIn} in`,
    mLabel: `${Number(bboxMeters.width).toFixed(3)} × ${Number(bboxMeters.height).toFixed(3)} × ${Number(bboxMeters.depth).toFixed(3)} m`,
  };
}
