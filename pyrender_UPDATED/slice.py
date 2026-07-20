"""Tile slicer — cut individual tile crops from a full board composite.

Slicing from the composite (rather than rendering each tile in isolation)
intentionally captures bleed from neighbouring tiles: buildings, unit outlines,
and terrain that spill across tile boundaries appear naturally in each crop,
matching what the game actually shows for each tile.

Usage
-----
    from render import render_with_meta
    from slice import slice_tiles, save_slices

    image, centers, half = render_with_meta(gs)
    crops = slice_tiles(image, centers, half_size=half)
    # crops: {(x, y): Image}

    save_slices(crops, "/tmp/slices")   # writes x_y.png for every tile

CLI
---
    python3 slice.py <gamestate.json> [--out-dir /tmp/slices] [--half N] [--pad P]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from image import Image


def slice_tiles(
    image: Image,
    tile_centers: dict,
    half_size: int,
) -> dict:
    """Cut one square crop per tile from the composite board image.

    Each crop is ``(2*half_size) × (2*half_size)`` pixels, centred on the
    tile's diamond centre.  Pixels outside the board canvas are transparent
    (the crop canvas is pre-filled with alpha=0).

    Parameters
    ----------
    image        : full board composite from render_with_meta()
    tile_centers : {(grid_x, grid_y): (canvas_cx, canvas_cy)}
    half_size    : half the crop edge length in pixels (P.HALF_W ≈ 128)

    Returns
    -------
    dict {(grid_x, grid_y): Image}
    """
    side  = half_size * 2
    crops = {}
    for (gx, gy), (cx, cy) in tile_centers.items():
        # Top-left of the crop in canvas coordinates.
        src_x = cx - half_size
        src_y = cy - half_size

        crop = Image.new(side, side, (0, 0, 0, 0))

        # Clamp source rect to the canvas.
        sx0 = max(src_x, 0)
        sy0 = max(src_y, 0)
        sx1 = min(src_x + side, image.w)
        sy1 = min(src_y + side, image.h)

        if sx0 >= sx1 or sy0 >= sy1:
            crops[(gx, gy)] = crop
            continue

        # Destination offset inside the crop canvas.
        dx = sx0 - src_x
        dy = sy0 - src_y
        blit_w = sx1 - sx0
        blit_h = sy1 - sy0

        # Copy pixel-by-pixel using Image.paste on a single-row basis.
        # Build a temporary Image view of the source region and paste it.
        region_px = bytearray(blit_w * blit_h * 4)
        for row in range(blit_h):
            src_row = sy0 + row
            src_off = (src_row * image.w + sx0) * 4
            dst_off = row * blit_w * 4
            region_px[dst_off: dst_off + blit_w * 4] = \
                image.px[src_off: src_off + blit_w * 4]

        region = Image(blit_w, blit_h, region_px)
        crop.paste(region, dx, dy)
        crops[(gx, gy)] = crop

    return crops


def save_slices(crops: dict, out_dir: str) -> None:
    """Write each crop as ``<out_dir>/<x>_<y>.png``."""
    os.makedirs(out_dir, exist_ok=True)
    for (gx, gy), img in crops.items():
        img.save_png(os.path.join(out_dir, f"{gx}_{gy}.png"))


# ── CLI ───────────────────────────────────────────────────────────────────────
def main(argv):
    import argparse
    import gamestate as GS
    from render import render_with_meta

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("gamestate",  help="path to gamestate.json")
    p.add_argument("--out-dir",  default="/tmp/slices", help="output directory")
    p.add_argument("--half",     type=int, default=None,
                   help="crop half-size in px (default: diamond HALF_W ≈ 128)")
    p.add_argument("--pad",      type=int, default=200,
                   help="board render padding (default: 200)")
    args = p.parse_args(argv)

    gs = GS.load(args.gamestate)
    image, centers, half = render_with_meta(gs, pad=args.pad)
    if args.half:
        half = args.half

    crops = slice_tiles(image, centers, half)
    save_slices(crops, args.out_dir)

    print(f"sliced {len(crops)} tiles  "
          f"({half*2}×{half*2} px each)  →  {args.out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
