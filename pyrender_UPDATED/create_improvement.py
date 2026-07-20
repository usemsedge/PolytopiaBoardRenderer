"""Simple and market improvements component (tile-local port of layer_improvements.py).

Renders the tile's ImprovementState into baked, tile-local Placements:

- SIMPLE improvements pick ONE themed sprite via the IMPROVEMENT_BASE table (optionally
  leveled) or the Monument table, baked at its IMPROVEMENT_SCALES factor and pivot-seated
  on the tile centre (ctx.seat_pivot, the port of layers._seat) at SORT_BUILDINGS, with an
  IMPROVEMENT_Y_OFFSETS height-scaled vertical nudge.

- MARKET (type == Market) is a procedural tower: level = min(8, sum of adjacent SAME-OWNER
  Windmill/Sawmill/Forge levels); a base + (level-1) stacked sections + roof + Wood/Metal/
  Farmers floor decorations are composited into ONE Image, emitted at SORT_BUILDINGS.

City tiles are handled by create_city (called directly by create_tile).

Tile-local space: the diamond CENTRE is the origin (0, 0), +y down. Every Placement's
(dx, dy) is the top-left of its baked image relative to that origin. Old canvas anchoring
collapses to anchor = (0, 0), so the ctx.seat_* helpers already yield correct local tops.
"""
from __future__ import annotations

import json
import math
import os
from typing import List, Tuple

import context
import enums as E
import projection as P
import spritemeta as SM
from context import Placement
from image import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
# Market building prefab parts (tools/extract_market.py) + trimmed-PNG pivots, used to
# reconstruct the procedural Market tower (see _market_items / _build_market below).
with open(os.path.join(_HERE, "market_parts.json")) as _f:
    _MARKET_PARTS = {p["node"]: p for p in json.load(_f)}
with open(os.path.join(_HERE, "sprite_reg.json")) as _f:
    _SPRITE_REG = json.load(_f)

# ---------------------------------------------------------------- simple table
# ImprovementData.Type -> base sprite name (recon §2). Spaces -> '_' in atlas.
# Leveled families carry the building level; resolve() appends "_<level>".
IMPROVEMENT_BASE = {
    E.Improvement.RUIN: ("ruin", False),
    E.Improvement.CUSTOMS_HOUSE: ("Customs_House", True),
    E.Improvement.FARM: ("Farm", False),
    E.Improvement.WINDMILL: ("Windmill", True),
    E.Improvement.PORT: ("Port", False),
    E.Improvement.LUMBER_HUT: ("Lumber_Hut", False),
    E.Improvement.SAWMILL: ("Sawmill", True),
    E.Improvement.TEMPLE: ("Temple", True),
    E.Improvement.FOREST_TEMPLE: ("Forest_Temple", True),
    E.Improvement.WATER_TEMPLE: ("Water_Temple", True),
    E.Improvement.MOUNTAIN_TEMPLE: ("Mountain_Temple", True),
    E.Improvement.MINE: ("Mine", False),
    E.Improvement.FORGE: ("Forge", True),
    E.Improvement.SANCTUARY: ("sanctuary", True),
    E.Improvement.ICE_BANK: ("icebank_icon", False),
    E.Improvement.ICE_TEMPLE: ("Ice_Temple", True),
    # MARKET is not a single sprite — it's a procedural tower built from adjacent income
    # buildings; see _market_items / _build_market (handled before this table).
    E.Improvement.ATOLL: ("atoll", False),
    E.Improvement.AQUAFARM: ("Aqua_Farm", False),
}


IMPROVEMENT_SCALES = {
    E.Improvement.LUMBER_HUT: 0.8,
}

# Extra vertical seat per improvement type, as a FRACTION of the drawn sprite's height
# (negative = up, positive = down). Scaling by height keeps the nudge proportional across
# sprites instead of being a hard pixel count. Applied in the simple-improvement path.
# (The Market is NOT listed here: _build_market already returns the composite's
# SpriteContainer origin (ox, oy), and _market_items seats that on the diamond centre. A
# blanket height-fraction nudge here just shoves the tower off the tile -- the old value
# of 30 multiplied the tower height by 30, pushing it ~5600px off-canvas.)
IMPROVEMENT_Y_OFFSETS = {}


def _y_offset_px(imp_type, height: float) -> float:
    """Vertical nudge in pixels for ``imp_type``: its IMPROVEMENT_Y_OFFSETS fraction times the
    sprite/render ``height`` (+ = down, - = up). 0.0 when the type has no configured offset."""
    return IMPROVEMENT_Y_OFFSETS.get(imp_type, 0.0) * height


