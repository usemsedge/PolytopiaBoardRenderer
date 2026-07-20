"""Isometric projection, depth, and canvas framing (recon/projection_depth.md).

World position from grid (x,y):  posX=(x-y)*0.4811, posY=(x+y)*0.288  (verified
from MapExtensions.ToPosition @0x2CC11AC).  Pixels:  PPU = 256/0.9622 = 266.057,
half-diamond = 128.0 px wide, 76.624 px tall.  Image Y is down so we negate posY.

Anchoring: a sprite's world position lands at its pivot. Tile ground sprites are
256 px wide (= full diamond width) so pivX = 0.5. The vertical pivot is art-defined
(the catalog has no pivot data); ``TILE_PIVOT_Y`` is calibrated so the diamond
surfaces of neighbouring ground tiles tessellate (see scripts/calibrate_pivot.py).
"""
from __future__ import annotations
import math
from typing import Tuple

TILE_WIDTH = 0.9622
TILE_HEIGHT = 0.576
TILE_WIDTH_HALF = 0.4811
TILE_HEIGHT_HALF = 0.288
TILE_VERTICAL_OFFSET = -0.223
DEPTH_INCREASE_PER_ROW = 100

PPU = 256.0 / TILE_WIDTH          # 266.0569...
HALF_W = TILE_WIDTH_HALF * PPU    # 128.0
HALF_H = TILE_HEIGHT_HALF * PPU   # 76.624

# Calibrated vertical pivot fraction (Unity convention: 0=bottom, 1=top) of the
# ground tile sprite — the y where the world anchor lands. Tuned for tessellation.
TILE_PIVOT_Y = 0.5


def world_pos(x: int, y: int) -> Tuple[float, float]:
    return ((x - y) * TILE_WIDTH_HALF, (x + y) * TILE_HEIGHT_HALF)


def tile_pixel(x: int, y: int) -> Tuple[float, float]:
    """Pixel position of a tile's world anchor, before canvas offset. Y-down."""
    return ((x - y) * HALF_W, -(x + y) * HALF_H)


class Frame:
    """Canvas size + origin so the whole map (plus sprite extents) fits."""

    def __init__(self, width: int, height: int, pad: int = 320):
        self.W = width
        self.H = height
        self.pad = pad
        # tile-anchor extents over the grid
        min_px = -(height - 1) * HALF_W
        max_px = (width - 1) * HALF_W
        min_py = -(width - 1 + height - 1) * HALF_H
        max_py = 0.0
        self.canvas_w = int(math.ceil(max_px - min_px)) + 2 * pad
        self.canvas_h = int(math.ceil(max_py - min_py)) + 2 * pad
        self.origin_x = -min_px + pad
        self.origin_y = -min_py + pad

    def anchor(self, x: int, y: int, extra_world_y: float = 0.0) -> Tuple[float, float]:
        """Canvas pixel of the tile (x,y) world anchor (+ optional world-y nudge)."""
        px, py = tile_pixel(x, y)
        py += -extra_world_y * PPU
        return (self.origin_x + px, self.origin_y + py)

    def place(self, x: int, y: int, sw: int, sh: int,
              piv_x: float = 0.5, piv_y: float = TILE_PIVOT_Y,
              extra_world_y: float = 0.0) -> Tuple[int, int]:
        """Top-left paste position for a sprite of size (sw,sh) with given pivot."""
        cx, cy = self.anchor(x, y, extra_world_y)
        left = round(cx - piv_x * sw)
        top = round(cy - (1.0 - piv_y) * sh)
        return (left, top)


def diamond_center_pivot(img):
    """(piv_x, piv_y) normalized pivot at the tile diamond's centre.

    The diamond's left/right vertices lie on the topmost near-max-width opaque row
    (robust to art rising above the surface, e.g. mountain peaks / ice spikes). The
    horizontal centre is the midpoint of that row, NOT the sprite-width centre — so
    sprites whose content is off-centre in their bounding box (asymmetric mountains)
    still seat centred on the tile."""
    w, h, px = img.w, img.h, img.px
    rows = []
    for y in range(h):
        b = y * w * 4
        xs = [x for x in range(w) if px[b + x * 4 + 3] > 40]
        rows.append((xs[0], xs[-1]) if xs else None)
    max_w = max((r[1] - r[0]) for r in rows if r)
    for y, r in enumerate(rows):
        if r and (r[1] - r[0]) >= max_w - 2:
            center_x = (r[0] + r[1]) / 2.0
            center_y = y
            break
    return ((center_x + 0.5) / w, (h - center_y) / h)


def diamond_center_pivot_y(img) -> float:
    """Pivot-Y (from bottom, 0..1) placing the world anchor at the tile diamond's
    vertical centre.  The diamond's left/right vertices lie on its widest opaque
    row, so the centre = the widest row.  This is robust to art that rises above
    the surface (ice spikes, waves) — unlike using the topmost opaque pixel.
    Tessellation holds because every base tile shares the same diamond geometry."""
    w, h, px = img.w, img.h, img.px
    widths = []
    for y in range(h):
        base = y * w * 4
        xs = [x for x in range(w) if px[base + x * 4 + 3] > 40]
        widths.append((xs[-1] - xs[0]) if xs else -1)
    max_w = max(widths)
    # The diamond's left/right vertices sit on the TOPMOST near-max-width row:
    # above it the diamond tapers to its apex; below it the dirt extrusion keeps
    # full width.  This is robust to spikes/waves rising above the surface.
    center_y = h * 0.5
    for y, wd in enumerate(widths):
        if wd >= max_w - 2:
            center_y = y
            break
    return (h - center_y) / h


def row_depth(x: int, y: int, map_height: int) -> int:
    """Engine SortingOrder base: mapHeight - (x+y)*100  (GetDepthForTile @0x2D507A4)."""
    return map_height - (x + y) * DEPTH_INCREASE_PER_ROW


def sort_key(x: int, y: int, layer_offset: int, emission: int = 0,
             row_bias: int = 0) -> tuple:
    """Painter's-algorithm key, ascending sort = back-to-front.

    Engine SortingOrder = mapHeight - (x+y)*100 + offset (GetDepthForTile @0x2D507A4),
    drawn ascending: large (x+y) = back = smallest value = painted first.  So the row
    term must be DESCENDING in (x+y): we negate it.  Back rows paint first (behind),
    front rows (small x+y, bottom of screen) paint last (on top).  Within a tile,
    higher layer_offset draws later (on top); ties keep emission order (stable).

    ``row_bias`` shifts a tile's effective row for sorting only (not position):
    recessed water uses +1 so it sorts a row further back, letting the higher land
    edge at a water/land boundary paint over the seam (the cliff).
    """
    return (-(x + y + row_bias), layer_offset, emission)
