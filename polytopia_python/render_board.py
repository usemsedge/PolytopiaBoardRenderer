#!/usr/bin/env python3
"""Render Polytopia GameState boards to PNG.

Usage:
  python3 render_board.py --example -o board.png
  python3 render_board.py --all -o boards/
  python3 render_board.py --preset 3 -o board.png
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(_ROOT.parent))

from polytopia_python.board_renderer import DEFAULT_SPRITE_DIR, PIXELS_PER_UNIT, render_game_state
from polytopia_python.example_match import BOARD_PRESETS, build_board_preset, build_example_match, preset_slug


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Polytopia GameState to PNG")
    parser.add_argument("-o", "--output", type=Path, default=Path("board.png"), help="Output PNG or directory")
    parser.add_argument("--ppu", type=float, default=PIXELS_PER_UNIT, help="Pixels per Unity world unit")
    parser.add_argument("--sprites", type=Path, default=DEFAULT_SPRITE_DIR, help="Sprite directory")
    parser.add_argument("--viewer", type=int, default=1, help="Viewing player id (fog of war)")
    parser.add_argument("--example", action="store_true", help="Use first four-tribe preset")
    parser.add_argument("--all", action="store_true", help="Render all eight four-tribe presets")
    parser.add_argument("--preset", type=int, choices=range(len(BOARD_PRESETS)), help="Preset index 0–7")
    args = parser.parse_args()

    if args.all:
        out_dir = args.output
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, preset in enumerate(BOARD_PRESETS):
            slug = preset_slug(preset)
            path = out_dir / f"{i + 1:02d}_{slug}.png"
            render_game_state(
                build_board_preset(i),
                path,
                sprite_dir=args.sprites,
                pixels_per_unit=args.ppu,
                viewing_player_id=args.viewer,
            )
            print(f"Wrote {path} ({path.stat().st_size // 1024} KB)")
        return 0

    if args.preset is not None:
        state = build_board_preset(args.preset)
    elif args.example:
        state = build_example_match()
    else:
        print("Provide --example, --all, or --preset N.", file=sys.stderr)
        return 1

    out = render_game_state(
        state,
        args.output,
        sprite_dir=args.sprites,
        pixels_per_unit=args.ppu,
        viewing_player_id=args.viewer,
    )
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