# Monuments 23..29 -> Monument1..Monument7 (themed, no level).
_MONUMENTS = {
    E.Improvement.MONUMENT1: 1, E.Improvement.MONUMENT2: 2, E.Improvement.MONUMENT3: 3,
    E.Improvement.MONUMENT4: 4, E.Improvement.MONUMENT5: 5, E.Improvement.MONUMENT6: 6,
    E.Improvement.MONUMENT7: 7,
}

# ---------------------------------------------------------------- market tower
# The Market (ImprovementData.Type.Market) is not a flat icon: the engine's `Market : Building`
# renders a procedural tower via BuildingTowerHelper. Its level = the income it draws from
# adjacent same-owner income buildings (Windmill/Sawmill/Forge), capped at 8; the renderer then
# draws `level-1` stacked sections between a base and a roof, with Wood/Metal/Farmers floor
# decorations toggled by which of those neighbours exist. Geometry (recovered from the binary):
#   GetNumberOfSections @0x2AAA390 -> level - 1
#   SetupInternal @0x2AA4610:  sectionBaseY=section1.y, sectionHeight=section2.y-section1.y,
#                              roofOffsetY=roof.y-section2.y
#   UpdateTowerSections @0x2AA4B34:  section i localY = sectionBaseY + i*sectionHeight,
#                                    roof  localY = sectionBaseY + (n-1)*sectionHeight + roofOffsetY
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
    """(level, decoration-nodes) for a market: level = min(8, sum of adjacent SAME-OWNER
    Windmill/Sawmill/Forge building levels); decos = the floor nodes for the present types."""
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


def _build_market(ctx, level: int, decos: set):
    """Composite the market tower into one image; returns (image, origin_x, origin_y) where the
    origin is the building's SpriteContainer world point (which seats on the tile centre).

    (origin_x, origin_y) is the position, INSIDE the composite, of the tile-local origin: the
    caller emits dx = round(-origin_x), dy = round(-origin_y) so the world point lands on the
    diamond centre (in the old code this was frame.anchor; in local space the anchor is (0,0))."""
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

    # Build the ordered draw list: base, then present floor decos, then sections bottom->top
    # (each higher ring sits on and occludes the top of the one below it, so it must paint
    # later/on top), then the roof cap last of all.
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
    # The world origin (0,0) maps to pixel (0,0) before recentring; after shifting by
    # (-minx,-miny) it lands at (-minx, -miny) inside the composite.
    return canvas, -minx, -miny


def _market_items(ctx, tile) -> List[Placement]:
    level, decos = _market_state(ctx, tile)
    built = _build_market(ctx, level, decos)
    if built is None:
        return []
    img, ox, oy = built
    # In tile-local space the anchor is the origin (0,0); seat the composite so its world
    # origin (ox, oy) lands on the diamond centre. The tower's foot then sits on the tile.
    return [Placement(E.SORT_BUILDINGS, img, round(-ox), round(-oy))]


# ---------------------------------------------------------------- simple improvements
def _simple_items(ctx, tile) -> List[Placement]:
    st = tile.improvement
    t = st.type
    tribe, skin = ctx.player_tribe_skin(tile.owner)

    if t in _MONUMENTS:
        base = "Monument" + str(_MONUMENTS[t])
        name, _ = ctx.resolve(base, tribe, skin)
    elif t in IMPROVEMENT_BASE:
        base, leveled = IMPROVEMENT_BASE[t]
        lvl = max(1, st.level) if leveled else -1
        name, _ = ctx.resolve(base, tribe, skin, level=lvl)
    else:
        return []

    if not name:
        return []

    # Bake at the type's render scale (IMPROVEMENT_SCALES on top of the measured render-scale
    # that ctx.bake always applies), then pivot-seat on the tile centre (port of layers._seat).
    scale = IMPROVEMENT_SCALES.get(t, 1.0)
    img = ctx.bake(name, scale=scale)
    if img is None:
        return []
    left, top = ctx.seat_pivot(name, img.w, img.h)
    # IMPROVEMENT_Y_OFFSETS nudge: a fraction of the drawn height (+ = down), applied to dy.
    top += round(_y_offset_px(t, img.h))

    return [Placement(E.SORT_BUILDINGS, img, left, top)]


# ---------------------------------------------------------------- entry point
def items(ctx, x: int, y: int) -> List[Placement]:
    """Tile-local improvement Placements for tile (x, y). Returns [] when the tile is hidden,
    out of bounds, or has no improvement. City tiles are handled by create_city."""
    tile = ctx.tile_at(x, y)
    if tile is None or tile.improvement is None:
        return []
    st = tile.improvement
    if st.type == E.Improvement.CITY:
        return []
    if st.type == E.Improvement.MARKET:
        return _market_items(ctx, tile)
    return _simple_items(ctx, tile)
