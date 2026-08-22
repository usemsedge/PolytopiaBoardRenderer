"""Simple and generated improvements component (tile-local port of layer_improvements.py).

Renders the tile's ImprovementState into baked, tile-local Placements:

- SIMPLE improvements pick ONE themed sprite via the IMPROVEMENT_BASE table (optionally
  leveled) or the Monument table, baked at its IMPROVEMENT_SCALES factor and pivot-seated
  on the tile centre (ctx.seat_pivot, the port of layers._seat) at SORT_BUILDINGS, with an
  IMPROVEMENT_Y_OFFSETS height-scaled vertical nudge.

- CITY / MARKET / LIGHTHOUSE are procedural composites from ``generated_improvements/``:
  each module's ``build(ctx, tile)`` returns a single Image + origin, seated on the
  diamond centre.

Tile-local space: the diamond CENTRE is the origin (0, 0), +y down. Every Placement's
(dx, dy) is the top-left of its baked image relative to that origin. Old canvas anchoring
collapses to anchor = (0, 0), so the ctx.seat_* helpers already yield correct local tops.
"""
from __future__ import annotations

from typing import List

import enums as E
from context import Placement
from generated_improvements import cities, lighthouses, markets

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
    E.Improvement.OUTPOST: ("iceport", False),          # Polaris outpost = iceport art
    E.Improvement.ICE_BANK: ("icebank_icon", False),
    E.Improvement.ICE_TEMPLE: ("Ice_Temple", True),
    E.Improvement.FUNGI: ("fungi", True),
    E.Improvement.ALGAE: ("algae", False),
    E.Improvement.MYCELIUM: ("Mycelium", False),
    E.Improvement.CLATHRUS: ("clathrus", True),
    E.Improvement.HIDDEN_SANCTUARY: ("sanctuary", True),
    # CITY / MARKET / LIGHTHOUSE → generated_improvements/
    E.Improvement.ATOLL: ("atoll", False),
    E.Improvement.AQUAFARM: ("Aqua_Farm", False),
}


IMPROVEMENT_SCALES = {
    E.Improvement.LUMBER_HUT: 0.8,
}

# Extra vertical seat per improvement type, as a FRACTION of the drawn sprite's height
# (negative = up, positive = down). Scaling by height keeps the nudge proportional across
# sprites instead of being a hard pixel count. Applied in the simple-improvement path.
# Generated towers are NOT listed here: their build() already returns the composite's
# SpriteContainer origin (ox, oy), and we seat that on the diamond centre.
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


def _seat_generated(built, sublayer: int) -> List[Placement]:
    """Seat a ``build()`` result so its world origin lands on the diamond centre."""
    if built is None:
        return []
    img, ox, oy = built
    return [Placement(sublayer, img, round(-ox), round(-oy))]


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
    out of bounds, or has no improvement."""
    tile = ctx.tile_at(x, y)
    if tile is None or tile.improvement is None:
        return []
    st = tile.improvement
    if st.type == E.Improvement.CITY:
        # Houses+wall composite; SORT_HOUSES keeps cities under SORT_BUILDINGS peers.
        return _seat_generated(cities.build(ctx, tile), E.SORT_HOUSES)
    if st.type == E.Improvement.MARKET:
        return _seat_generated(markets.build(ctx, tile), E.SORT_BUILDINGS)
    if st.type == E.Improvement.LIGHTHOUSE:
        return _seat_generated(lighthouses.build(ctx, tile), E.SORT_BUILDINGS)
    return _simple_items(ctx, tile)
