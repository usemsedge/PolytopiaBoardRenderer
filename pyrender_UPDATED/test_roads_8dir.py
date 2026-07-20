"""Render a 3×3 grid: centre tile has roads to all 8 neighbours.

All 9 tiles carry has_road=True so every directional stub fires on the centre.
Output: /tmp/test_roads_8dir.png
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render, gamestate as GS
from enums import Terrain, Tribe

TRIBE  = int(Tribe.IMPERIUS)
OUMAJI = int(Tribe.OUMAJI)
OWNER  = 1

tiles = []
for y in range(3):
    for x in range(3):
        climate = OUMAJI if (x, y) == (1, 1) else TRIBE
        tiles.append(GS.TileData(
            x=x, y=y, terrain=int(Terrain.FIELD), climate=climate,
            owner=OWNER, has_road=True,
        ))

gs = GS.GameState(
    map=GS.MapData(width=3, height=3, tiles=tiles),
    players=[GS.PlayerState(id=OWNER, tribe=TRIBE)],
    current_player_index=99,
)

if __name__ == "__main__":
    out = "/tmp/test_roads_8dir.png"
    img = render.render(gs, pad=40)
    img.save_png(out)
    print(f"rendered -> {out} ({img.w}x{img.h} px)")
