"""Render a 3-row grid with city levels 1–8 in the middle row, spaced 2 apart.

Layout (17 wide × 3 tall):
  row 0: plain field
  row 1: city level 1 at x=1, level 2 at x=3, ..., level 8 at x=15
  row 2: plain field

Output: /tmp/test_cities.png
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
from enums import Terrain, Improvement, Tribe

TRIBE = int(Tribe.IMPERIUS)
OWNER = 1
WIDTH  = 17   # x 0..16; cities at x=1,3,5,7,9,11,13,15
HEIGHT = 3    # y 0..2;  cities in middle row y=1

# (x, y) -> city level for the 8 cities in the middle row
_NAMES  = ["Odum", "Nobu", "Leva", "Quor", "Sath", "Rimox", "Tyvae", "Elphi"]
_CITIES = {(1 + i * 2, 1): i + 1 for i in range(8)}


def _tile(x, y):
    city_level = _CITIES.get((x, y))
    imp = None
    capital_of = 0
    if city_level is not None:
        idx = list(_CITIES.keys()).index((x, y))
        # Cumulative pop: baseline to reach this level + leftover fill for the bar.
        leftover = (city_level - 1) % (city_level + 1)
        baseline = max(0, city_level * (city_level + 1) // 2 - 1)
        population = baseline + leftover
        if city_level == 1:
            capital_of = OWNER
        imp = GS.ImprovementState(
            type=int(Improvement.CITY), level=city_level,
            name=_NAMES[idx], population=population, xp=leftover,
        )
    return GS.TileData(
        coordinates=GS.WorldCoordinates(x, y),
        terrain=int(Terrain.FIELD),
        climate=TRIBE,
        owner=OWNER if city_level is not None else 0,
        capital_of=capital_of,
        improvement=imp,
    )


def build_gamestate() -> GS.GameState:
    tiles = [_tile(x, y) for y in range(HEIGHT) for x in range(WIDTH)]
    mapdata = GS.MapData(width=WIDTH, height=HEIGHT, tiles=tiles)
    players = [GS.PlayerState(id=OWNER, tribe=TRIBE)]
    # current_player_index out of range → viewer=None → all tiles visible
    return GS.GameState(map=mapdata, player_states=players, current_player_index=99)


if __name__ == "__main__":
    out = "/tmp/test_cities.png"
    gs = build_gamestate()
    img = render.render(gs, pad=60)
    img.save_png(out)
    print(f"rendered {WIDTH}x{HEIGHT} board -> {out} ({img.w}x{img.h})")
