"""Board renderer: GameState -> Image.

render.py knows NOTHING about tile internals. It builds the canvas, asks
create_tile for each finished tile image, and pastes each at its correct board
location in back-to-front order (see CONTRACT.md).

The engine draws larger (x+y) first (further back) and smaller (x+y) last (front,
on top). So we sort tiles by (x+y) DESCENDING and paste in that order: lower/front
tiles paste last and cover the upper/back ones they overlap.

    python3 render.py <gamestate.json> [out.png] [--pad N]
"""
from __future__ import annotations

import sys
import os
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gamestate as GS  # noqa: E402
import projection as P  # noqa: E402
import context  # noqa: E402
import create_tile  # noqa: E402
from image import Image  # noqa: E402


def render_with_meta(gs, pad: int = 200):
    """Same composite as render(), but also returns tile metadata.

    Returns
    -------
    image       : Image   — the full board composite
    tile_centers: dict    — {(grid_x, grid_y): (canvas_cx, canvas_cy)}
                            pixel position of each tile's diamond centre
                            in the output image
    tile_size   : int     — recommended square crop half-size in pixels;
                            equals the diamond half-width (HALF_W ≈ 128)
                            so a full tile fits in 2*tile_size × 2*tile_size
    """
    frame = P.Frame(gs.map.width, gs.map.height, pad=pad)
    ctx   = context.TileContext(gs)

    tiles = []
    for y in range(gs.map.height):
        for x in range(gs.map.width):
            t = gs.map.tile_at(x, y)
            if t is not None:
                tiles.append(t)
    tiles.sort(key=lambda t: t.x + t.y, reverse=True)

    bg_ops:   list[tuple] = []
    unit_ops: list[tuple] = []

    for t in tiles:
        bg, ox, oy = create_tile.background(ctx, t.x, t.y)
        ax, ay = frame.anchor(t.x, t.y)
        bg_ops.append((bg, round(ax - ox), round(ay - oy)))

    for t in tiles:
        ax, ay = frame.anchor(t.x, t.y)
        for _s, img, dx, dy in sorted(
            create_tile.unit_placements(ctx, t.x, t.y), key=lambda p: p.sublayer
        ):
            unit_ops.append((img, round(ax + dx), round(ay + dy)))

    all_ops = bg_ops + unit_ops
    if not all_ops:
        return Image.new(1, 1, (0, 0, 0, 0)), {}, int(P.HALF_W)

    min_l = min(l         for _, l, _ in all_ops)
    min_t = min(t         for _, _, t in all_ops)
    max_r = max(l + img.w for img, l, _ in all_ops)
    max_b = max(t + img.h for img, _, t in all_ops)

    off_x = -min_l + pad
    off_y = -min_t + pad
    cw    = max_r - min_l + 2 * pad
    ch    = max_b - min_t + 2 * pad

    canvas = Image.new(cw, ch, (0, 0, 0, 0))
    for img, l, t in all_ops:
        canvas.paste(img, l + off_x, t + off_y)

    # Tile diamond centres in canvas space.
    tile_centers = {}
    for t in tiles:
        ax, ay = frame.anchor(t.x, t.y)
        tile_centers[(t.x, t.y)] = (round(ax + off_x), round(ay + off_y))

    return canvas, tile_centers, int(P.HALF_W)


def render(gs, pad: int = 200) -> Image:
    """Composite every tile of ``gs`` onto a single board canvas, back-to-front.

    Two passes share the same depth order so units always sit in front of tile
    backgrounds at the same depth rather than being buried by them:
      Pass 1 — all tile backgrounds (terrain, improvements, borders)
      Pass 2 — all units + labels

    Canvas size is computed from the actual sprite extents of every placement so
    tall buildings, edge tiles, and large units are never clipped.
    """
    frame = P.Frame(gs.map.width, gs.map.height, pad=pad)
    ctx   = context.TileContext(gs)

    tiles = []
    for y in range(gs.map.height):
        for x in range(gs.map.width):
            t = gs.map.tile_at(x, y)
            if t is not None:
                tiles.append(t)
    tiles.sort(key=lambda t: t.x + t.y, reverse=True)

    # Collect all (img, left, top) in paint order (backgrounds then units).
    bg_ops:   list[tuple] = []
    unit_ops: list[tuple] = []

    for t in tiles:
        bg, ox, oy = create_tile.background(ctx, t.x, t.y)
        ax, ay = frame.anchor(t.x, t.y)
        bg_ops.append((bg, round(ax - ox), round(ay - oy)))

    for t in tiles:
        ax, ay = frame.anchor(t.x, t.y)
        for _s, img, dx, dy in sorted(
            create_tile.unit_placements(ctx, t.x, t.y), key=lambda p: p.sublayer
        ):
            unit_ops.append((img, round(ax + dx), round(ay + dy)))

    all_ops = bg_ops + unit_ops
    if not all_ops:
        return Image.new(1, 1, (0, 0, 0, 0))

    # Compute actual bounding box across all placements.
    min_l = min(l           for _, l, _ in all_ops)
    min_t = min(t           for _, _, t in all_ops)
    max_r = max(l + img.w   for img, l, _ in all_ops)
    max_b = max(t + img.h   for img, _, t in all_ops)

    off_x = -min_l + pad
    off_y = -min_t + pad
    cw    = max_r - min_l + 2 * pad
    ch    = max_b - min_t + 2 * pad

    canvas = Image.new(cw, ch, (0, 0, 0, 0))
    for img, l, t in all_ops:
        canvas.paste(img, l + off_x, t + off_y)

    return canvas


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    src = argv[0]
    out = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else \
        os.path.splitext(os.path.basename(src))[0] + ".png"
    pad = 200
    if "--pad" in argv:
        pad = int(argv[argv.index("--pad") + 1])
    gs = GS.load(src)
    img = render(gs, pad=pad)
    img.save_png(out)
    print(f"rendered {gs.map.width}x{gs.map.height} board -> {out} ({img.w}x{img.h})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
