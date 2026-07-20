"""Per-sprite metadata (pivot + pixelsToUnits) extracted from the Unity bundle.

Gives each sprite its true render scale = REF_PPU / sprite_ppu, so objects are
sized in correct world proportion (a sprite's world size = pixels / ppu). This
replaces hand-tuned scale constants with measured values. Missing sprites (e.g.
atlas-packed ground/house art not present as standalone Sprite objects) fall back
to the nearest same-family sibling, else native scale.
"""
from __future__ import annotations
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_HERE, "sprite_pivots.json")

# Reference PPU = the terrain tile density (water/ice/ground ≈ 265); matches the
# renderer's projection PPU (256 / TILE_WIDTH = 266.06), so terrain renders ~native.
REF_PPU = 266.06

try:
    _DATA = json.load(open(_PATH))
except Exception:
    _DATA = {}

_ppu_cache = {}


def _lookup_ppu(name):
    if name in _DATA:
        return _DATA[name]["ppu"]
    base = name[:-8] if name.endswith("_Outline") else name
    if base in _DATA:
        return _DATA[base]["ppu"]
    # walk up the family: strip trailing _<token>s; use the MEDIAN ppu of non-outline
    # siblings under that prefix (robust to outliers like odd/UI variants).
    parts = base.split("_")
    for cut in range(len(parts) - 1, 0, -1):
        pre = "_".join(parts[:cut])
        sibs = sorted(v["ppu"] for k, v in _DATA.items()
                      if (k == pre or k.startswith(pre + "_")) and not k.endswith("_Outline"))
        if sibs:
            return sibs[len(sibs) // 2]
    return None


def ppu(name):
    if name not in _ppu_cache:
        _ppu_cache[name] = _lookup_ppu(name)
    return _ppu_cache[name]


def render_scale(name):
    """Scale to draw this sprite's PNG at so its world size is correct (1.0 if unknown)."""
    p = ppu(name)
    if not p or p <= 0:
        return 1.0
    return REF_PPU / p


def pivot(name):
    """Normalized (x, y) pivot from bottom-left, or None if unknown."""
    if name in _DATA:
        return tuple(_DATA[name]["pivot"])
    base = name[:-8] if name.endswith("_Outline") else name
    if base in _DATA:
        return tuple(_DATA[base]["pivot"])
    return None
