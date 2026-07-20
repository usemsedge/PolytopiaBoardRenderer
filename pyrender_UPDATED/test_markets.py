"""Render markets at levels 0–8 in a single row.

Each column is a 3×3 cluster: market in the centre, surrounded by N feeder
buildings (Windmill/Sawmill/Forge, same owner) to produce the target level.
Feeder types cycle: Windmill (→FarmersMarket deco) for the first 3 slots,
Sawmill (→WoodMarket) for the next 3, Forge (→MetalMarket) for the last 2, so
higher-level markets progressively show all three floor decorations.

Columns: x = 2, 5, 8, 11, 14, 17, 20, 23, 26  (market at y=2, feeders at y=1-3)
Output: /tmp/test_markets.png
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
from enums import Terrain, Tribe, Improvement

TRIBE = int(Tribe.IMPERIUS)
OWNER = 1
MARKET_Y = 2
HEIGHT   = 5
SPACING  = 3          # tiles between market centres
N_LEVELS = 9          # 0..8
WIDTH    = SPACING * (N_LEVELS - 1) + SPACING  # market centres at x=2,5,8,...26, map 0..28
MARKET_XS = [SPACING - 1 + i * SPACING for i in range(N_LEVELS)]  # [2,5,8,...,26]

# Eight neighbour offsets in feeder-priority order.
_NEIGHBORS = [(-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1)]

# Feeder type per slot index (cycles Windmill×3, Sawmill×3, Forge×2).
_FEEDER_TYPES = (
    [int(Improvement.WINDMILL)] * 3 +
    [int(Improvement.SAWMILL)]  * 3 +
    [int(Improvement.FORGE)]    * 2
)


def _build_tiles():
    tiles = {}

    for col, mx in enumerate(MARKET_XS):
        level = col   # level 0..8
        my = MARKET_Y

        # Market tile
        tiles[(mx, my)] = GS.TileData(
            x=mx, y=my,
            terrain=int(Terrain.FIELD),
            climate=TRIBE,
            owner=OWNER,
            improvement=GS.ImprovementState(type=int(Improvement.MARKET)),
        )

        # Place `level` feeders in neighbour slots
        for slot in range(level):
            dx, dy = _NEIGHBORS[slot]
            nx, ny = mx + dx, my + dy
            tiles[(nx, ny)] = GS.TileData(
                x=nx, y=ny,
                terrain=int(Terrain.FIELD),
                climate=TRIBE,
                owner=OWNER,
                improvement=GS.ImprovementState(type=_FEEDER_TYPES[slot], level=1),
            )

    # Fill remaining tiles with plain field
    result = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if (x, y) in tiles:
                result.append(tiles[(x, y)])
            else:
                result.append(GS.TileData(
                    x=x, y=y,
                    terrain=int(Terrain.FIELD),
                    climate=TRIBE,
                ))
    return result


def build_gamestate():
    tiles = _build_tiles()
    mapdata = GS.MapData(width=WIDTH, height=HEIGHT, tiles=tiles)
    players = [GS.PlayerState(id=OWNER, tribe=TRIBE)]
    return GS.GameState(map=mapdata, players=players, current_player_index=99)


if __name__ == "__main__":
    out = "/tmp/test_markets.png"
    gs = build_gamestate()
    img = render.render(gs, pad=40)
    img.save_png(out)
    print(f"rendered {WIDTH}x{HEIGHT} board -> {out} ({img.w}x{img.h} px)")
    print()
    print("Market levels (left→right):")
    for i, mx in enumerate(MARKET_XS):
        feeders = _FEEDER_TYPES[:i]
        types = []
        if feeders.count(int(Improvement.WINDMILL)): types.append(f"Windmill×{feeders.count(int(Improvement.WINDMILL))}")
        if feeders.count(int(Improvement.SAWMILL)):  types.append(f"Sawmill×{feeders.count(int(Improvement.SAWMILL))}")
        if feeders.count(int(Improvement.FORGE)):    types.append(f"Forge×{feeders.count(int(Improvement.FORGE))}")
        print(f"  level {i}: {', '.join(types) or 'no feeders'}")
