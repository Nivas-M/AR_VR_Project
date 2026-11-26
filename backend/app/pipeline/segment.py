"""Memory-safe photo preprocessing and foreground segmentation for TrueScale AR."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image, ImageOps

SegmentEngine = Literal["auto", "studio", "rembg"]


@dataclass(slots=True)
class SegmentedImage:
    """Segmented, tightly cropped, square-padded foreground RGBA result."""

    rgba_image: Image.Image
    alpha_mask: np.ndarray
    original_size: tuple[int, int]
    processed_size: tuple[int, int]
    foreground_bbox: tuple[int, int, int, int]
    foreground_ratio: float
    method_used: str

    def to_png_bytes(self) -> bytes:
        """Encode segmented RGBA image as PNG bytes."""
        buf = io.BytesIO()
        self.rgba_image.save(buf, format="PNG")
        return buf.getvalue()


def _load_and_resize(
    source: str | Path | bytes | Image.Image,
    max_image_size_px: int = 1024,
) -> tuple[Image.Image, tuple[int, int]]:
    """Load an image safely, apply EXIF orientation, and cap max dimension."""
    if isinstance(source, Image.Image):
        img = source.copy()
    elif isinstance(source, (str, Path)):
        with Image.open(source) as opened:
            img = ImageOps.exif_transpose(opened).copy()
    elif isinstance(source, (bytes, bytearray)):
        with Image.open(io.BytesIO(source)) as opened:
            img = ImageOps.exif_transpose(opened).copy()
    else:
        raise TypeError(f"Unsupported image source type: {type(source)!r}")

    if isinstance(source, Image.Image):
        img = ImageOps.exif_transpose(img)

    original_size = img.size
    rgba = img.convert("RGBA")

    width, height = rgba.size
    longest = max(width, height)
    if max_image_size_px > 0 and longest > max_image_size_px:
        scale = max_image_size_px / float(longest)
        new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
        rgba = rgba.resize(new_size, Image.Resampling.LANCZOS)

    return rgba, original_size


def _has_meaningful_alpha(alpha: np.ndarray) -> bool:
    """Detect whether an image already carries a real foreground/background alpha matte."""
    total = alpha.size
    if total == 0:
        return False
    transparent_ratio = float(np.count_nonzero(alpha < 24)) / total
    opaque_ratio = float(np.count_nonzero(alpha > 230)) / total
    return transparent_ratio >= 0.02 and opaque_ratio >= 0.02


def _keep_significant_components(binary_mask: np.ndarray, min_rel_area: float = 0.05) -> np.ndarray:
    """Remove small disconnected specks while preserving significant object parts."""
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary_mask, connectivity=8)
    if num_labels <= 1:
        return binary_mask

    areas = stats[1:, cv2.CC_STAT_AREA]
    max_area = int(areas.max()) if len(areas) > 0 else 0
    if max_area == 0:
        return binary_mask

    keep = np.zeros_like(binary_mask)
    threshold_area = max(16, int(max_area * min_rel_area))
    for label_idx in range(1, num_labels):
        if int(stats[label_idx, cv2.CC_STAT_AREA]) >= threshold_area:
            keep[labels == label_idx] = 255
    return keep


def _extract_studio_grabcut_mask(rgb: np.ndarray) -> np.ndarray:
    """Segment foreground from uniform, gradient, or studio backgrounds on CPU."""
    height, width = rgb.shape[:2]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    margin = max(4, min(height, width) // 25)
    border_pixels = np.concatenate(
        [
            lab[:margin, :, :].reshape(-1, 3),
            lab[-margin:, :, :].reshape(-1, 3),
            lab[:, :margin, :].reshape(-1, 3),
            lab[:, -margin:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg_median = np.median(border_pixels, axis=0)
    mad = np.median(np.abs(border_pixels - bg_median), axis=0)
    bg_spread = float(np.linalg.norm(mad))
    bg_thresh = float(np.clip(max(16.0, 3.0 * bg_spread), 16.0, 42.0))

    dist = np.linalg.norm(lab - bg_median, axis=2)
    bg_candidates = (dist < bg_thresh).astype(np.uint8)

    # Only treat border-connected pixels as exterior background so interior
    # highlights/patches inside the product are preserved.
    num_labels, labels = cv2.connectedComponents(bg_candidates, connectivity=4)
    border_labels = set(np.unique(labels[0, :]).tolist())
    border_labels.update(np.unique(labels[-1, :]).tolist())
    border_labels.update(np.unique(labels[:, 0]).tolist())
    border_labels.update(np.unique(labels[:, -1]).tolist())
    border_labels.discard(0)

    exterior_bg = np.isin(labels, list(border_labels)) if border_labels else np.zeros((height, width), dtype=bool)
    rough_fg = (~exterior_bg).astype(np.uint8) * 255
    rough_fg = _keep_significant_components(rough_fg)

    fg_ratio = float(np.count_nonzero(rough_fg)) / float(height * width)
    final_mask = rough_fg

    if 0.02 <= fg_ratio <= 0.92 and min(height, width) >= 32:
        gc_mask = np.full((height, width), cv2.GC_PR_BGD, dtype=np.uint8)
        gc_mask[exterior_bg & (dist < bg_thresh * 0.75)] = cv2.GC_BGD
        gc_mask[0, :] = cv2.GC_BGD
        gc_mask[-1, :] = cv2.GC_BGD
        gc_mask[:, 0] = cv2.GC_BGD
        gc_mask[:, -1] = cv2.GC_BGD

        fg_bool = rough_fg > 0
        gc_mask[fg_bool] = cv2.GC_PR_FGD
        erode_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        sure_fg = cv2.erode(rough_fg, erode_kernel, iterations=2) > 0
        if np.any(sure_fg):
            gc_mask[sure_fg] = cv2.GC_FGD

        if np.any(gc_mask == cv2.GC_BGD) and np.any((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD)):
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            bgd_model = np.zeros((1, 65), dtype=np.float64)
            fgd_model = np.zeros((1, 65), dtype=np.float64)
            try:
                cv2.grabCut(bgr, gc_mask, None, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_MASK)
                gc_fg = np.where((gc_mask == cv2.GC_FGD) | (gc_mask == cv2.GC_PR_FGD), 255, 0).astype(
                    np.uint8
                )
                gc_ratio = float(np.count_nonzero(gc_fg)) / float(height * width)
                if gc_ratio >= 0.015:
                    final_mask = gc_fg
            except cv2.error:
                final_mask = rough_fg

    open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = cv2.morphologyEx(final_mask, cv2.MORPH_OPEN, open_kernel)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, close_kernel)
    cleaned = _keep_significant_components(cleaned)

    # Light feathering solely near silhouette boundaries for clean alpha transitions.
    soft = cv2.GaussianBlur(cleaned, (3, 3), sigmaX=0.75)
    soft[cleaned == 255] = np.maximum(soft[cleaned == 255], 235)
    soft[cleaned == 0] = np.minimum(soft[cleaned == 0], 20)
    soft[soft < 16] = 0
    return soft


def _extract_rembg_mask(rgba_img: Image.Image) -> np.ndarray | None:
    """Optionally extract foreground alpha using lightweight rembg u2netp if installed."""
    try:
        from rembg import new_session, remove  # type: ignore[import-not-found]
    except ImportError:
        return None

    session = new_session("u2netp")
    cutout = remove(rgba_img, session=session)
    return np.asarray(cutout.convert("RGBA"))[:, :, 3]


def _crop_and_square_pad(
    rgb: np.ndarray,
    alpha: np.ndarray,
    output_size: int = 512,
    pad_ratio: float = 0.08,
) -> tuple[Image.Image, np.ndarray, tuple[int, int, int, int]]:
    """Tightly crop foreground, center it on a square RGBA canvas, and clean RGB bleed."""
    ys, xs = np.where(alpha > 16)
    if len(xs) == 0 or len(ys) == 0:
        raise ValueError("No foreground object detected during segmentation")

    x_min, x_max = int(xs.min()), int(xs.max()) + 1
    y_min, y_max = int(ys.min()), int(ys.max()) + 1

    crop_rgb = rgb[y_min:y_max, x_min:x_max].copy()
    crop_alpha = alpha[y_min:y_max, x_min:x_max].copy()
    crop_rgb[crop_alpha == 0] = 0

    crop_rgba = np.dstack([crop_rgb, crop_alpha])
    crop_pil = Image.fromarray(crop_rgba, mode="RGBA")

    crop_w, crop_h = crop_pil.size
    inner_max = max(1, int(round(output_size * (1.0 - 2.0 * pad_ratio))))
    scale = inner_max / float(max(crop_w, crop_h))
    resized_w = max(1, int(round(crop_w * scale)))
    resized_h = max(1, int(round(crop_h * scale)))
    resized = crop_pil.resize((resized_w, resized_h), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", (output_size, output_size), (0, 0, 0, 0))
    offset_x = (output_size - resized_w) // 2
    offset_y = (output_size - resized_h) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)

    canvas_alpha = np.asarray(canvas)[:, :, 3].copy()
    return canvas, canvas_alpha, (x_min, y_min, x_max, y_max)


def segment_image(
    source: str | Path | bytes | Image.Image,
    max_image_size_px: int = 1024,
    output_size: int = 512,
    pad_ratio: float = 0.08,
    engine: SegmentEngine = "auto",
) -> SegmentedImage:
    """Preprocess an input photo and return a centered square foreground RGBA cutout."""
    if output_size < 32:
        raise ValueError(f"output_size must be >= 32, got {output_size}")
    if not (0.0 <= pad_ratio < 0.45):
        raise ValueError(f"pad_ratio must be in [0.0, 0.45), got {pad_ratio}")

    rgba_img, original_size = _load_and_resize(source, max_image_size_px=max_image_size_px)
    rgba_arr = np.asarray(rgba_img)
    rgb = rgba_arr[:, :, :3]
    alpha_in = rgba_arr[:, :, 3]

    if _has_meaningful_alpha(alpha_in):
        alpha = alpha_in.copy()
        method_used = "alpha_passthrough"
    elif engine == "rembg":
        rembg_alpha = _extract_rembg_mask(rgba_img)
        if rembg_alpha is not None:
            alpha = rembg_alpha
            method_used = "rembg_u2netp"
        else:
            alpha = _extract_studio_grabcut_mask(rgb)
            method_used = "studio_grabcut_fallback"
    else:
        alpha = _extract_studio_grabcut_mask(rgb)
        method_used = "studio_grabcut"

    canvas, canvas_alpha, bbox = _crop_and_square_pad(
        rgb=rgb,
        alpha=alpha,
        output_size=output_size,
        pad_ratio=pad_ratio,
    )
    fg_ratio = float(np.count_nonzero(canvas_alpha > 16)) / float(canvas_alpha.size)

    return SegmentedImage(
        rgba_image=canvas,
        alpha_mask=canvas_alpha,
        original_size=original_size,
        processed_size=rgba_img.size,
        foreground_bbox=bbox,
        foreground_ratio=round(fg_ratio, 4),
        method_used=method_used,
    )
