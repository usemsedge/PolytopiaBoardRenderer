"""Procedural Market tower — BuildingTowerHelper composite.

Level = min(8, sum of adjacent SAME-OWNER Windmill/Sawmill/Forge levels).
Draws a base + (level-1) stacked sections + roof + Wood/Metal/Farmers floor
decorations into ONE Image.

Geometry (from binary):
  GetNumberOfSections @0x2AAA390 -> level - 1
  SetupInternal @0x2AA4610:  sectionBaseY=section1.y, sectionHeight=section2.y-section1.y,
                             roofOffsetY=roof.y-section2.y
  UpdateTowerSections @0x2AA4B34:  section i localY = sectionBaseY + i*sectionHeight,
                                   roof  localY = sectionBaseY + (n-1)*sectionHeight + roofOffsetY
"""
from __future__ import annotations

import json
import math
import os
from typing import List, Optional, Tuple

import enums as E
import projection as P
import spritemeta as SM
from image import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

with open(os.path.join(_ROOT, "market_parts.json")) as _f:
    _MARKET_PARTS = {p["node"]: p for p in json.load(_f)}
with open(os.path.join(_ROOT, "sprite_reg.json")) as _f:
    _SPRITE_REG = json.load(_f)

MARKET_MAX_LEVEL = 8
# Adjacent income building -> floor-decoration node on the Market prefab (engine fields
# WoodMarket/MetalMarket/FarmersMarket; hasWindmill/hasSawmill/hasForge in UpdateObjectInternal).
_MARKET_FEEDERS = {
    int(E.Improvement.WINDMILL): "FarmersMarket",
    int(E.Improvement.SAWMILL): "WoodMarket",
    int(E.Improvement.FORGE): "MetalMarket",
}


def _market_pivot(name: str) -> Tuple[float, float]:
    r = _SPRITE_REG.get(name)
    if r:
        return tuple(r["pivot"])
    return SM.pivot(name) or (0.5, 0.5)


def _market_state(ctx, tile) -> Tuple[int, set]:
    """(level, decoration-nodes) for a market."""
    owner = tile.owner
    total = 0
    decos = set()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nt = ctx.tile_at(tile.x + dx, tile.y + dy)
            if nt is None or nt.improvement is None or nt.owner != owner:
                continue
            node = _MARKET_FEEDERS.get(int(nt.improvement.type))
            if node:
                decos.add(node)
                total += max(1, nt.improvement.level)
    return min(MARKET_MAX_LEVEL, total), decos


def build(ctx, tile) -> Optional[Tuple[Image, float, float]]:
    """Composite the market tower.

    Returns ``(image, origin_x, origin_y)`` where the origin is the building's
    SpriteContainer world point (seats on the tile centre), or None if parts are
    missing. Caller emits ``dx = round(-origin_x), dy = round(-origin_y)``.
    """
    level, decos = _market_state(ctx, tile)
    PPU = P.PPU
    base = _MARKET_PARTS.get("BaseMarket")
    sec1 = _MARKET_PARTS.get("Market_part_section1")
    sec2 = _MARKET_PARTS.get("Market_part_section2")
    roof = _MARKET_PARTS.get("Roof")
    if not (base and sec1 and sec2 and roof):
        return None
    section_base_y = sec1["pos"][1]
    section_h = sec2["pos"][1] - sec1["pos"][1]
    roof_off_y = roof["pos"][1] - sec2["pos"][1]
    n = max(0, level - 1)                              # numberOfSections = level - 1

    # Base, then present floor decos, then sections bottom->top (higher rings paint
    # later), then the roof cap last.
    draw: List[Tuple[str, float, float, list]] = [
        (base["sprite"], base["pos"][0], base["pos"][1], base["scale"])]
    for node in ("MetalMarket", "FarmersMarket", "WoodMarket"):
        if node in decos and node in _MARKET_PARTS:
            p = _MARKET_PARTS[node]
            draw.append((p["sprite"], p["pos"][0], p["pos"][1], p["scale"]))
    for i in range(n):
        draw.append((sec1["sprite"], sec1["pos"][0], section_base_y + i * section_h, sec1["scale"]))
    draw.append((roof["sprite"], roof["pos"][0],
                 section_base_y + (n - 1) * section_h + roof_off_y, roof["scale"]))

    placed = []
    minx = miny = 1e18
    maxx = maxy = -1e18
    for sprite, px, py, scale in draw:
        name = ctx.resolve(sprite, 0, 0)[0] or sprite
        if not ctx.exists(name):
            continue
        try:
            img = ctx.store.get(name)
        except KeyError:
            continue
        rs = SM.render_scale(name)
        dw = max(1, round(img.w * scale[0] * rs))
        dh = max(1, round(img.h * scale[1] * rs))
        if dw != img.w or dh != img.h:
            img = img.resized(dw, dh)
        pvx, pvy = _market_pivot(name)
        piv_x = px * PPU
        piv_y = -py * PPU                              # world Y up -> pixel Y down
        tlx = piv_x - pvx * dw
        tly = piv_y - (1.0 - pvy) * dh
        placed.append((img, tlx, tly))
        minx = min(minx, tlx); miny = min(miny, tly)
        maxx = max(maxx, tlx + dw); maxy = max(maxy, tly + dh)

    if not placed:
        return None
    W = int(math.ceil(maxx - minx))
    H = int(math.ceil(maxy - miny))
    canvas = Image.new(W, H, (0, 0, 0, 0))
    for img, tlx, tly in placed:
        canvas.paste(img, round(tlx - minx), round(tly - miny))
    # World origin (0,0) maps to (-minx, -miny) inside the composite after recentring.
    return canvas, -minx, -miny
