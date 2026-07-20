"""Transport component: roads / routes (8 directional segments) + bridges.

Tile-local port of the old ``layer_transport.items`` (see CONTRACT.md).  Renders
baked sprites in TILE-LOCAL space (diamond centre = origin (0,0), +y down).

Road convention (Single Source of Truth):
  N → (x, y-1), roads0001
  NE → (x+1, y-1), roads0002
  Sprites numbered clockwise: NW=0, N=1, NE=2, E=3, SE=4, S=5, SW=6, W=7.

Placement (source-code confirmed, CreateRoad @ 0x2CE2A1C):
  left = round(-pvx * w),  top = round(-pvy * h)   [screen Y-down, sprite_reg.json pivot]
  Scale = 1.0; no rotation or flip.

Bridges: ImprovementData.Type Bridge(48) → child ``bridge`` (NW-SE) or
  ``bridge-flipped`` (NE-SW when ImprovementState.level == 1); SORT_BUILDINGS layer.
"""
from __future__ import annotations

import json
import os
from typing import List

import enums as E
import spritelookup as SL
from context import Placement
from image import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "sprite_reg.json")) as _f:
    _SPRITE_REG = json.load(_f)


def _road_pivot(name: str):
    """(pvx, pvy) trimmed-PNG pivot (screen Y-down). Falls back to (0.5, 0.5)."""
    r = _SPRITE_REG.get(name)
    return tuple(r["pivot"]) if r else (0.5, 0.5)


# GridDirection → neighbour grid delta (dx, dy).
# N=(0,-1) means y decreases (away from viewer in isometric = up on map).
_DIR_DELTA = {
    E.GridDirection.NW: (-1, 1),
    E.GridDirection.N:  ( 0, 1),
    E.GridDirection.NE: ( 1, 1),
    E.GridDirection.E:  ( 1,  0),
    E.GridDirection.SE: ( 1,  -1),
    E.GridDirection.S:  ( 0,  -1),
    E.GridDirection.SW: (-1,  -1),
    E.GridDirection.W:  (-1,  0),
}


# Per-direction pixel nudge (+x right, +y down).  Key = GridDirection.
C = 40
ROAD_OFFSET = {
    E.GridDirection.NW: (0, 0),   # roads0002 
    E.GridDirection.N:  (0, - C),   # roads0003 upper left
    E.GridDirection.NE: (0, - 2 * C),   # roads0004 straight up
    E.GridDirection.E:  (0, - C),   # roads0005 
    E.GridDirection.SE: (0, 0),  # roads0006 
    E.GridDirection.S:  (0, C),   # roads0007 
    E.GridDirection.SW: (0, 2 * C),   # roads0000 
    E.GridDirection.W:  (0, C),   # roads0001 
}

# Bridge deck downward nudge (px).
BRIDGE_DY = 0.0

# Connectable improvement types (road endpoints).
_CONNECTABLE_IMPROVEMENTS = frozenset({
    int(E.Improvement.CITY),
    int(E.Improvement.BRIDGE),
    int(E.Improvement.PORT),
})


def _has_road(tile) -> bool:
    if tile.has_road:
        return True
    imp = tile.improvement
    return imp is not None and int(imp.type) in _CONNECTABLE_IMPROVEMENTS


def _is_connectable(tile) -> bool:
    if tile.has_road:
        return True
    imp = tile.improvement
    return imp is not None and int(imp.type) in _CONNECTABLE_IMPROVEMENTS


def _has_matching_transport_path(a, b) -> bool:
    if _is_connectable(a) and _is_connectable(b):
        return True
    return a.has_route and b.has_route


def _skin_suffix(ctx, tile) -> str:
    _tribe, skin = ctx.tile_theme(tile)
    tok = SL.theme_suffix(0, skin) if skin else None
    return f"_{tok}" if tok else ""


def items(ctx, x: int, y: int) -> List[Placement]:
    tile = ctx.tile_at(x, y)
    if tile is None:
        return []

    out: List[Placement] = []

    road  = _has_road(tile)
    route = tile.has_route

    if road or route:
        is_road = road
        base = "roads000" if is_road else "routes000"
        skin_suffix = _skin_suffix(ctx, tile) if not is_road else ""
        for d, (ddx, ddy) in _DIR_DELTA.items():
            nb = ctx.tile_at(tile.x + ddx, tile.y + ddy)
            if nb is None:
                continue
            if not _has_matching_transport_path(tile, nb):
                continue
            name = f"{base}{d}"
            print(f"tile {tile.x, tile.y} dir_delta {ddx, ddy}, new tile {nb.x, nb.y} road {name}")
            if not is_road and skin_suffix:
                skinned = name + skin_suffix
                if ctx.exists(skinned):
                    name = skinned
            if not ctx.exists(name):
                continue
            img = ctx.bake(name, scale=1.0)
            if img is None:
                continue
            pvx, pvy = _road_pivot(name)
            odx, ody = ROAD_OFFSET.get(d, (0, 0))
            left = round(-pvx * img.w) + odx
            top  = round(-pvy * img.h) + ody
            out.append(Placement(E.SORT_TRANSPORT, img, left, top))

    # ---- bridge -------------------------------------------------------
    imp = tile.improvement
    if imp is not None and imp.type == E.Improvement.BRIDGE:
        horizontal = (imp.level == 1)
        base = "bridge-flipped" if horizontal else "bridge"
        _tribe, skin = ctx.tile_theme(tile)
        name, _ = ctx.resolve(base, 0, skin)
        if name and ctx.exists(name):
            img = ctx.bake(name)
            if img is not None:
                left, top = ctx.seat_base(name, img.w, img.h)
                top = round(top + BRIDGE_DY)
                out.append(Placement(E.SORT_BUILDINGS, img, left, top))

    return out
