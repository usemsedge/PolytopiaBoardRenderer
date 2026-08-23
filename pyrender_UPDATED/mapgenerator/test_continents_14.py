"""14×14 Continents map with 2 players — generate and render.

Usage:
  cd pyrender_UPDATED
  python3 -m mapgenerator.test_continents_14
  python3 -m mapgenerator.test_continents_14 /tmp/out.png

Default output: mapgenerator/test_continents_14.png
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import render
from enums import MapPreset, MapSize, Terrain, Tribe
from gamestate import GameSettings, GameState, PlayerState
from mapgenerator import MapGenerator, MapGeneratorSettings

SEED = 42
WIDTH = 14  # MapSize.SMALL


def build_gamestate(seed: int = SEED) -> GameState:
    state = GameState(
        version=1,
        seed=seed,
        settings=GameSettings(
            map_size=int(MapSize.SMALL),
            map_preset=int(MapPreset.CONTINENTS),
        ),
        player_states=[
            PlayerState(
                id=1,
                tribe=int(Tribe.IMPERIUS),
                climate=int(Tribe.IMPERIUS),
                has_chosen_tribe=True,
            ),
            PlayerState(
                id=2,
                tribe=int(Tribe.BARDUR),
                climate=int(Tribe.BARDUR),
                has_chosen_tribe=True,
            ),
        ],
    )
    settings = MapGeneratorSettings.CreateFromPreset(int(MapPreset.CONTINENTS))
    MapGenerator().GenerateWithSeed(seed, state, settings, None)
    return state


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = argv[0] if argv else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "test_continents_14.png"
    )

    state = build_gamestate()
    assert state.map is not None
    assert state.map.width == WIDTH and state.map.height == WIDTH
    assert len(state.map.tiles) == WIDTH * WIDTH

    capitals = [t for t in state.map.tiles if t.capital_of]
    assert len(capitals) == 2, f"expected 2 capitals, got {len(capitals)}"

    land = sum(
        1
        for t in state.map.tiles
        if t.terrain
        in (
            int(Terrain.FIELD),
            int(Terrain.FOREST),
            int(Terrain.MOUNTAIN),
            int(Terrain.ICE),
            int(Terrain.WETLAND),
        )
    )
    assert land > 0, "expected some land tiles"

    img = render.render(state, pad=80)
    img.save_png(out)
    print(
        f"rendered continents {WIDTH}x{WIDTH} seed={SEED} "
        f"players=2 land={land} capitals={len(capitals)} "
        f"-> {out} ({img.w}x{img.h} px)"
    )


if __name__ == "__main__":
    main()
