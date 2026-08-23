"""Dump a generated map to JSON for seed-parity / visual diffs.

Usage:
  python3 -m mapgenerator.dump_seed --seed 12345 --preset dryland --size normal -o /tmp/map.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enums import MAP_SIZE_WIDTH, MapPreset, MapSize, Terrain, Tribe
from gamestate import GameSettings, GameState, PlayerState
from mapgenerator import MapGenerator, MapGeneratorSettings


_PRESET = {
    "none": MapPreset.NONE,
    "dryland": MapPreset.DRYLAND,
    "lakes": MapPreset.LAKES,
    "continents": MapPreset.CONTINENTS,
    "archipelago": MapPreset.ARCHIPELAGO,
    "water_world": MapPreset.WATER_WORLD,
    "pangea": MapPreset.PANGEA,
}
_SIZE = {
    "tiny": MapSize.TINY,
    "small": MapSize.SMALL,
    "normal": MapSize.NORMAL,
    "large": MapSize.LARGE,
    "huge": MapSize.HUGE,
    "massive": MapSize.MASSIVE,
}


def generate_dump(
    seed: int,
    preset: MapPreset,
    size: MapSize,
    tribes: list[int],
) -> dict:
    players = [
        PlayerState(id=i + 1, tribe=t, climate=t, has_chosen_tribe=True)
        for i, t in enumerate(tribes)
    ]
    state = GameState(
        version=1,
        settings=GameSettings(map_size=int(size), map_preset=int(preset)),
        player_states=players,
    )
    settings = MapGeneratorSettings.CreateFromPreset(int(preset))
    MapGenerator().GenerateWithSeed(seed, state, settings, lambda: None)
    assert state.map is not None
    m = state.map
    terrain = [t.terrain for t in m.tiles]
    capitals = [
        {"x": t.x, "y": t.y, "owner": t.capital_of}
        for t in m.tiles
        if t.capital_of
    ]
    return {
        "seed": seed,
        "preset": int(preset),
        "map_size": int(size),
        "width": m.width,
        "height": m.height,
        "settings": settings.ToString(),
        "terrain": terrain,
        "capitals": capitals,
        "land_count": sum(
            1
            for t in terrain
            if t
            in (
                int(Terrain.FIELD),
                int(Terrain.FOREST),
                int(Terrain.MOUNTAIN),
                int(Terrain.ICE),
            )
        ),
        "water_count": sum(1 for t in terrain if t == int(Terrain.WATER)),
        "ocean_count": sum(1 for t in terrain if t == int(Terrain.OCEAN)),
    }


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--preset", choices=sorted(_PRESET), default="dryland")
    p.add_argument("--size", choices=sorted(_SIZE), default="normal")
    p.add_argument(
        "--tribes",
        default="imperius,bardur",
        help="comma tribe names (imperius,bardur,...)",
    )
    p.add_argument("-o", "--output", default="-")
    args = p.parse_args(argv)

    name_to_tribe = {t.name.lower(): int(t) for t in Tribe}
    tribes = []
    for part in args.tribes.split(","):
        key = part.strip().lower().replace("-", "_")
        if key not in name_to_tribe:
            raise SystemExit(f"unknown tribe {part!r}")
        tribes.append(name_to_tribe[key])

    dump = generate_dump(
        args.seed, _PRESET[args.preset], _SIZE[args.size], tribes
    )
    text = json.dumps(dump, indent=2)
    if args.output == "-":
        print(text)
    else:
        with open(args.output, "w") as f:
            f.write(text)
        print(
            f"wrote {args.output}: {dump['width']}x{dump['height']} "
            f"land={dump['land_count']} water={dump['water_count']} "
            f"ocean={dump['ocean_count']} capitals={len(dump['capitals'])}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
