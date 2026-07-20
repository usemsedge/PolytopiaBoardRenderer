r"""Shoreline / coast component (Tile.RenderShorelines 0x2CDEB78).

Ported to the tile-local create_* contract (see CONTRACT.md / context.py) from the
engine slice documented in recon/shorelines.md.

For each non-frozen Water tile we emit up to four shoreline foam strips, one per
grid neighbour (N/S/E/W) that ``IsLand`` (Field/Mountain/Forest/Ice). The single
``shoreline`` sprite (or ``shoreline_swamp`` when the land neighbour is a swamp) is
placed along the corresponding iso edge of the tile's diamond.

Geometry (the part recon/shorelines.md flags as the open question)
-----------------------------------------------------------------
In the engine, ``ShoreLineContainer`` owns four child ``PolytopiaSpriteRenderer``s
(north/south/east/west); each carries the SAME base art but a per-edge prefab
**transform that ROTATES** the strip to lie along its diamond edge. The base art is
a foam band whose long axis is horizontal and whose solid foam crest runs along its
BOTTOM, fading toward the top (verified from the sprite alpha).

The old layer (pyrender/layer_shorelines.py) only had ``flip_x`` and so pasted the
flat band centred on each edge midpoint. A flat band cannot follow the ~31deg iso
edge, so the four strips read as stray streaks crossing the tile centre. We instead
ROTATE each strip to the true edge angle so the crest hugs the coast.

Each diamond edge is the line between two vertices of the half-W x half-H diamond,
so its screen slope is ``atan2(HALF_H, HALF_W)`` (~30.9deg). Rotating the band by
that angle aligns its long axis with the edge; the sign/branch per edge is chosen so
the band's crest (its solid +y side) points OUTWARD toward the land neighbour — waves
break brightest at the shore and fade into the water. The 4 edge -> grid-neighbour
mapping (see projection.py):

    E (x+1) -> upper-right edge  (top  -> right vertex)   rotate A-180
    N (y+1) -> upper-left  edge  (left -> top   vertex)   rotate 180-A
    S (y-1) -> lower-right edge  (right-> bottom vertex)  rotate -A
    W (x-1) -> lower-left  edge  (bottom-> left vertex)   rotate +A

Emitted at SORT_TRANSPORT (2): a flat layer just above base terrain and below
terrain features / resources (recon/shorelines.md sec.4).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import context
import enums as E
import projection as P
from context import Placement
from image import Image

# --- IsLand: terrain in {Field, Mountain, Forest, Ice} (get_IsLand 0x7DCBC4) ---
_LAND = {E.Terrain.FIELD, E.Terrain.MOUNTAIN, E.Terrain.FOREST, E.Terrain.ICE}
_FROZEN_CLIMATE = 15  # IsFrozen 0x7D9E3C: Water + climate==15

# Iso edge slope: every diamond edge runs between two vertices of the
# HALF_W x HALF_H diamond, so it makes this angle with the horizontal.
_EDGE_ANGLE = math.degrees(math.atan2(P.HALF_H, P.HALF_W))   # ~30.9 deg

# Per-edge (rotation_deg, edge-midpoint dx, edge-midpoint dy). Rotation is
# clockwise-positive on screen (rotates the sprite's +x toward +y); the midpoint is
# half a diamond-vertex out from the centre along each screen axis. The branch is
# picked so the foam crest (band's solid +y side) faces OUTWARD toward the land
# neighbour — waves break brightest at the shore and fade into the water.
# The strip centre is shifted inward (into the water) by half the sprite height so
# the crest lands exactly on the shoreline edge rather than extending over land.
_HALF_QW = P.HALF_W / 2.0   # 64.0   (edge-midpoint x offset)
_HALF_QH = P.HALF_H / 2.0   # ~38.3  (edge-midpoint y offset)
_EDGES: Dict[str, Tuple[float, float, float]] = {
    "E": (_EDGE_ANGLE - 180.0, +_HALF_QW, -_HALF_QH),   # upper-right edge
    "N": (180.0 - _EDGE_ANGLE, -_HALF_QW, -_HALF_QH),   # upper-left  edge
    "S": (-_EDGE_ANGLE,        +_HALF_QW, +_HALF_QH),   # lower-right edge
    "W": (+_EDGE_ANGLE,        -_HALF_QW, +_HALF_QH),   # lower-left  edge
}

# Water surfaces are drawn recessed below the geometric diamond (create_terrain
# _water_recess); foam must sit on that surface, so drop it by the same amount.
_WATER_RECESS = 17

# Cache rotated strips: (name, edge) -> (rotated_image, raw_sprite_height).
# raw_sprite_height is the pre-rotation height; it gives the perpendicular screen
# extent of the band (rotation preserves distances).
_rot_cache: Dict[Tuple[str, str], Tuple[Image, int]] = {}


# Per-edge position nudge knobs (pixels, applied after all geometry).
# Positive dx = right, positive dy = down (screen coords).
N_DX, N_DY = 8, -8
S_DX, S_DY = -8, 8
E_DX, E_DY = -8, -8
W_DX, W_DY = 8, 8

def _edge_offset(d: str):
    return {"N": (N_DX, N_DY), "S": (S_DX, S_DY),
            "E": (E_DX, E_DY), "W": (W_DX, W_DY)}[d]


def _is_land(t) -> bool:
    return t is not None and t.terrain in _LAND


def _is_swamp_neighbour(t) -> bool:
    # neighbour.skin == Swamp(17) OR neighbour HasEffect(Swamped==2)
    if t is None:
        return False
    return (getattr(t, "skin", 0) == int(E.Skin.SWAMP)
            or int(E.TileEffect.SWAMPED) in getattr(t, "effects", ()))


def _frozen_water(tile) -> bool:
    return tile.terrain == E.Terrain.WATER and tile.climate == _FROZEN_CLIMATE


def _rotated(img: Image, degrees: float) -> Image:
    """Rotate ``img`` about its centre by ``degrees`` (clockwise-positive on screen,
    i.e. +x rotates toward +y). Returns a new Image sized to the rotated bounding box
    with the content centred; bilinear sampling, transparent outside the source."""
    if abs(degrees % 360.0) < 1e-6:
        return img
    th = math.radians(degrees)
    cos, sin = math.cos(th), math.sin(th)
    sw, sh, sp = img.w, img.h, img.px
    # Forward map (src vec -> out vec) is [[cos,-sin],[sin,cos]]; bounding box of the
    # rotated rectangle:
    nw = int(math.ceil(abs(sw * cos) + abs(sh * sin)))
    nh = int(math.ceil(abs(sw * sin) + abs(sh * cos)))
    out = bytearray(nw * nh * 4)
    ocx, ocy = (nw - 1) / 2.0, (nh - 1) / 2.0
    scx, scy = (sw - 1) / 2.0, (sh - 1) / 2.0
    for oy in range(nh):
        dy = oy - ocy
        # inverse map = transpose of forward: src = R^T * (out - ocenter)
        sx_b = scx + sin * dy   # + cos*dx added per column
        sy_b = scy + cos * dy
        ob = oy * nw * 4
        for ox in range(nw):
            dx = ox - ocx
            fx = sx_b + cos * dx
            fy = sy_b - sin * dx
            x0 = math.floor(fx); y0 = math.floor(fy)
            if x0 < -1 or x0 > sw - 1 or y0 < -1 or y0 > sh - 1:
                continue
            wx = fx - x0; wy = fy - y0
            x1 = x0 + 1; y1 = y0 + 1
            # four source-sample base indices (or -1 when that corner is off-image)
            in_x0 = 0 <= x0 < sw; in_x1 = 0 <= x1 < sw
            in_y0 = 0 <= y0 < sh; in_y1 = 0 <= y1 < sh
            i00 = (y0 * sw + x0) * 4 if (in_x0 and in_y0) else -1
            i10 = (y0 * sw + x1) * 4 if (in_x1 and in_y0) else -1
            i01 = (y1 * sw + x0) * 4 if (in_x0 and in_y1) else -1
            i11 = (y1 * sw + x1) * 4 if (in_x1 and in_y1) else -1
            o = ob + ox * 4
            for c in range(4):
                p00 = sp[i00 + c] if i00 >= 0 else 0
                p10 = sp[i10 + c] if i10 >= 0 else 0
                p01 = sp[i01 + c] if i01 >= 0 else 0
                p11 = sp[i11 + c] if i11 >= 0 else 0
                top = p00 * (1 - wx) + p10 * wx
                bot = p01 * (1 - wx) + p11 * wx
                out[o + c] = int(top * (1 - wy) + bot * wy + 0.5)
    return Image(nw, nh, out)


def _strip(ctx, name: str, edge: str) -> Optional[Tuple[Image, int]]:
    """Baked + edge-rotated foam strip. Returns (rotated_img, raw_h) or None."""
    key = (name, edge)
    cached = _rot_cache.get(key)
    if cached is not None:
        return cached
    base = ctx.bake(name)
    if base is None:
        return None
    if edge in ("E", "W"):
        base = base.flipped_x()
    rot = _rotated(base, _EDGES[edge][0])
    result = (rot, base.h)
    _rot_cache[key] = result
    return result


def items(ctx, x: int, y: int) -> List[Placement]:
    tile = ctx.tile_at(x, y)
    if tile is None or tile.terrain != E.Terrain.WATER or _frozen_water(tile):
        return []

    sl = tile.shorelines
    use_precomputed = bool(sl and sl.any)
    neigh = {
        "N": ctx.tile_at(x, y + 1),
        "S": ctx.tile_at(x, y - 1),
        "E": ctx.tile_at(x + 1, y),
        "W": ctx.tile_at(x - 1, y),
    }

    out: List[Placement] = []
    for d, (_ang, mx, my) in _EDGES.items():
        if use_precomputed:
            edge = getattr(sl, d)
            if not edge.visible:
                continue
            swamp = edge.sprite_ext == "_swamp"
        else:
            n = neigh[d]
            if not _is_land(n):
                continue
            swamp = _is_swamp_neighbour(n)

        name = "shoreline_swamp" if (swamp and ctx.exists("shoreline_swamp")) else "shoreline"
        result = _strip(ctx, name, d)
        if result is None:
            continue
        strip, raw_h = result
        # Shift the strip centre inward (into the water) by half the raw sprite
        # height so the foam crest lands right at the shoreline edge.  Rotation
        # preserves distances, so (sin θ, -cos θ) * raw_h/2 is the exact
        # inward displacement in screen pixels.
        ang = math.radians(_ang)
        half_h = raw_h / 2.0
        shift_x = math.sin(ang) * half_h
        shift_y = -math.cos(ang) * half_h
        odx, ody = _edge_offset(d)
        dx = round(mx + shift_x - strip.w / 2.0 + odx)
        dy = round(my + shift_y - strip.h / 2.0 + _WATER_RECESS + ody)
        out.append(Placement(E.SORT_TRANSPORT, strip, dx, dy))
    return out
