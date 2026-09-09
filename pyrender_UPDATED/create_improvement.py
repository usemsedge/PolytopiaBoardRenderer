"""Simple and generated improvements component (tile-local port of layer_improvements.py).

Renders the tile's ImprovementState into baked, tile-local Placements:

- SIMPLE improvements pick ONE themed sprite via the IMPROVEMENT_BASE table (optionally
  leveled) or the Monument table, baked at its IMPROVEMENT_SCALES factor and pivot-seated
  on the tile centre (ctx.seat_pivot, the port of layers._seat) at SORT_BUILDINGS, with
  IMPROVEMENT_DX / IMPROVEMENT_DY pixel nudges.

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

# Per-type pixel nudge on top of seat_pivot / generated origin. +dx = right, +dy = down.
# Missing keys → 0. Applies to both the simple sprite path and generated city/market/lighthouse.
IMPROVEMENT_DX = {
    E.Improvement.CITY: 0,
    E.Improvement.RUIN: 0,
    E.Improvement.CUSTOMS_HOUSE: 0,
    E.Improvement.FARM: 0,
    E.Improvement.WINDMILL: 0,
    E.Improvement.PORT: 0,
    E.Improvement.LUMBER_HUT: 0,
    E.Improvement.SAWMILL: 0,
    E.Improvement.TEMPLE: 0,
    E.Improvement.FOREST_TEMPLE: 0,
    E.Improvement.WATER_TEMPLE: 0,
    E.Improvement.MOUNTAIN_TEMPLE: 0,
    E.Improvement.MINE: 0,
    E.Improvement.FORGE: 0,
    E.Improvement.MONUMENT1: 0,
    E.Improvement.MONUMENT2: 0,
    E.Improvement.MONUMENT3: 0,
    E.Improvement.MONUMENT4: 0,
    E.Improvement.MONUMENT5: 0,
    E.Improvement.MONUMENT6: 0,
    E.Improvement.MONUMENT7: 0,
    E.Improvement.SANCTUARY: 0,
    E.Improvement.OUTPOST: 0,
    E.Improvement.ICE_BANK: 0,
    E.Improvement.ICE_TEMPLE: 0,
    E.Improvement.FUNGI: 0,
    E.Improvement.ALGAE: 0,
    E.Improvement.MYCELIUM: 0,
    E.Improvement.CLATHRUS: 0,
    E.Improvement.HIDDEN_SANCTUARY: 0,
    E.Improvement.LIGHTHOUSE: 0,
    E.Improvement.AQUAFARM: 0,
    E.Improvement.MARKET: 0,
    E.Improvement.ATOLL: 0,
}
IMPROVEMENT_DY = {
    E.Improvement.CITY: 0,
    E.Improvement.RUIN: 0,
    E.Improvement.CUSTOMS_HOUSE: 0,
    E.Improvement.FARM: 0,
    E.Improvement.WINDMILL: 0,
    E.Improvement.PORT: 10,
    E.Improvement.LUMBER_HUT: 0,
    E.Improvement.SAWMILL: 0,
    E.Improvement.TEMPLE: 0,
    E.Improvement.FOREST_TEMPLE: 0,
    E.Improvement.WATER_TEMPLE: 0,
    E.Improvement.MOUNTAIN_TEMPLE: 0,
    E.Improvement.MINE: 0,
    E.Improvement.FORGE: 0,
    E.Improvement.MONUMENT1: 0,
    E.Improvement.MONUMENT2: 0,
    E.Improvement.MONUMENT3: 0,
    E.Improvement.MONUMENT4: 0,
    E.Improvement.MONUMENT5: 0,
    E.Improvement.MONUMENT6: 0,
    E.Improvement.MONUMENT7: 0,
    E.Improvement.SANCTUARY: 0,
    E.Improvement.OUTPOST: 0,
    E.Improvement.ICE_BANK: 0,
    E.Improvement.ICE_TEMPLE: 0,
    E.Improvement.FUNGI: 0,
    E.Improvement.ALGAE: 0,
    E.Improvement.MYCELIUM: 0,
    E.Improvement.CLATHRUS: 0,
    E.Improvement.HIDDEN_SANCTUARY: 0,
    E.Improvement.LIGHTHOUSE: 0,
    E.Improvement.AQUAFARM: 0,
    E.Improvement.MARKET: 0,
    E.Improvement.ATOLL: 0,
}

# Extra raise for ports on swamp / flooded field (+ = down, so negative = up).
PORT_WETLAND_DY = -8


def _is_swamp_or_flooded(tile) -> bool:
    """Swamp-skin or flooded/wetland land — ports get a small extra lift here."""
    if tile is None:
        return False
    if int(getattr(tile, "skin", 0) or 0) == int(E.Skin.SWAMP):
        return True
    effects = getattr(tile, "effects", ()) or ()
    if int(E.TileEffect.FLOODED) in effects or int(E.TileEffect.SWAMPED) in effects:
        return True
    return tile.terrain in (E.Terrain.WETLAND, E.Terrain.MANGROVE)


def _nudge(imp_type, tile=None) -> tuple:
    """(dx, dy) pixel nudge for ``imp_type``. Missing keys are 0."""
    dx = IMPROVEMENT_DX.get(imp_type, 0)
    dy = IMPROVEMENT_DY.get(imp_type, 0)
    if imp_type == E.Improvement.PORT and _is_swamp_or_flooded(tile):
        dy += PORT_WETLAND_DY
    return dx, dy


# Monuments 23..29 -> Monument1..Monument7 (themed, no level).
_MONUMENTS = {
    E.Improvement.MONUMENT1: 1, E.Improvement.MONUMENT2: 2, E.Improvement.MONUMENT3: 3,
    E.Improvement.MONUMENT4: 4, E.Improvement.MONUMENT5: 5, E.Improvement.MONUMENT6: 6,
    E.Improvement.MONUMENT7: 7,
}


def _seat_generated(built, sublayer: int, imp_type) -> List[Placement]:
    """Seat a ``build()`` result so its world origin lands on the diamond centre."""
    if built is None:
        return []
    img, ox, oy = built
    ndx, ndy = _nudge(imp_type, None)
    return [Placement(sublayer, img, round(-ox) + ndx, round(-oy) + ndy)]


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
    ndx, ndy = _nudge(t, tile)
    return [Placement(E.SORT_BUILDINGS, img, left + ndx, top + ndy)]


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
        return _seat_generated(cities.build(ctx, tile), E.SORT_HOUSES, st.type)
    if st.type == E.Improvement.MARKET:
        return _seat_generated(markets.build(ctx, tile), E.SORT_BUILDINGS, st.type)
    if st.type == E.Improvement.LIGHTHOUSE:
        return _seat_generated(lighthouses.build(ctx, tile), E.SORT_BUILDINGS, st.type)
    return _simple_items(ctx, tile)
