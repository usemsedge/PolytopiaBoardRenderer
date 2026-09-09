"""Procedural city composite — port of CityRenderer.RefreshCity (0x2AA671C).

Plot count is 4 / 9 / 16 from level. House *instances* are
``(8·level²)//5 + 4·level − 1``, drawn from types 1..min(5, level), then
workshop / parks append onto that list and the whole list is walked with
GetNextRandomPlot. Capital is House_7 on plots[0] (not on the walk).
Seeded RNG is ours (engine System.Random is not replayed). Plot spacing is
the calibrated isometric diamond.

``build`` returns a single composite image with houses then walls baked
back-to-front.
"""
from __future__ import annotations

import math
from typing import List, Optional, Tuple

import enums as E
import projection as P
import spritemeta as SM
from context import FEATURE_FOOT, OBJECT_FOOT
from image import Image

# CityRenderer ctor defaults (0x2AA93CC–0x2AA93D4): workshop=6, capital=7, park=8.
# GetHouse maps 6→House_Workshop, 8→House_Park, else House_{n}.
_HOUSE_WORKSHOP = 6
_HOUSE_CAPITAL = 7
_HOUSE_PARK = 8
# Regular pool is only 1..min(5, level). House_6/9 themed art is unused here.

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

# Kind tags for the seating pass.
_KIND_HOUSE = "house"
_KIND_CAPITAL = "capital"
_KIND_EMBASSY = "embassy"


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

    def next_range(self, lo: int, hi: int) -> int:
        """System.Random.Next(min, max): [lo, hi). IL2CPP Next(lo, lo) returns lo."""
        if hi <= lo:
            return lo
        return lo + self.next() % (hi - lo)


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


def _walk_plot(idx, plots, floors, rng, size: Optional[int] = None):
    """Advance GetNextRandomPlot and bump that plot's floor count.

    Returns (new_idx, ux, uy, floor_before_add). ``size`` defaults to len(plots);
    embassy walks pass count-1.
    """
    n = len(plots) if size is None else max(1, min(int(size), len(plots)))
    idx, p = _next_plot(idx, n, rng)
    p %= len(plots)
    ux, uy = plots[p]
    floor = floors[p]
    floors[p] += 1
    return idx, ux, uy, floor


def _house_count(level: int) -> int:
    """(8·level²)//5 + 4·level − 1  (RefreshCity 0x2AA7330 smull /10)."""
    return (8 * level * level) // 5 + 4 * level - 1


def _type_list(level: int, have_workshop: bool, park_count: int, rng: _Rng) -> List[int]:
    """Build the GetHouse type sequence (RefreshCity 0x2AA72A4–0x2AA7510)."""
    unique = list(range(1, min(5, level) + 1)) or [1]
    types: List[int] = []
    for _ in range(_house_count(level)):
        t = unique[rng.next_range(0, len(unique))]
        if types:
            types.insert(rng.next_range(0, len(types) - 1), t)
        else:
            types.insert(0, t)
    if have_workshop:
        types.append(_HOUSE_WORKSHOP)
    for _ in range(park_count):
        types.append(_HOUSE_PARK)
    return types


def _embassy_level(rel) -> int:
    if rel is None:
        return 0
    if isinstance(rel, dict):
        return int(rel.get("embassy_level", 0) or 0)
    return int(getattr(rel, "embassy_level", 0) or 0)


def _embassies_in_capital_of(gs, capital_player_id: int) -> List[int]:
    """PlayerStateExtensions.GetEmbassiesInCapitalOf — other players with an
    embassy in this capital (diplomacy embassy_level > 0)."""
    if gs is None or not capital_player_id:
        return []
    out: List[int] = []
    for p in getattr(gs, "player_states", ()) or ():
        pid = int(getattr(p, "id", 0) or 0)
        if pid == 0 or pid == capital_player_id:
            continue
        rels = getattr(p, "relations", None) or {}
        if _embassy_level(rels.get(capital_player_id) or rels.get(str(capital_player_id))):
            out.append(pid)
    return out


