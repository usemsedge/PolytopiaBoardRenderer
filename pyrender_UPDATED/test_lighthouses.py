"""Render lighthouses with 0–8 discovering tribes — water row + land copy.

Checkerboard ground:
  water band  ocean ↔ shallow WATER
  land band   Imperius field ↔ Luxidoor mercenary field

Two lighthouse rows (same discoverer counts left→right):
  y=WATER_Y  towers on water checkerboard
  y=LAND_Y   identical towers on land checkerboard

Discoverers come from improvement.discovered_by (not tile.explorers / fog).

Output: /tmp/test_lighthouses.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
from enums import Terrain, Tribe, Skin, Improvement

N_LEVELS = 9          # 0..8 discoverers
SPACING = 2           # tiles between lighthouse centres
WIDTH = SPACING * (N_LEVELS - 1) + SPACING   # centres at x=1,3,5,...
LH_XS = [SPACING - 1 + i * SPACING for i in range(N_LEVELS)]
WATER_Y = 1
LAND_Y = 3
HEIGHT = 5

# Distinct tribes so each stacked drum is a different colour.
_TRIBES = (
    Tribe.IMPERIUS, Tribe.BARDUR, Tribe.XINXI, Tribe.KICKOO,
    Tribe.OUMAJI, Tribe.VENGIR, Tribe.ZEBASI, Tribe.POLARIS,
)


def _tile_theme(x: int, y: int, on_land: bool) -> tuple[int, int, int]:
    """(terrain, climate, skin) for checkerboard cell."""
    a = (x + y) & 1
    if on_land:
        if a == 0:
            return int(Terrain.FIELD), int(Tribe.IMPERIUS), int(Skin.DEFAULT)
        return int(Terrain.FIELD), int(Tribe.LUXIDOOR), int(Skin.MERCENARY)
    # Water band: ocean ↔ shallow.
    if a == 0:
        return int(Terrain.OCEAN), int(Tribe.IMPERIUS), int(Skin.DEFAULT)
    return int(Terrain.WATER), int(Tribe.IMPERIUS), int(Skin.DEFAULT)


def build_gamestate() -> GS.GameState:
    players = [
        GS.PlayerState(id=i + 1, tribe=int(_TRIBES[i]))
        for i in range(len(_TRIBES))
    ]
    tiles = []
    lh_at = {LH_XS[i]: i for i in range(N_LEVELS)}  # x -> discoverer count
    for y in range(HEIGHT):
        on_land = y >= LAND_Y
        for x in range(WIDTH):
            terrain, climate, skin = _tile_theme(x, y, on_land)
            n = lh_at.get(x) if y in (WATER_Y, LAND_Y) else None
            if n is None:
                tiles.append(GS.TileData(
                    coordinates=GS.WorldCoordinates(x, y),
                    terrain=terrain,
                    climate=climate,
                    skin=skin,
                ))
                continue
            tiles.append(GS.TileData(
                coordinates=GS.WorldCoordinates(x, y),
                terrain=terrain,
                climate=climate,
                skin=skin,
                explorers=[p.id for p in players],  # revealed (no fog)
                improvement=GS.ImprovementState(
                    type=int(Improvement.LIGHTHOUSE),
                    discovered_by=[p.id for p in players[:n]],
                ),
            ))
    return GS.GameState(
        map=GS.MapData(width=WIDTH, height=HEIGHT, tiles=tiles),
        player_states=players,
        current_player_index=99,
    )


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_lighthouses.png"
    gs = build_gamestate()
    img = render.render(gs, pad=80)
    img.save_png(out)
    print(f"rendered {WIDTH}x{HEIGHT} board -> {out} ({img.w}x{img.h} px)")
    print(
        f"Rows: water y={WATER_Y} (ocean/shallow checker), "
        f"land y={LAND_Y} (imperius/luxidoor-mercenary); "
        f"discoverers left→right: 0 .. 8"
    )
    print("Tribes:", ", ".join(t.name for t in _TRIBES))
