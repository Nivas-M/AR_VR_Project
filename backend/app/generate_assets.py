"""Generate bundled multi-angle studio product PNGs for the ShopScale sample catalog."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from app.catalog import ASSETS_PRODUCTS_DIR


@dataclass(frozen=True)
class BoxPart:
    """Axis-aligned 3D shaded primitive in normalized [-1, 1]^3 product space."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float
    color: tuple[int, int, int]
    kind: str = "box"  # "box" or "cylinder_y"


def _product_parts() -> dict[str, list[BoxPart]]:
    """Define 3D part layouts for each catalog item so multi-angle PNGs stay aligned."""
    teal = (45, 108, 132)
    teal_dark = (34, 86, 108)
    cushion = (62, 128, 152)
    oak = (176, 132, 82)

    walnut = (112, 70, 42)
    walnut_dark = (88, 52, 30)

    brass = (188, 150, 74)
    ivory_shade = (232, 222, 200)

    oak_shelf = (196, 156, 104)
    charcoal_frame = (52, 56, 62)
    book_red = (172, 66, 58)
    book_blue = (54, 96, 140)
    book_green = (72, 124, 92)

    speaker_mesh = (54, 58, 66)
    champagne = (198, 178, 146)
    grill_accent = (82, 88, 98)

    return {
        "nordic-armchair": [
            # 4 legs
            BoxPart(-0.72, -0.95, 0.48, -0.52, -0.28, 0.68, oak, "cylinder_y"),
            BoxPart(0.52, -0.95, 0.48, 0.72, -0.28, 0.68, oak, "cylinder_y"),
            BoxPart(-0.72, -0.95, -0.68, -0.52, -0.28, -0.48, oak, "cylinder_y"),
            BoxPart(0.52, -0.95, -0.68, 0.72, -0.28, -0.48, oak, "cylinder_y"),
            # Base & seat cushion
            BoxPart(-0.82, -0.28, -0.76, 0.82, -0.04, 0.76, teal_dark),
            BoxPart(-0.68, -0.04, -0.62, 0.68, 0.22, 0.72, cushion),
            # Left & right armrests
            BoxPart(-0.88, -0.04, -0.72, -0.62, 0.48, 0.66, teal),
            BoxPart(0.62, -0.04, -0.72, 0.88, 0.48, 0.66, teal),
            # Backrest
            BoxPart(-0.86, 0.16, -0.82, 0.86, 0.94, -0.44, teal),
            BoxPart(-0.68, 0.24, -0.50, 0.68, 0.86, -0.32, cushion),
        ],
        "walnut-coffee-table": [
            # 4 splayed legs
            BoxPart(-0.82, -0.94, 0.56, -0.66, 0.64, 0.74, walnut_dark, "cylinder_y"),
            BoxPart(0.66, -0.94, 0.56, 0.82, 0.64, 0.74, walnut_dark, "cylinder_y"),
            BoxPart(-0.82, -0.94, -0.74, -0.66, 0.64, -0.56, walnut_dark, "cylinder_y"),
            BoxPart(0.66, -0.94, -0.74, 0.82, 0.64, -0.56, walnut_dark, "cylinder_y"),
            # Lower stretcher shelf
            BoxPart(-0.72, -0.36, -0.60, 0.72, -0.22, 0.60, walnut_dark),
            # Main tabletop
            BoxPart(-0.92, 0.64, -0.88, 0.92, 0.92, 0.88, walnut),
        ],
        "brass-floor-lamp": [
            # Heavy circular base
            BoxPart(-0.76, -0.95, -0.76, 0.76, -0.76, 0.76, brass, "cylinder_y"),
            # Slender stem
            BoxPart(-0.12, -0.76, -0.12, 0.12, 0.36, 0.12, brass, "cylinder_y"),
            # Top drum shade
            BoxPart(-0.84, 0.34, -0.84, 0.84, 0.94, 0.84, ivory_shade, "cylinder_y"),
            # Brass top finial ring
            BoxPart(-0.22, 0.92, -0.22, 0.22, 0.96, 0.22, brass, "cylinder_y"),
        ],
        "oak-bookshelf": [
            # Side uprights (left & right)
            BoxPart(-0.90, -0.95, -0.74, -0.74, 0.95, 0.74, charcoal_frame),
            BoxPart(0.74, -0.95, -0.74, 0.90, 0.95, 0.74, charcoal_frame),
            # 4 horizontal oak shelves
            BoxPart(-0.88, -0.82, -0.72, 0.88, -0.68, 0.72, oak_shelf),
            BoxPart(-0.88, -0.24, -0.72, 0.88, -0.10, 0.72, oak_shelf),
            BoxPart(-0.88, 0.34, -0.72, 0.88, 0.48, 0.72, oak_shelf),
            BoxPart(-0.88, 0.82, -0.72, 0.88, 0.95, 0.72, oak_shelf),
            # Decorative books on middle shelves
            BoxPart(-0.66, -0.10, -0.45, -0.44, 0.32, 0.45, book_red),
            BoxPart(-0.42, -0.10, -0.45, -0.20, 0.28, 0.45, book_blue),
            BoxPart(0.24, 0.48, -0.45, 0.56, 0.80, 0.45, book_green),
        ],
        "studio-bluetooth-speaker": [
            # Silicone foot base
            BoxPart(-0.78, -0.92, -0.68, 0.78, -0.74, 0.68, charcoal_frame),
            # Acoustic fabric body
            BoxPart(-0.88, -0.74, -0.78, 0.88, 0.74, 0.78, speaker_mesh),
            # Front/back acoustic grille detail
            BoxPart(-0.74, -0.58, -0.82, 0.74, 0.58, 0.82, grill_accent),
            # Anodized champagne top control plate
            BoxPart(-0.82, 0.74, -0.72, 0.82, 0.92, 0.72, champagne),
        ],
    }


