"""Render a montage of all map presets for one seed.

Usage:
  cd pyrender_UPDATED
  python3 -m mapgenerator.render_montage --seed 42 -o /tmp/mapgen_montage.png
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enums import MapPreset, MapSize, Tribe
from gamestate import GameSettings, GameState, PlayerState
from image import Image
from mapgenerator import MapGenerator, MapGeneratorSettings
import render

_PRESETS = [
    MapPreset.DRYLAND,
    MapPreset.LAKES,
    MapPreset.CONTINENTS,
    MapPreset.ARCHIPELAGO,
    MapPreset.WATER_WORLD,
    MapPreset.PANGEA,
]


def _gen(seed: int, preset: MapPreset, size: MapSize) -> GameState:
    tribes = [int(Tribe.IMPERIUS), int(Tribe.BARDUR), int(Tribe.KICKOO), int(Tribe.XINXI)]
    # Fewer players on tiny water maps still fine with 2.
    use = tribes[:2]
    state = GameState(
        version=1,
        seed=seed,
        current_player_index=0,
        settings=GameSettings(map_size=int(size), map_preset=int(preset)),
        player_states=[
            PlayerState(id=i + 1, tribe=t, climate=t, has_chosen_tribe=True)
            for i, t in enumerate(use)
        ],
    )
    settings = MapGeneratorSettings.CreateFromPreset(int(preset))
    MapGenerator().GenerateWithSeed(seed, state, settings, None)
    return state


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--size", default="small", choices=["tiny", "small", "normal"])
    p.add_argument("-o", "--output", default="/tmp/mapgen_montage.png")
    p.add_argument("--pad", type=int, default=40)
    args = p.parse_args(argv)

    size = {
        "tiny": MapSize.TINY,
        "small": MapSize.SMALL,
        "normal": MapSize.NORMAL,
    }[args.size]

    images: list[Image] = []
    for preset in _PRESETS:
        st = _gen(args.seed, preset, size)
        img = render.render(st, pad=args.pad)
        images.append(img)
        print(f"  {preset.name}: {st.map.width}x{st.map.height} -> {img.w}x{img.h}")

    # 2x3 grid
    cols, rows = 3, 2
    cell_w = max(im.w for im in images)
    cell_h = max(im.h for im in images)
    gap = 16
    canvas = Image.new(
        cols * cell_w + (cols + 1) * gap,
        rows * cell_h + (rows + 1) * gap,
        (20, 24, 32, 255),
    )
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        x = gap + c * (cell_w + gap) + (cell_w - im.w) // 2
        y = gap + r * (cell_h + gap) + (cell_h - im.h) // 2
        canvas.paste(im, x, y)

    canvas.save_png(args.output)
    print(f"wrote montage {canvas.w}x{canvas.h} -> {args.output}")


if __name__ == "__main__":
    main()
