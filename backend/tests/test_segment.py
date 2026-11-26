"""Unit tests for memory-safe photo segmentation and foreground cropping."""

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.pipeline.segment import segment_image  # noqa: E402


def _make_synthetic_chair_image(
    bg_color: tuple[int, int, int],
    size: tuple[int, int] = (480, 360),
    offset: tuple[int, int] = (0, 0),
) -> Image.Image:
    """Create a synthetic product photo (chair-like silhouette) on a studio background."""
    img = Image.new("RGB", size, bg_color)
    draw = ImageDraw.Draw(img)
    cx = size[0] // 2 + offset[0]
    cy = size[1] // 2 + offset[1]

    # Seat + backrest + two legs in warm wood/teal tones
    draw.rectangle([cx - 55, cy - 85, cx + 55, cy - 15], fill=(38, 92, 118))
    draw.rectangle([cx - 65, cy - 15, cx + 65, cy + 25], fill=(44, 108, 136))
    draw.rectangle([cx - 55, cy + 25, cx - 35, cy + 95], fill=(120, 82, 48))
    draw.rectangle([cx + 35, cy + 25, cx + 55, cy + 95], fill=(120, 82, 48))
    # Interior light cushion highlight (must NOT be removed as background)
    draw.rectangle([cx - 35, cy - 65, cx + 35, cy - 25], fill=(246, 245, 240))
    return img


def test_segment_white_background_preserves_interior_highlights_and_centers() -> None:
    """White studio background should be removed while keeping white interior cushion."""
    img = _make_synthetic_chair_image(bg_color=(250, 250, 250), offset=(60, -25))
    result = segment_image(img, output_size=256)

    assert result.rgba_image.size == (256, 256)
    assert result.rgba_image.mode == "RGBA"
    assert result.method_used == "studio_grabcut"

    arr = np.asarray(result.rgba_image)
    alpha = arr[:, :, 3]
    # Corners must be transparent
    assert alpha[0, 0] == 0
    assert alpha[0, -1] == 0
    assert alpha[-1, 0] == 0
    assert alpha[-1, -1] == 0

    # Center cushion area must remain opaque despite light color
    assert alpha[100:125, 118:138].mean() > 200
    assert 0.15 < result.foreground_ratio < 0.80

    # Foreground should be centered in the 256x256 output canvas
    ys, xs = np.where(alpha > 16)
    center_x = 0.5 * (xs.min() + xs.max())
    center_y = 0.5 * (ys.min() + ys.max())
    assert center_x == pytest.approx(128.0, abs=8.0)
    assert center_y == pytest.approx(128.0, abs=8.0)


def test_segment_colored_studio_background() -> None:
    """Colored/gradient studio backgrounds should segment cleanly."""
    width, height = 400, 400
    y_grad = np.linspace(195, 225, height, dtype=np.uint8)[:, None]
    bg = np.zeros((height, width, 3), dtype=np.uint8)
    bg[:, :, 0] = y_grad
    bg[:, :, 1] = 210
    bg[:, :, 2] = 195
    img = Image.fromarray(bg, mode="RGB")

    draw = ImageDraw.Draw(img)
    draw.ellipse([130, 90, 270, 310], fill=(185, 58, 42))

    result = segment_image(img, output_size=256)
    arr = np.asarray(result.rgba_image)
    alpha = arr[:, :, 3]

    assert alpha[5, 5] == 0
    assert alpha[-5, -5] == 0
    assert alpha[128, 128] > 220
    assert result.foreground_bbox[2] - result.foreground_bbox[0] >= 120


def test_segment_caps_large_images_and_supports_alpha_passthrough() -> None:
    """Large images should downscale safely and existing RGBA cutouts should pass through."""
    large = Image.new("RGBA", (2400, 1600), (0, 0, 0, 0))
    draw = ImageDraw.Draw(large)
    draw.rectangle([700, 300, 1700, 1300], fill=(70, 130, 180, 255))

    result = segment_image(large, max_image_size_px=1024, output_size=256)
    assert result.original_size == (2400, 1600)
    assert max(result.processed_size) == 1024
    assert result.method_used == "alpha_passthrough"
    assert result.rgba_image.size == (256, 256)
    assert result.alpha_mask[128, 128] > 230
    assert result.alpha_mask[0, 0] == 0
