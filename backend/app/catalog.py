"""Bundled dummy e-commerce sample catalog ("ShopScale") with real metric dimensions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

ASSETS_PRODUCTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "products"


@dataclass(frozen=True, slots=True)
class ProductImage:
    """Single multi-angle product photo metadata."""

    angle: str
    filename: str
    label: str


@dataclass(frozen=True, slots=True)
class CatalogProduct:
    """Mock e-commerce product entry with real-world physical dimensions."""

    id: str
    title: str
    brand: str
    category: str
    price_usd: float
    rating: float
    review_count: int
    description: str
    material: str
    color: str
    width_cm: float
    height_cm: float
    depth_cm: float
    weight_kg: float
    images: tuple[ProductImage, ...]
    highlights: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize product metadata including API image URLs and inch equivalents."""
        data = asdict(self)
        cm_to_in = 1.0 / 2.54
        data["dimensions_cm"] = {
            "width": self.width_cm,
            "height": self.height_cm,
            "depth": self.depth_cm,
        }
        data["dimensions_in"] = {
            "width": round(self.width_cm * cm_to_in, 1),
            "height": round(self.height_cm * cm_to_in, 1),
            "depth": round(self.depth_cm * cm_to_in, 1),
        }
        data["images"] = [
            {
                "angle": img.angle,
                "filename": img.filename,
                "label": img.label,
                "url": f"/api/products/{self.id}/images/{img.filename}",
            }
            for img in self.images
        ]
        return data


