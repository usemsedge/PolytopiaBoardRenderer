"""Parse compact map notation into a GameState.

Notation format — lines separated by ';', all whitespace ignored:
  line 1: city_count
  line 2: capture + border-growth sequence (comma-separated city ids)
  line 3: height,width
  line 4: height×width tile codes, row-major (top-left first)

Tile code — exactly 6 ASCII digits TTRRIIIII:
  TT  terrain     (Terrain enum value, zero-padded)
  RR  resource    (Resource enum value, zero-padded)
  II  improvement (Improvement enum value, zero-padded)

City id rules:
  • City ids are NOT supplied by the user. They are inferred automatically from
    the tile grid in English reading order (row-major, left-to-right top-to-bottom),
    numbered 1..city_count.
  • Every city id must appear at least once and at most twice in line 2; any id
    missing or appearing three or more times is a parse error.
  • First occurrence of an id  → the city was captured at that point in the sequence.
    Capture order determines territory priority when cities overlap (earlier = wins).
  • Second occurrence of an id → the city underwent border growth after capture.
    Cities with border growth: level 5, Chebyshev radius 2 (5×5 territory).
    Cities without border growth: level 3, Chebyshev radius 1 (3×3 territory).
  • The first unique id in line 2 is the capital of player 1.
  • All other player-1 cities get connected_to_capital_of=1.

Other inferences:
  • Player 1 owns every tile inside any city's territory.
  • Climate defaults to Imperius; all tiles visible to player 1 (explorers=[1]).

Example — 3×3 grid, 1 city captured with border growth (appears twice), 3 farms,
          1 windmill, 1 market:
  1;
  1;
  3,3;
  030000,030000,030000,030205,030001,030205,030205,030006,030050;
"""
from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gamestate as GS
from enums import Improvement, Tribe


# City level and Chebyshev territory radius.
_LEVEL_GROWTH  = 5   # city in capture-order list
_LEVEL_NORMAL  = 3   # city not in list
_RADIUS_GROWTH = 2   # 5×5
_RADIUS_NORMAL = 1   # 3×3


def _city_level(cid: int, growth_ids: set[int]) -> int:
    return _LEVEL_GROWTH if cid in growth_ids else _LEVEL_NORMAL


def _city_radius(cid: int, growth_ids: set[int]) -> int:
    return _RADIUS_GROWTH if cid in growth_ids else _RADIUS_NORMAL


def _compute_territory(
    city_order: list[int],          # all city ids in priority order
    city_pos: dict[int, tuple],     # cid → (x, y)
    growth_ids: set[int],
    h: int, w: int,
) -> dict[tuple, int]:
    """Return {(x,y): owning_city_id} for all tiles claimed by any city.

    City priority is determined by position in city_order (earlier = higher).
    Within territories that share no ordering, lower city id wins.
    """
    # Build full priority list: ordered ids first, then remaining by id
    seen = set(city_order)
    full_order = city_order + sorted(c for c in city_pos if c not in seen)

    owned: dict[tuple, int] = {}
    for cid in full_order:
        cx, cy = city_pos[cid]
        r = _city_radius(cid, growth_ids)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                tx, ty = cx + dx, cy + dy
                if 0 <= tx < w and 0 <= ty < h and (tx, ty) not in owned:
                    owned[(tx, ty)] = cid
    return owned


# Building → what it counts in its 8 neighbours to determine its own level.
# Each entry is a set of Improvement type ints that feed this building.
_FEEDER_TYPES: dict[int, set[int]] = {
    int(Improvement.WINDMILL): {int(Improvement.FARM)},
    int(Improvement.SAWMILL):  {int(Improvement.LUMBER_HUT)},
    int(Improvement.FORGE):    {int(Improvement.MINE)},
}
# Market sums the *levels* of adjacent income buildings.
_MARKET_INPUTS: set[int] = {
    int(Improvement.WINDMILL),
    int(Improvement.SAWMILL),
    int(Improvement.FORGE),
}
_MARKET_MAX = 8


def _resolve_building_levels(tiles: list, w: int, h: int) -> None:
    """Two-pass in-place level resolution after all tiles are created.

    Pass 1 — windmills, sawmills, forges:
        level = number of 8-directional neighbours with a matching feeder building.
    Pass 2 — markets:
        level = sum of 8-directional neighbour levels for windmills/sawmills/forges,
        capped at _MARKET_MAX.
    """
    by_pos = {(t.x, t.y): t for t in tiles}

    def nbrs(x, y):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = by_pos.get((x + dx, y + dy))
                if nb is not None:
                    yield nb

    # Pass 1
    for t in tiles:
        if t.improvement is None:
            continue
        feeders = _FEEDER_TYPES.get(t.improvement.type)
        if feeders is None:
            continue
        t.improvement.level = sum(
            1 for nb in nbrs(t.x, t.y)
            if nb.improvement and nb.improvement.type in feeders
        )

    # Pass 2 — markets use the levels set in pass 1
    for t in tiles:
        if t.improvement is None or t.improvement.type != int(Improvement.MARKET):
            continue
        t.improvement.level = min(
            _MARKET_MAX,
            sum(
                nb.improvement.level
                for nb in nbrs(t.x, t.y)
                if nb.improvement and nb.improvement.type in _MARKET_INPUTS
            ),
        )


