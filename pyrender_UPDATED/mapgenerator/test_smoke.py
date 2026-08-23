"""Smoke test: GenerateWithSeed on a minimal GameState."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enums import MapPreset, MapSize, Terrain, Tribe
from gamestate import GameSettings, GameState, PlayerState
from mapgenerator import MapGenerator, MapGeneratorSettings


def main() -> None:
    state = GameState(
        version=1,
        settings=GameSettings(
            map_size=int(MapSize.NORMAL),
            map_preset=int(MapPreset.DRYLAND),
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
    settings = MapGeneratorSettings.CreateFromPreset(int(MapPreset.DRYLAND))
    done = {"ok": False}

    def on_complete() -> None:
        done["ok"] = True

    MapGenerator().GenerateWithSeed(12345, state, settings, on_complete)

    assert done["ok"], "onComplete was not called"
    assert state.map is not None, "state.map is None"
    assert state.map.width == 16 and state.map.height == 16
    assert len(state.map.tiles) == 16 * 16
    capitals = [t for t in state.map.tiles if t.capital_of]
    assert len(capitals) >= 2, f"expected >=2 capitals, got {len(capitals)}"
    land = sum(
        1
        for t in state.map.tiles
        if t.terrain
        in (
            int(Terrain.FIELD),
            int(Terrain.FOREST),
            int(Terrain.MOUNTAIN),
            int(Terrain.ICE),
        )
    )
    assert land > 0, "expected some land tiles"
    print(
        f"ok: {state.map.width}x{state.map.height}, "
        f"land={land}, capitals={len(capitals)}, "
        f"continents={len(state.map.continents)}, settings={settings}"
    )


if __name__ == "__main__":
    main()