CATALOG_PRODUCTS: tuple[CatalogProduct, ...] = (
    CatalogProduct(
        id="nordic-armchair",
        title="Nordic Tufted Accent Armchair",
        brand="FjordHome",
        category="Living Room",
        price_usd=289.00,
        rating=4.7,
        review_count=1284,
        description=(
            "Mid-century reading armchair upholstered in textured slate-teal weave "
            "with solid kiln-dried ash wood legs and supportive high-density cushion."
        ),
        material="Woven Polyester Linen & Solid Ash Wood",
        color="Slate Teal / Natural Oak",
        width_cm=78.0,
        height_cm=84.0,
        depth_cm=74.0,
        weight_kg=16.5,
        images=(
            ProductImage("front", "front.png", "Front View"),
            ProductImage("side", "side.png", "Side Profile"),
            ProductImage("back", "back.png", "Back View"),
            ProductImage("top", "top.png", "Top View"),
        ),
        highlights=(
            "Ergonomic angled backrest for living rooms and reading corners",
            "True-scale dimensions: 78 × 84 × 74 cm (30.7 × 33.1 × 29.1 in)",
            "Non-slip felt floor glides pre-installed",
        ),
    ),
    CatalogProduct(
        id="walnut-coffee-table",
        title="Mid-Century Walnut Coffee Table",
        brand="TimberCraft",
        category="Living Room",
        price_usd=219.00,
        rating=4.8,
        review_count=842,
        description=(
            "Low-profile rectangular living room centerpiece with beveled walnut-veneer top "
            "and splayed solid hardwood legs."
        ),
        material="Walnut Veneer & Solid Beech Legs",
        color="Warm American Walnut",
        width_cm=110.0,
        height_cm=45.0,
        depth_cm=60.0,
        weight_kg=14.2,
        images=(
            ProductImage("front", "front.png", "Front View"),
            ProductImage("side", "side.png", "Side Profile"),
            ProductImage("back", "back.png", "Back View"),
            ProductImage("top", "top.png", "Top View"),
        ),
        highlights=(
            "Spacious 110 × 60 cm tabletop ideal for 2–3 seater sofas",
            "Comfortable 45 cm height aligns with standard couch seat cushions",
            "Matte water-resistant polyurethane finish",
        ),
    ),
    CatalogProduct(
        id="brass-floor-lamp",
        title="Minimalist Column Brass Floor Lamp",
        brand="LumenAtelier",
        category="Lighting",
        price_usd=149.00,
        rating=4.6,
        review_count=615,
        description=(
            "Tall standing ambient floor lamp featuring a weighted brushed-brass base, "
            "slender stem, and warm linen drum shade."
        ),
        material="Brushed Brass & Natural Linen Shade",
        color="Antique Brass / Warm Ivory",
        width_cm=42.0,
        height_cm=165.0,
        depth_cm=42.0,
        weight_kg=6.8,
        images=(
            ProductImage("front", "front.png", "Front View"),
            ProductImage("side", "side.png", "Side Profile"),
            ProductImage("back", "back.png", "Back View"),
            ProductImage("top", "top.png", "Top View"),
        ),
        highlights=(
            "Tall 165 cm silhouette fits cleanly beside armchairs or sofas",
            "Compact 42 × 42 cm weighted base footprint",
            "2700K warm LED bulb compatible (E26 socket)",
        ),
    ),
    CatalogProduct(
        id="oak-bookshelf",
        title="4-Tier Open Oak Storage Bookshelf",
        brand="FjordHome",
        category="Storage",
        price_usd=199.00,
        rating=4.5,
        review_count=493,
        description=(
            "Clean-lined 4-tier open bookcase crafted for apartments and home offices, "
            "offering vertical storage with a slim 36 cm wall depth."
        ),
        material="White Oak Laminate & Powder-Coated Steel Frame",
        color="Natural Oak / Matte Charcoal",
        width_cm=80.0,
        height_cm=155.0,
        depth_cm=36.0,
        weight_kg=21.0,
        images=(
            ProductImage("front", "front.png", "Front View"),
            ProductImage("side", "side.png", "Side Profile"),
            ProductImage("back", "back.png", "Back View"),
            ProductImage("top", "top.png", "Top View"),
        ),
        highlights=(
            "Space-saving 36 cm depth fits narrow hallways and alcoves",
            "Four reinforced shelves supporting up to 22 kg each",
            "Includes anti-tip wall anchor hardware",
        ),
    ),
    CatalogProduct(
        id="studio-bluetooth-speaker",
        title="Acoustic Fabric Tabletop Bluetooth Speaker",
        brand="SoundForm",
        category="Audio",
        price_usd=129.00,
        rating=4.9,
        review_count=2140,
        description=(
            "Compact countertop wireless speaker wrapped in acoustic heather-charcoal mesh "
            "with anodized aluminum top controls and dual passive radiators."
        ),
        material="Acoustic Textile, Brushed Aluminum & Silicone Base",
        color="Charcoal Mesh / Champagne Trim",
        width_cm=28.0,
        height_cm=18.0,
        depth_cm=16.0,
        weight_kg=2.1,
        images=(
            ProductImage("front", "front.png", "Front View"),
            ProductImage("side", "side.png", "Side Profile"),
            ProductImage("back", "back.png", "Back View"),
            ProductImage("top", "top.png", "Top View"),
        ),
        highlights=(
            "Compact desk/shelf footprint: 28 × 18 × 16 cm",
            "24-hour battery life with USB-C fast charging",
            "Room-filling stereo acoustic dispersion",
        ),
    ),
)

_PRODUCT_BY_ID: dict[str, CatalogProduct] = {p.id: p for p in CATALOG_PRODUCTS}


def list_products() -> list[dict[str, object]]:
    """Return all bundled catalog products as serialized dicts."""
    return [product.to_dict() for product in CATALOG_PRODUCTS]


def get_product(product_id: str) -> CatalogProduct | None:
    """Look up a bundled catalog product by ID."""
    return _PRODUCT_BY_ID.get(product_id)


def get_product_image_path(product_id: str, filename: str) -> Path | None:
    """Resolve a product photo path safely inside backend/assets/products/."""
    product = get_product(product_id)
    if product is None:
        return None
    valid_names = {img.filename for img in product.images}
    if filename not in valid_names:
        return None
    path = ASSETS_PRODUCTS_DIR / product_id / filename
    return path if path.is_file() else None