def parse(text: str) -> GS.GameState:
    """Parse compact notation string and return a GameState."""
    clean = "".join(text.split())
    parts = [p for p in clean.split(";") if p]

    city_count = int(parts[0])
    h, w       = [int(x) for x in parts[2].split(",")]
    codes      = parts[3].split(",")

    if len(codes) != h * w:
        raise ValueError(f"Expected {h*w} tile codes, got {len(codes)}")

    # --- parse line 2: first occurrence = capture, second = border growth ---
    raw = [int(x) for x in parts[1].split(",")] if parts[1] else []
    capture_order: list[int] = []
    growth_ids: set[int] = set()
    seen: dict[int, int] = {}
    for cid in raw:
        seen[cid] = seen.get(cid, 0) + 1
        if seen[cid] == 1:
            capture_order.append(cid)
        elif seen[cid] == 2:
            growth_ids.add(cid)
        else:
            raise ValueError(f"City id {cid} appears more than twice in line 2")
    missing = set(range(1, city_count + 1)) - set(seen)
    if missing:
        raise ValueError(f"City ids missing from line 2: {sorted(missing)}")

    # --- locate cities (row-major scan, ids 1..city_count) ---
    city_pos: dict[int, tuple] = {}   # cid → (x, y)
    cid = 1
    for y in range(h):
        for x in range(w):
            if int(codes[y * w + x][4:6]) == int(Improvement.CITY):
                city_pos[cid] = (x, y)
                cid += 1

    capital_id   = capture_order[0] if capture_order else (min(city_pos) if city_pos else 1)
    capital_pos  = city_pos.get(capital_id)
    pos_to_cid   = {pos: cid for cid, pos in city_pos.items()}  # (x,y) → city id

    # --- compute territory ownership ---
    territory = _compute_territory(capture_order, city_pos, growth_ids, h, w)
    # reverse lookup: (x,y) → (ruling_cx, ruling_cy)
    ruling: dict[tuple, tuple] = {
        pos: city_pos[cid] for pos, cid in territory.items()
    }

    # --- build tiles ---
    tiles: list[GS.TileData] = []
    for y in range(h):
        for x in range(w):
            code    = codes[y * w + x]
            terrain = int(code[0:2])
            res     = int(code[2:4])
            imp     = int(code[4:6])

            # Determine ownership from territory map
            owner       = 1 if (x, y) in territory else 0
            rcx, rcy    = ruling.get((x, y), (-1, -1))

            improvement = None
            if imp != 0:
                is_city    = (imp == int(Improvement.CITY))
                this_cid   = pos_to_cid.get((x, y))  # None for non-city tiles
                is_capital = (this_cid == capital_id)

                level = 1
                border_size = 0
                if is_city and this_cid is not None:
                    level       = _city_level(this_cid, growth_ids)
                    border_size = _city_radius(this_cid, growth_ids)

                improvement = GS.ImprovementState(
                    type=imp,
                    level=level,
                    border_size=border_size,
                    founder=1,
                    is_capital_of=1 if is_capital else 0,
                    connected_to_capital_of=(
                        1 if is_city and not is_capital else 0
                    ),
                )

            resource = GS.ResourceState(type=res) if res != 0 else None

            tiles.append(GS.TileData(
                x=x, y=y,
                terrain=terrain,
                climate=int(Tribe.IMPERIUS),
                owner=owner,
                capital_of=1 if (x, y) == capital_pos else 0,
                ruling_city_x=rcx,
                ruling_city_y=rcy,
                improvement=improvement,
                resource=resource,
                explorers=[1],
            ))

    _resolve_building_levels(tiles, w, h)

    mapdata = GS.MapData(width=w, height=h, tiles=tiles)
    players = [GS.PlayerState(id=1, tribe=int(Tribe.IMPERIUS))]
    return GS.GameState(map=mapdata, players=players, current_player_index=0)


def from_file(path: str) -> GS.GameState:
    with open(path) as f:
        return parse(f.read())


if __name__ == "__main__":
    import render

    EXAMPLE = """
    1;
    1;
    3,3;
    030000,030000,030000,030205,030001,030205,030205,030006,030050;
    """

    out = "/tmp/mapparse_example.png"
    gs  = parse(EXAMPLE)
    img = render.render(gs, pad=60)
    img.save_png(out)
    print(f"rendered {gs.map.width}x{gs.map.height} -> {out} ({img.w}x{img.h})")
    _SHOW = {
        int(Improvement.CITY):     "city",
        int(Improvement.WINDMILL): "windmill",
        int(Improvement.SAWMILL):  "sawmill",
        int(Improvement.FORGE):    "forge",
        int(Improvement.MARKET):   "market",
    }
    for t in gs.map.tiles:
        if t.improvement is None or t.improvement.type not in _SHOW:
            continue
        name = _SHOW[t.improvement.type]
        lv   = t.improvement.level
        extra = f" r={t.improvement.border_size}" if name == "city" else ""
        print(f"  ({t.x},{t.y}) {name} lv={lv}{extra}")
