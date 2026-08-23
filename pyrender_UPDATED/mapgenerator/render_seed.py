"""Generate a seeded map and render it with pyrender.

Usage:
  cd pyrender_UPDATED
  python3 -m mapgenerator.render_seed --seed 12345 --preset continents --size normal \\
      -o /tmp/gen_continents.png
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enums import MapPreset, MapSize, Tribe
from gamestate import GameSettings, GameState, PlayerState
from mapgenerator import MapGenerator, MapGeneratorSettings
from mapgenerator.dump_seed import _PRESET, _SIZE
import render


def build_state(seed: int, preset: MapPreset, size: MapSize, tribes: list[int]) -> GameState:
    players = [
        PlayerState(id=i + 1, tribe=t, climate=t, has_chosen_tribe=True, color=0)
        for i, t in enumerate(tribes)
    ]
    state = GameState(
        version=1,
        seed=seed,
        current_player_index=0,
        settings=GameSettings(map_size=int(size), map_preset=int(preset)),
        player_states=players,
    )
    settings = MapGeneratorSettings.CreateFromPreset(int(preset))
    MapGenerator().GenerateWithSeed(seed, state, settings, None)
    return state


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--preset", choices=sorted(_PRESET), default="continents")
    p.add_argument("--size", choices=sorted(_SIZE), default="normal")
    p.add_argument("--tribes", default="imperius,bardur")
    p.add_argument("-o", "--output", default="/tmp/mapgen_render.png")
    p.add_argument("--pad", type=int, default=80)
    args = p.parse_args(argv)

    name_to_tribe = {t.name.lower(): int(t) for t in Tribe}
    tribes = []
    for part in args.tribes.split(","):
        key = part.strip().lower().replace("-", "_")
        if key not in name_to_tribe:
            raise SystemExit(f"unknown tribe {part!r}")
        tribes.append(name_to_tribe[key])

    state = build_state(
        args.seed, _PRESET[args.preset], _SIZE[args.size], tribes
    )
    assert state.map is not None
    img = render.render(state, pad=args.pad)
    img.save_png(args.output)
    print(
        f"rendered seed={args.seed} {args.preset} {state.map.width}x{state.map.height} "
        f"-> {args.output} ({img.w}x{img.h})"
    )


if __name__ == "__main__":
    main()