def _project_part(part: BoxPart, angle: str) -> tuple[float, float, float, float, float]:
    """Return (u0, v0, u1, v1, depth_key) in normalized [-1, 1] image coords."""
    if angle == "front":
        return part.min_x, part.min_y, part.max_x, part.max_y, part.max_z
    if angle == "back":
        return -part.max_x, part.min_y, -part.min_x, part.max_y, -part.min_z
    if angle == "side":
        return -part.max_z, part.min_y, -part.min_z, part.max_y, part.max_x
    if angle == "top":
        return part.min_x, -part.max_z, part.max_x, -part.min_z, part.max_y
    raise ValueError(f"Unsupported angle {angle!r}")


def render_product_view(parts: list[BoxPart], angle: str, size: int = 512) -> Image.Image:
    """Render an orthographic studio product image on a soft light backdrop."""
    # Clean studio gradient background (#f5f6f8 -> #e8ebf0)
    y_grad = np.linspace(246, 232, size, dtype=np.uint8)[:, None]
    bg = np.zeros((size, size, 3), dtype=np.uint8)
    bg[:, :, 0] = y_grad
    bg[:, :, 1] = np.clip(y_grad + 1, 0, 255)
    bg[:, :, 2] = np.clip(y_grad + 4, 0, 255)
    canvas = Image.fromarray(bg, mode="RGB")

    # Subtle floor shadow for grounded side/front/back views
    shadow_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    pad = int(size * 0.14)
    span = size - 2 * pad

    def to_px(u: float, v: float) -> tuple[int, int]:
        px = int(round(pad + ((u + 1.0) * 0.5) * span))
        py = int(round(pad + ((1.0 - v) * 0.5) * span))
        return px, py

    if angle != "top":
        sx0, sy0 = to_px(-0.85, -0.88)
        sx1, sy1 = to_px(0.85, -1.02)
        shadow_draw.ellipse([sx0, sy0, sx1, sy1], fill=(120, 128, 140, 65))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=10))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow_layer).convert("RGB")

    # Painter's algorithm sorted back-to-front by view depth
    projected = sorted(
        [(part, *_project_part(part, angle)) for part in parts],
        key=lambda item: item[5],
    )

    draw = ImageDraw.Draw(canvas)
    for part, u0, v0, u1, v1, depth in projected:
        x0, y1 = to_px(u0, v0)
        x1, y0 = to_px(u1, v1)
        x_lo, x_hi = min(x0, x1), max(x0, x1)
        y_lo, y_hi = min(y0, y1), max(y0, y1)

        # Gentle depth shading so overlapping parts read clearly in 2D photos
        shade = 0.88 + 0.12 * max(0.0, min(1.0, (depth + 1.0) * 0.5))
        r = int(min(255, part.color[0] * shade))
        g = int(min(255, part.color[1] * shade))
        b = int(min(255, part.color[2] * shade))
        outline = (max(0, r - 24), max(0, g - 24), max(0, b - 24))

        if part.kind == "cylinder_y" and angle == "top":
            draw.ellipse([x_lo, y_lo, x_hi, y_hi], fill=(r, g, b), outline=outline, width=2)
        else:
            radius = max(2, min((x_hi - x_lo), (y_hi - y_lo)) // 8)
            draw.rounded_rectangle(
                [x_lo, y_lo, x_hi, y_hi],
                radius=radius,
                fill=(r, g, b),
                outline=outline,
                width=2,
            )

    return canvas


def generate_all_assets(output_root: Path = ASSETS_PRODUCTS_DIR) -> list[Path]:
    """Generate multi-angle PNGs for every bundled catalog product."""
    written: list[Path] = []
    for product_id, parts in _product_parts().items():
        product_dir = output_root / product_id
        product_dir.mkdir(parents=True, exist_ok=True)
        for angle in ("front", "side", "back", "top"):
            out_path = product_dir / f"{angle}.png"
            img = render_product_view(parts, angle=angle, size=512)
            img.save(out_path, format="PNG")
            written.append(out_path)
    return written


if __name__ == "__main__":
    files = generate_all_assets()
    print(f"Generated {len(files)} product asset images.")