def _wall_sprite(ctx, tile, tribe, skin) -> Optional[str]:
    """Land: CityWallGFX (DoSpriteLookup). Water/ocean: ocean_wall_* / water_wall_*."""
    t = int(getattr(tile, "terrain", 0) or 0)
    if t == int(E.Terrain.OCEAN):
        for cand in ("ocean_wall_left_wall_right", "ocean_wall_left"):
            if ctx.exists(cand):
                return cand
    elif t == int(E.Terrain.WATER):
        for cand in ("water_wall_left_wall_right", "water_wall_left"):
            if ctx.exists(cand):
                return cand
    name, _ = ctx.resolve("CityWallGFX", tribe, skin)
    return name


def _house_sprite(ctx, htype: int, tribe: int, skin: int) -> Optional[str]:
    """CityRenderer.GetHouse: workshop/park literals, else House_{n} + DoSpriteLookup."""
    if htype == _HOUSE_WORKSHOP:
        name, _ = ctx.resolve("House_Workshop", tribe, skin)
        return name or ("House_Workshop" if ctx.exists("House_Workshop") else None)
    if htype == _HOUSE_PARK:
        return "House_Park" if ctx.exists("House_Park") else None
    name, _ = ctx.resolve("House_" + str(htype), tribe, skin)
    return name


# ---------------------------------------------------------------- entry
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
    plots = _diamond_plots(int(round(math.sqrt(count))))
    floors = [0] * len(plots)

    rng = _Rng(_seed_for(tile))
    idx = 0

    # (kind, ux, uy, floor, extra) — extra is GetHouse type or embassy owner id.
    placed: List[Tuple[str, float, float, int, int]] = []

    types = _type_list(
        level,
        st.has_reward(int(E.CityReward.WORKSHOP)),
        st.reward_count(int(E.CityReward.PARK)),
        rng,
    )
    for htype in types:
        idx, ux, uy, floor = _walk_plot(idx, plots, floors, rng, count)
        placed.append((_KIND_HOUSE, ux, uy, floor, htype))

    # Embassies: GetNextRandomPlot with size = count-1 (0x2AA75D0).
    cap_of = int(tile.capital_of or 0)
    if cap_of:
        for eid in _embassies_in_capital_of(getattr(ctx, "gs", None), cap_of):
            idx, ux, uy, floor = _walk_plot(idx, plots, floors, rng, count - 1)
            placed.append((_KIND_EMBASSY, ux, uy, floor, eid))

    # Capital: GetHouse(HOUSE_CAPITAL=7) on plots[0] saved before Reverse (0x2AA70B4).
    if cap_of:
        ux, uy = plots[0]
        floor = floors[0]
        floors[0] += 1
        placed.append((_KIND_CAPITAL, ux, uy, floor, _HOUSE_CAPITAL))

    seated: List[Tuple[Image, int, int]] = []

    def seat_sprite(name: Optional[str], ux: float, uy: float, floor: int):
        if not name:
            return
        img = ctx.bake(name, scale=CITY_OUTPUT_SCALE)
        if img is None:
            return
        dx = ux * PLOT_DX * CITY_OUTPUT_SCALE
        dy = (uy * PLOT_DY - floor * FLOOR_HEIGHT + CITY_Y_LIFT) * CITY_OUTPUT_SCALE
        left, top = ctx.seat_planted(img.w, img.h, foot=HOUSE_FOOT, dx=dx, dy=dy)
        seated.append((img, left, top))

    order = sorted(range(len(placed)), key=lambda i: (placed[i][2], placed[i][3]))
    for i in order:
        kind, ux, uy, floor, extra = placed[i]
        if kind in (_KIND_HOUSE, _KIND_CAPITAL):
            seat_sprite(_house_sprite(ctx, extra, tribe, skin), ux, uy, floor)
        elif kind == _KIND_EMBASSY:
            etribe, eskin = ctx.player_tribe_skin(extra)
            name, _ = ctx.resolve("embassy", etribe, eskin)
            if not name and ctx.exists("embassy"):
                name = "embassy"
            seat_sprite(name, ux, uy, floor)

    if st.has_reward(int(E.CityReward.CITY_WALL)):
        wall = _wall_sprite(ctx, tile, tribe, skin)
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
