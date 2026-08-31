"""Territory borders component (tile-local port of layer_borders.py).

For an owned, non-hidden tile we emit up to four diamond-edge border sprites,
one per orthogonal grid neighbour (N/S/E/W) whose owner differs (or is off-map).

Two white diagonal art sprites cover the four edges:
  - N (upper-left screen edge)  and S (lower-right edge) use ``BorderXGFX``.
  - E (upper-right screen edge) and W (lower-left edge) use ``BorderYGFX``.

Depth: N & E -> SORT_BORDERS_BACK (0); S & W -> SORT_BORDERS_FRONT (99).
Tint: player_color(owner); E & W edges have RGB darkened by SIDE_DARKEN.
Unowned / hidden / no-colour tiles draw nothing.

Tile-local placement: the diamond centre is the origin (0, 0). The source layer
centred the 128x102 sprite on the world anchor then nudged by per-edge
(edge_dx, edge_dy) and subtracted (_SW/2, _SH/2). Here the anchor is (0, 0), so
the local top-left of the BAKED image (w, h) is
    (round(edge_dx - w / 2), round(edge_dy - h / 2))
using the same per-edge nudges the source used.
"""
from __future__ import annotations

from typing import List

import context
import enums as E
import projection as P
from context import Placement
from image import Image

# Darken multiplier applied to the E & W (y-axis art) edges' RGB (recon: 128/255).
SIDE_DARKEN = 128.0 / 255.0

HALF_W = P.HALF_W   # 128.0  (half diamond width)
HALF_H = P.HALF_H   # 76.624 (half diamond height)

# Outward push fraction applied to the back-layer N/E edges toward their neighbour
# so the stripe clears this tile's own terrain.
BACK_OUTWARD = 0.15


# Global vertical shift applied to all four edges.
BORDER_Y_SHIFT = -10

# Per-edge nudge knobs (dx, dy) added on top of BORDER_Y_SHIFT.
# N = upper-left back edge, E = upper-right back edge,
# S = lower-right front edge, W = lower-left front edge.
N_DX, N_DY = 9, 4
E_DX, E_DY = -8, 8
S_DX, S_DY = 0, 0
W_DX, W_DY = 0, 0


def items(ctx, x: int, y: int) -> List[Placement]:
    tile = ctx.tile_at(x, y)
    if tile is None:
        return []
    if tile.owner == 0:
        return []
    if ctx.is_hidden(tile):
        return []

    tint = ctx.player_color(tile.owner)
    if tint is None:
        return []
    r, g, b = tint
    dark = (round(r * SIDE_DARKEN), round(g * SIDE_DARKEN), round(b * SIDE_DARKEN))

    me = tile.owner
    out: List[Placement] = []

    def differs(nx, ny):
        n = ctx.tile_at(nx, ny)
        return n is None or n.owner != me

    # Outward push (px) applied to the back-layer N/E edges toward their neighbour.
    push_x = BACK_OUTWARD * HALF_W / 2
    push_y = BACK_OUTWARD * HALF_H / 2

    _knobs = {"N": (N_DX, N_DY), "E": (E_DX, E_DY),
              "S": (S_DX, S_DY), "W": (W_DX, W_DY)}

    def emit(sublayer, name, tint_rgb, edge_dx, edge_dy, edge):
        img = ctx.bake(name, tint=tint_rgb)
        if img is None:
            return
        kdx, kdy = _knobs[edge]
        dx = round(edge_dx - img.w / 2.0) + kdx
        dy = round(edge_dy - img.h / 2.0) + BORDER_Y_SHIFT + kdy
        out.append(Placement(sublayer, img, dx, dy))

    # N: upper-left edge, neighbour (x, y+1). BorderXGFX. back. full colour.
    if differs(x, y + 1):
        emit(E.SORT_BORDERS_BACK, "BorderXGFX", tint,
             -HALF_W / 2 - push_x, -HALF_H / 2 - push_y, "N")

    # E: upper-right edge, neighbour (x+1, y). BorderYGFX. back. darkened.
    if differs(x + 1, y):
        emit(E.SORT_BORDERS_BACK, "BorderYGFX", dark,
             +HALF_W / 2 + push_x, -HALF_H / 2 - push_y, "E")

    # S: lower-right edge, neighbour (x, y-1). BorderXGFX. front. full colour.
    if differs(x, y - 1):
        emit(E.SORT_BORDERS_FRONT, "BorderXGFX", tint,
             +HALF_W / 2, +HALF_H / 2, "S")

    # W: lower-left edge, neighbour (x-1, y). BorderYGFX. front. darkened.
    if differs(x - 1, y):
        emit(E.SORT_BORDERS_FRONT, "BorderYGFX", dark,
             -HALF_W / 2, +HALF_H / 2, "W")

    return out
