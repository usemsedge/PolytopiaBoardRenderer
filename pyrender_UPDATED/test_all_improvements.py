"""8×8 catalog: one tile per Improvement enum value (row-major order).

Layout: improvement i at (i % 8, i // 8). Values 0..55 fill the first 56 cells;
the last 8 tiles are plain field.

Terrain is picked to suit each type (water / forest / mountain / ice / field).
CITY is a small capital so houses + status UI appear. ROAD uses has_road so
segments can connect to neighbouring connectable tiles when present.

Output: /tmp/test_all_improvements.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
from enums import Terrain, Tribe, Improvement, CityReward

TRIBE = int(Tribe.IMPERIUS)
OWNER = 1
WIDTH = 8
HEIGHT = 8

_WATER = frozenset({
    Improvement.FISHING, Improvement.PORT, Improvement.WHALE_HUNTING,
    Improvement.WATER_TEMPLE, Improvement.BRIDGE, Improvement.STAR_FISHING,
    Improvement.LIGHTHOUSE, Improvement.AQUAFARM, Improvement.ATOLL,
    Improvement.CANAL, Improvement.ALGAE, Improvement.ALGAE_SPAWN,
})
_FOREST = frozenset({
    Improvement.HUNTING, Improvement.CLEAR_FOREST, Improvement.BURN_FOREST,
    Improvement.LUMBER_HUT, Improvement.GROW_FOREST, Improvement.FOREST_TEMPLE,
    Improvement.FUNGI, Improvement.MYCELIUM, Improvement.BURN_SPORES,
    Improvement.CLATHRUS, Improvement.HARVEST_SPORES,
})
_MOUNTAIN = frozenset({
    Improvement.MOUNTAIN_TEMPLE, Improvement.MINE,
})
_ICE = frozenset({
    Improvement.OUTPOST, Improvement.ICE_BANK, Improvement.ICE_TEMPLE,
    Improvement.POLARIS_CLIMATE,
})


def _terrain_for(imp: Improvement) -> int:
    if imp in _WATER:
        return int(Terrain.WATER)
    if imp in _FOREST:
        return int(Terrain.FOREST)
    if imp in _MOUNTAIN:
        return int(Terrain.MOUNTAIN)
    if imp in _ICE:
        return int(Terrain.ICE)
    return int(Terrain.FIELD)


def _improvement_state(imp: Improvement) -> GS.ImprovementState | None:
    if imp == Improvement.NONE:
        return None
    if imp == Improvement.CITY:
        return GS.ImprovementState(
            type=int(imp),
            level=3,
            name="City",
            population=1,
            production=2,
            rewards=[int(CityReward.CITY_WALL)],
        )
    # Leveled families look better at level 1+; monuments ignore level.
    return GS.ImprovementState(type=int(imp), level=1)


def _tile(x: int, y: int) -> GS.TileData:
    idx = y * WIDTH + x
    imps = list(Improvement)
    if idx < len(imps):
        imp = imps[idx]
    else:
        imp = Improvement.NONE

    st = _improvement_state(imp)
    capital_of = OWNER if imp == Improvement.CITY else 0
    owner = OWNER if st is not None else 0
    has_road = imp == Improvement.ROAD
    # Bridge / port tiles are connectable; also mark ROAD so a lone road still
    # has a chance to show a stub toward city/port/bridge neighbours.
    if imp == Improvement.LIGHTHOUSE and st is not None:
        st.discovered_by = [1, 2, 3]
    return GS.TileData(
        coordinates=GS.WorldCoordinates(x, y),
        terrain=_terrain_for(imp),
        climate=TRIBE,
        owner=owner,
        capital_of=capital_of,
        has_road=has_road,
        improvement=st,
    )


def build_gamestate() -> GS.GameState:
    tiles = [_tile(x, y) for y in range(HEIGHT) for x in range(WIDTH)]
    mapdata = GS.MapData(width=WIDTH, height=HEIGHT, tiles=tiles)
    players = [
        GS.PlayerState(id=1, tribe=TRIBE),
        GS.PlayerState(id=2, tribe=int(Tribe.BARDUR)),
        GS.PlayerState(id=3, tribe=int(Tribe.XINXI)),
    ]
    return GS.GameState(map=mapdata, player_states=players, current_player_index=99)


def _print_legend() -> None:
    imps = list(Improvement)
    print(f"{'y\\\\x':>14}", end="")
    for x in range(WIDTH):
        print(f"  {x:^14}", end="")
    print()
    for y in range(HEIGHT):
        print(f"{y:14}", end="")
        for x in range(WIDTH):
            idx = y * WIDTH + x
            label = imps[idx].name if idx < len(imps) else "(empty)"
            print(f"  {label:^14}", end="")
        print()


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/test_all_improvements.png"
    gs = build_gamestate()
    img = render.render(gs, pad=80)
    img.save_png(out)
    print(f"rendered {WIDTH}x{HEIGHT} board -> {out} ({img.w}x{img.h} px)")
    print(f"{len(Improvement)} Improvement values (0..{len(Improvement) - 1}); "
          f"{WIDTH * HEIGHT - len(Improvement)} filler tiles")
    print()
    _print_legend()
