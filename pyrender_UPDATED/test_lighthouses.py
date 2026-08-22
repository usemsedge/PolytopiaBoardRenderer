"""Render lighthouses with 0–8 discovering tribes in a single row.

Each column is one water tile with a LightHouse. Discoverers come from
tile.explorers (the unique-improvement list is left empty so each column can
show a different height). The tower grows one team-tinted drum per discoverer,
plus the lantern roof (no untinted base layer).

Output: /tmp/test_lighthouses.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
from enums import Terrain, Tribe, Improvement

N_LEVELS = 9          # 0..8 discoverers
SPACING = 2           # tiles between lighthouse centres
HEIGHT = 3
WIDTH = SPACING * (N_LEVELS - 1) + SPACING   # centres at x=1,3,5,...
LH_XS = [SPACING - 1 + i * SPACING for i in range(N_LEVELS)]
LH_Y = 1

# Distinct tribes so each stacked drum is a different colour.
_TRIBES = (
    Tribe.IMPERIUS, Tribe.BARDUR, Tribe.XINXI, Tribe.KICKOO,
    Tribe.OUMAJI, Tribe.VENGIR, Tribe.ZEBASI, Tribe.POLARIS,
)


def build_gamestate() -> GS.GameState:
    players = [
        GS.PlayerState(id=i + 1, tribe=int(_TRIBES[i]))
        for i in range(len(_TRIBES))
    ]
    tiles = []
    lh_at = {LH_XS[i]: i for i in range(N_LEVELS)}  # x -> discoverer count
    for y in range(HEIGHT):
        for x in range(WIDTH):
            n = lh_at.get(x) if y == LH_Y else None
            if n is None:
                tiles.append(GS.TileData(
                    coordinates=GS.WorldCoordinates(x, y),
                    terrain=int(Terrain.WATER),
                    climate=int(Tribe.IMPERIUS),
                ))
                continue
            tiles.append(GS.TileData(
                coordinates=GS.WorldCoordinates(x, y),
                terrain=int(Terrain.WATER),
                climate=int(Tribe.IMPERIUS),
                improvement=GS.ImprovementState(type=int(Improvement.LIGHTHOUSE)),
                explorers=[p.id for p in players[:n]],
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
    print("Discoverers left→right: 0 .. 8")
    print("Tribes:", ", ".join(t.name for t in _TRIBES))
