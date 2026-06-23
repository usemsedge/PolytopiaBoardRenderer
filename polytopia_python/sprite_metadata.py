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


def _unity_pivot_to_pil(pivot_x: float, pivot_y: float, width: float, height: float) -> tuple[float, float]:
    """Unity pivot (0,0 = bottom-left) → PIL top-left origin."""
    px = pivot_x * width
    py = (1.0 - pivot_y) * height
    if pivot_y == 0.0:
        py = height - 1.0
    return px, py


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


# Cached at import; extended via UnityPy. Forest/mountain paste offsets vary per tribe.
_TERRAIN_META: dict[str, SpriteMeta] = {
    "ground_imperius": SpriteMeta((256, 245), (128.0, 244.0), (0, 0), GROUND_PIXELS_PER_UNIT),
    "Forest_imperius": SpriteMeta((256, 198), (128.0, 99.0), (7, 6), 279.1562194824219),
    "Forest_bardur": SpriteMeta((256, 198), (128.0, 99.0), (13, 21), 279.1562194824219),
    "Forest_kickoo": SpriteMeta((256, 198), (128.0, 99.0), (0, 16), 279.1562194824219),
    "Forest_zebasi": SpriteMeta((256, 198), (128.0, 99.0), (28, 38), 279.1562194824219),
    "mountain_imperius": SpriteMeta((232, 256), (116.0, 255.0), (0, 15), 239.01657104492188),
    "mountain_bardur": SpriteMeta((232, 256), (116.0, 255.0), (0, 15), 239.01657104492188),
    "mountain_kickoo": SpriteMeta((232, 256), (116.0, 255.0), (0, 19), 239.01657104492188),
    "mountain_zebasi": SpriteMeta((232, 256), (116.0, 255.0), (0, 33), 239.242919921875),
}


def get_sprite_meta(name: str) -> Optional[SpriteMeta]:
    stem = name.replace(".png", "")
    if stem in _TERRAIN_META:
        return _TERRAIN_META[stem]
    loaded = _load_from_unity(stem)
    if loaded is not None:
        _TERRAIN_META[stem] = loaded
        return loaded
    # Ground tiles share the same canvas; features must not fall back to imperius.
    if stem.startswith("ground_"):
        return _TERRAIN_META.get("ground_imperius")
    return None


def pad_to_logical(img: Image.Image, meta: SpriteMeta) -> Image.Image:
    """Paste cropped PNG into Unity logical sprite rect."""
    canvas = Image.new("RGBA", meta.logical_size, (0, 0, 0, 0))
    canvas.alpha_composite(img, meta.paste_at)
    return canvas
