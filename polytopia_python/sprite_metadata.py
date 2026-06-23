"""Unity sprite rect/pivot metadata for correct isometric placement."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image


@dataclass(frozen=True)
class SpriteMeta:
    logical_size: tuple[int, int]
    pivot_pil: tuple[float, float]
    paste_at: tuple[int, int]
    pixels_per_unit: float


# ground_imperius m_PixelsToUnits — reference for world ↔ pixel mapping.
GROUND_PIXELS_PER_UNIT = 265.08197021484375
FOREST_PIXELS_PER_UNIT = 279.1562194824219
MOUNTAIN_PIXELS_PER_UNIT = 239.01657104492188

_FOREST_TEMPLATE = SpriteMeta((256, 198), (128.0, 99.0), (0, 0), FOREST_PIXELS_PER_UNIT)
_MOUNTAIN_TEMPLATE = SpriteMeta((232, 256), (116.0, 255.0), (0, 0), MOUNTAIN_PIXELS_PER_UNIT)
_RESOURCE_TEMPLATE = SpriteMeta((128, 128), (64.0, 127.0), (0, 0), GROUND_PIXELS_PER_UNIT)
# Short mountains anchor at this foot row; taller art falls back to canvas-bottom pivot.
_MOUNTAIN_STANDARD_FOOT_Y = 194
_MOUNTAIN_MIN_PASTE_Y = -5

_DEFAULT_SPRITE_DIR = Path(__file__).resolve().parent.parent / "sprites"


def _unity_pivot_to_pil(pivot_x: float, pivot_y: float, width: float, height: float) -> tuple[float, float]:
    """Unity pivot (0,0 = bottom-left) → PIL top-left origin."""
    px = pivot_x * width
    py = (1.0 - pivot_y) * height
    if pivot_y == 0.0:
        py = height - 1.0
    return px, py


def _alpha(img: Image.Image) -> Image.Image:
    return img.getchannel("A")


def _opaque_bounds(img: Image.Image, threshold: int = 8) -> Optional[tuple[int, int, int, int]]:
    """Return (x0, y0, x1, y1) of opaque pixels, or None."""
    alpha = _alpha(img)
    w, h = img.size
    y0, y1 = h, -1
    x0, x1 = w, -1
    for y in range(h):
        row_opaque = False
        for x in range(w):
            if alpha.getpixel((x, y)) > threshold:
                row_opaque = True
                x0 = min(x0, x)
                x1 = max(x1, x)
        if row_opaque:
            y0 = min(y0, y)
            y1 = max(y1, y)
    if y1 < 0:
        return None
    return x0, y0, x1, y1


def _bottom_center(img: Image.Image) -> tuple[int, int]:
    """Bottom-row center of opaque pixels — tile foot on isometric ground."""
    alpha = _alpha(img)
    w, h = img.size
    bottom = -1
    for y in range(h - 1, -1, -1):
        for x in range(w):
            if alpha.getpixel((x, y)) > 8:
                bottom = y
                break
        if bottom >= 0:
            break
    if bottom < 0:
        return w // 2, h - 1
    cols = [x for x in range(w) if alpha.getpixel((x, bottom)) > 8]
    if not cols:
        return w // 2, bottom
    return (cols[0] + cols[-1]) // 2, bottom


def _bbox_center(img: Image.Image) -> tuple[int, int]:
    bounds = _opaque_bounds(img)
    if bounds is None:
        w, h = img.size
        return w // 2, h // 2
    x0, y0, x1, y1 = bounds
    return (x0 + x1) // 2, (y0 + y1) // 2


def _infer_forest_meta(img: Image.Image) -> SpriteMeta:
    """Forest sprites share a 256×198 canvas with center pivot (Tile prefab forestRenderer)."""
    cx, cy = _bbox_center(img)
    pvx, pvy = _FOREST_TEMPLATE.pivot_pil
    paste_x = int(round(pvx - cx))
    paste_y = int(round(pvy - cy))
    return SpriteMeta(_FOREST_TEMPLATE.logical_size, _FOREST_TEMPLATE.pivot_pil, (paste_x, paste_y), FOREST_PIXELS_PER_UNIT)


def _infer_mountain_meta(img: Image.Image) -> SpriteMeta:
    """Mountain sprites share a 232×256 canvas with bottom-center pivot (mountainRenderer)."""
    bc_x, bc_y = _bottom_center(img)
    pvx, pvy = _MOUNTAIN_TEMPLATE.pivot_pil
    paste_y = int(round(_MOUNTAIN_STANDARD_FOOT_Y - bc_y))
    if paste_y < _MOUNTAIN_MIN_PASTE_Y:
        paste_y = int(round(pvy - bc_y))
    paste_x = int(round(pvx - bc_x))
    return SpriteMeta(_MOUNTAIN_TEMPLATE.logical_size, _MOUNTAIN_TEMPLATE.pivot_pil, (paste_x, paste_y), MOUNTAIN_PIXELS_PER_UNIT)


def _infer_resource_meta(img: Image.Image, stem: str) -> SpriteMeta:
    """ResourceGFX sprites use a fixed bottom-center slot on the tile (Tile.RenderResource)."""
    w, h = img.size
    bc_x, bc_y = _bottom_center(img)

    # crop is authored at full logical size (256×159 in v116).
    if stem in ("ResourceGFX_crop", "ResourceGFX_crop_Outline"):
        pvx, pvy = w / 2, float(h - 1)
        return SpriteMeta((w, h), (pvx, pvy), (0, 0), GROUND_PIXELS_PER_UNIT)

    pvx, pvy = _RESOURCE_TEMPLATE.pivot_pil
    paste_x = int(round(pvx - bc_x))
    paste_y = int(round(pvy - bc_y))
    return SpriteMeta(_RESOURCE_TEMPLATE.logical_size, _RESOURCE_TEMPLATE.pivot_pil, (paste_x, paste_y), GROUND_PIXELS_PER_UNIT)


def _load_from_unity(name: str) -> Optional[SpriteMeta]:
    try:
        import UnityPy
    except ImportError:
        return None

    src = Path(__file__).resolve().parent.parent / "Polytopia.app" / "Contents" / "Resources" / "Data"
    if not src.is_dir():
        return None

    env = UnityPy.load(str(src))
    for obj in env.objects:
        if obj.type.name != "Sprite":
            continue
        data = obj.read()
        if getattr(data, "m_Name", "") != name:
            continue
        rect = data.m_Rect
        tr = data.m_RD.textureRect
        off = data.m_RD.textureRectOffset
        pivot = data.m_Pivot
        w, h = int(round(rect.width)), int(round(rect.height))
        px, py = _unity_pivot_to_pil(pivot.x, pivot.y, rect.width, rect.height)
        paste_x = int(round(off.x))
        paste_y = int(round(h - (off.y + tr.height)))
        ppu = float(getattr(data, "m_PixelsToUnits", GROUND_PIXELS_PER_UNIT))
        return SpriteMeta(logical_size=(w, h), pivot_pil=(px, py), paste_at=(paste_x, paste_y), pixels_per_unit=ppu)
    return None


# Cached at import; extended via UnityPy or PNG inference.
_TERRAIN_META: dict[str, SpriteMeta] = {
    "ground_imperius": SpriteMeta((256, 245), (128.0, 244.0), (0, 0), GROUND_PIXELS_PER_UNIT),
}


def get_sprite_meta(name: str, sprite_dir: Path | str | None = None) -> Optional[SpriteMeta]:
    stem = name.replace(".png", "")
    if stem in _TERRAIN_META:
        return _TERRAIN_META[stem]

    loaded = _load_from_unity(stem)
    if loaded is not None:
        _TERRAIN_META[stem] = loaded
        return loaded

    if stem.startswith("ground_"):
        return _TERRAIN_META.get("ground_imperius")

    root = Path(sprite_dir) if sprite_dir is not None else _DEFAULT_SPRITE_DIR
    path = root / f"{stem}.png"
    if path.is_file():
        img = Image.open(path).convert("RGBA")
        if stem.startswith("Forest_"):
            meta = _infer_forest_meta(img)
        elif stem.startswith("mountain_"):
            meta = _infer_mountain_meta(img)
        elif stem.startswith("ResourceGFX_"):
            meta = _infer_resource_meta(img, stem)
        else:
            return None
        _TERRAIN_META[stem] = meta
        return meta

    return None


def pad_to_logical(img: Image.Image, meta: SpriteMeta) -> Image.Image:
    """Paste cropped PNG into Unity logical sprite rect."""
    canvas = Image.new("RGBA", meta.logical_size, (0, 0, 0, 0))
    canvas.alpha_composite(img, meta.paste_at)
    return canvas
