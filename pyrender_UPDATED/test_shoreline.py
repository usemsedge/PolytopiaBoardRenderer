"""Render a single water tile with land on all four sides to show all shoreline edges.

Only the centre water tile is rendered; the surrounding land tiles exist in the
map so the shoreline code detects land neighbours but are not painted.

Output: /tmp/test_shoreline.png
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
import projection as P
import create_tile
import context as CTX
from image import Image
from enums import Terrain, Tribe

TRIBE = int(Tribe.IMPERIUS)

def _tile(x, y):
    is_water = (x == 1 and y == 1)
    return GS.TileData(
        coordinates=GS.WorldCoordinates(x, y),
        terrain=int(Terrain.WATER if is_water else Terrain.FIELD),
        climate=TRIBE,
    )

if __name__ == "__main__":
    tiles = [_tile(x, y) for y in range(3) for x in range(3)]
    gs = GS.GameState(
        map=GS.MapData(width=3, height=3, tiles=tiles),
        player_states=[],
        current_player_index=99,
    )
    ctx = CTX.TileContext(gs)

    # Render only the centre water tile (x=1, y=1)
    timg, ox, oy = create_tile.items(ctx, 1, 1)

    PAD = 40
    canvas = Image.new(timg.w + PAD * 2, timg.h + PAD * 2, (0, 0, 0, 0))
    canvas.paste(timg, PAD, PAD)

    canvas.save_png("/tmp/test_shoreline.png")
    print(f"rendered -> /tmp/test_shoreline.png ({canvas.w}x{canvas.h})")
