"""Procedural city composite — House_* plots + optional CityWallGFX.

Level selects the plot grid size (count = 4/9/16 stacks) and the total house
instances:
  level 1     → 4  stacks (2×2 diamond), house_count = (8·1²)//5 + 4·1 − 1 = 4
  level 2–4   → 9  stacks (3×3 diamond), instances grow with level (some stacking)
  level 5+    → 16 stacks (4×4 diamond), instances grow quadratically

Each stack position receives one or more houses stacked vertically. The walk is
deterministically seeded from tile x,y so the city layout is stable across renders.

``build`` returns a single composite image with houses then walls baked in
back-to-front order (same visual as the old multi-Placement emit).
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import enums as E
import projection as P
import spritemeta as SM
from context import FEATURE_FOOT, OBJECT_FOOT
from image import Image

# House art indices that exist in the atlas (recon §3: 1..7, 9 — no 8).
_HOUSE_NUMS = (1, 2, 3, 4, 5, 6, 7, 9)

# Capital marker: House_7 is the tall gold-crowned "grand" house.
_CAPITAL_HOUSE_PREF = (7, 5, 4, 3, 2, 1)

HOUSE_FOOT = OBJECT_FOOT
# Fixed inter-plot spacing (same for all grid sizes so buildings are always tight).
# Calibrated from the 4×4 grid: 3 steps × PLOT_DX = HALF_W, front foot at HALF_H.
PLOT_DX = P.HALF_W / 5 + 5           # step in the ux (screen-x) axis
PLOT_DY = P.HALF_H / 5 + 2          # = PLOT_DX × HALF_H/HALF_W — correct isometric ratio
# Each stacked floor shifts the house upward by this many pixels (screen space).
FLOOR_HEIGHT = 38
# Shift the entire city cluster upward (negative = up in screen coords).
CITY_Y_LIFT = -P.HALF_H * 0.30
# Uniform post-render scale: expands the entire city cluster (positions + sprites)
# relative to the tile centre. 1.0 = no change, 1.1 = 10% larger.
CITY_OUTPUT_SCALE = 1.1

# Neutral village atlas sprite. Authored at UI PPU (~100); default ctx.bake
# (~2.66×) oversizes it. Effective scale is relative to terrain REF (1.0).
_VILLAGE_SPRITE = "UI_village"
_VILLAGE_EFFECTIVE_SCALE = 0.60


# ---------------------------------------------------------------- deterministic rng
class _Rng:
    """Tiny deterministic LCG seeded from tile coords (stable across renders)."""

    __slots__ = ("s",)

    def __init__(self, seed: int):
        self.s = (seed & 0xFFFFFFFF) or 0x9E3779B9

    def next(self) -> int:
        # Numerical Recipes LCG constants.
        self.s = (1664525 * self.s + 1013904223) & 0xFFFFFFFF
        return self.s

    def value(self) -> float:
        return self.next() / 4294967296.0

    def range(self, n: int) -> int:
        return self.next() % n if n > 0 else 0


def _seed_for(tile) -> int:
    return ((tile.x * 73856093) ^ (tile.y * 19349663) ^ 0x5BD1E995) & 0xFFFFFFFF


# ---------------------------------------------------------------- plot grid
def _diamond_plots(side: int) -> List[Tuple[float, float]]:
    """Return (ux, uy) unit offsets for a side×side isometric diamond grid,
    centred on the origin. side in {2,3,4}. ux = col-row, uy = col+row."""
    plots: List[Tuple[float, float]] = []
    half = (side - 1) / 2.0
    for r in range(side):
        for c in range(side):
            ux = (c - half) - (r - half)
            uy = (c - half) + (r - half)
            plots.append((ux, uy))
    plots.sort(key=lambda p: (p[1], p[0]))
    return plots


def _next_plot(idx: int, size: int, rng: _Rng) -> Tuple[int, int]:
    """GetNextRandomPlot: step by ceil(value*1.5) (1 or 2), wrap to 1 past size."""
    step = int(math.ceil(rng.value() * 1.5)) or 1
    idx += step
    if idx > size:
        idx = 1
    return idx, idx - 1


def build(ctx, tile) -> Optional[Tuple[Image, float, float]]:
    """Composite houses (+ wall) into one image.

    Unowned cities (neutral villages) use the ``UI_village`` sprite instead of
    the tribal house cluster.

    Returns ``(image, origin_x, origin_y)`` where the origin is the tile-local
    diamond centre mapped into the composite, or None if nothing drew.
    """
    st = tile.improvement
    if st is None:
        return None

    # Neutral village — single atlas sprite, not the owned-city house layout.
    if not tile.owner and not tile.capital_of:
        name = _VILLAGE_SPRITE
        if not ctx.exists(name):
            return None
        # Cancel UI PPU inflation, then apply map-tuned effective scale.
        rs = SM.render_scale(name)
        img = ctx.bake(
            name,
            scale=(_VILLAGE_EFFECTIVE_SCALE / rs) if rs else _VILLAGE_EFFECTIVE_SCALE,
        )
        if img is None:
            return None
        # Plant on the tile surface like other buildings (not center-pivot UI).
        left, top = ctx.seat_planted(img.w, img.h, foot=OBJECT_FOOT)
        return img, -left, -top

    # Owned cities use the owner's tribe.
    tribe, skin = ctx.player_tribe_skin(tile.owner)

    level = max(1, st.level)
    count = 4 if level <= 1 else (9 if level < 5 else 16)
    side = int(round(math.sqrt(count)))
    plots = _diamond_plots(side)
    plot_dx = PLOT_DX
    plot_dy = PLOT_DY

    rng = _Rng(_seed_for(tile))

    avail = [n for n in _HOUSE_NUMS if ctx.resolve("House_" + str(n), tribe, skin)[0]]
    if not avail:
        avail = [1]

    cap_house: Optional[int] = None
    if tile.capital_of:
        for n in _CAPITAL_HOUSE_PREF:
            if ctx.resolve("House_" + str(n), tribe, skin)[0]:
                cap_house = n
                break
        if cap_house is not None and len(avail) > 1 and cap_house in avail:
            avail = [n for n in avail if n != cap_house]

    # Total house instances (binary: second loop = (8·level²)//5 + 4·level − 1).
    # First count slots are unique (one per plot); beyond that, houses stack on existing
    # plots, each shifted upward by FLOOR_HEIGHT px relative to the previous floor.
    house_count = (8 * level * level) // 5 + 4 * level - 1
    nplots = len(plots)
    plot_floors: List[int] = [0] * nplots
    free = list(range(nplots))
    idx = rng.range(nplots)

    placements: List[Tuple[float, float, int]] = []
    for _ in range(house_count):
        if free:
            idx, p = _next_plot(idx, nplots, rng)
            p = p % nplots
            if p not in free:
                p = min(free, key=lambda q: (abs(q - p), q))
            free.remove(p)
        else:
            idx, p = _next_plot(idx, nplots, rng)
            p = p % nplots
        floor = plot_floors[p]
        plot_floors[p] += 1
        ux, uy = plots[p]
        placements.append((ux, uy, floor))

    cap_placement: Optional[Tuple[float, float]] = None
    if cap_house is not None:
        idx, _p = _next_plot(idx, nplots, rng)
        cap_placement = (0.0, 0.0)

    # Collect seated sprites as (img, left, top), houses first (back-to-front), then wall.
    seated: List[Tuple[Image, int, int]] = []

    def seat_house(ux: float, uy: float, floor: int, hnum: int):
        name, _ = ctx.resolve("House_" + str(hnum), tribe, skin)
        if not name:
            return
        img = ctx.bake(name, scale=CITY_OUTPUT_SCALE)
        if img is None:
            return
        dx = (ux * plot_dx + 0) * CITY_OUTPUT_SCALE
        dy = (uy * plot_dy - floor * FLOOR_HEIGHT + CITY_Y_LIFT) * CITY_OUTPUT_SCALE
        left, top = ctx.seat_planted(img.w, img.h, foot=HOUSE_FOOT, dx=dx, dy=dy)
        seated.append((img, left, top))

    order = sorted(range(len(placements)), key=lambda i: (placements[i][1], placements[i][2]))
    for i in order:
        ux, uy, floor = placements[i]
        hnum = avail[rng.range(len(avail))]
        seat_house(ux, uy, floor, hnum)

    if cap_placement is not None and cap_house is not None:
        ux, uy = cap_placement
        seat_house(ux, uy, 0, cap_house)

    if st.has_reward(int(E.CityReward.CITY_WALL)):
        wall, _ = ctx.resolve("CityWallGFX", tribe, skin)
        if wall:
            img = ctx.bake(wall)
            if img is not None:
                left, top = ctx.seat_planted(img.w, img.h, foot=FEATURE_FOOT)
                seated.append((img, left, top))

    if not seated:
        return None

    minx = min(left for (_img, left, _top) in seated)
    miny = min(top for (_img, _left, top) in seated)
    maxx = max(left + img.w for (img, left, _top) in seated)
    maxy = max(top + img.h for (img, _left, top) in seated)
    canvas = Image.new(math.ceil(maxx - minx), math.ceil(maxy - miny), (0, 0, 0, 0))
    for img, left, top in seated:
        canvas.paste(img, round(left - minx), round(top - miny))
    return canvas, -minx, -miny
