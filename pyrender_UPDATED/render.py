"""Board renderer: GameState -> Image.

render.py knows NOTHING about tile internals. It builds the canvas, asks
create_tile for each finished tile image, and pastes each at its correct board
location in back-to-front order (see CONTRACT.md).

The engine draws larger (x+y) first (further back) and smaller (x+y) last (front,
on top). So we sort tiles by (x+y) DESCENDING and paste in that order: lower/front
tiles paste last and cover the upper/back ones they overlap.

Foreground uses Unity sorting-layer bands (Units → CityStatus → UnitStatus) so
city/unit UI never interleaves under units on front tiles.

    python3 render.py <gamestate.json> [out.png] [--pad N] [--player ID]
"""
from __future__ import annotations

import sys
import os
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gamestate as GS  # noqa: E402
import projection as P  # noqa: E402
import context  # noqa: E402
import create_tile  # noqa: E402
from image import Image  # noqa: E402


def _board_tiles(gs):
    tiles = []
    for y in range(gs.map.height):
        for x in range(gs.map.width):
            t = gs.map.tile_at(x, y)
            if t is not None:
                tiles.append(t)
    # Back (large x+y) first, front (small x+y) last — matches engine row depth.
    tiles.sort(key=lambda t: t.x + t.y, reverse=True)
    return tiles


def _collect_ops(ctx, frame, tiles):
    """Backgrounds, then Units → CityStatus → UnitStatus (Unity sorting layers).

    Within each sorting-layer band, tiles stay back-to-front. Labels must not
    interleave with units per-tile (that would bury front units under back cities).
    """
    bg_ops: list[tuple] = []
    # (sublayer, depth=x+y, img, left, top) — sorted later by (sublayer, -depth)
    fg_raw: list[tuple] = []

    for t in tiles:
        bg, ox, oy = create_tile.background(ctx, t.x, t.y)
        ax, ay = frame.anchor(t.x, t.y)
        bg_ops.append((bg, round(ax - ox), round(ay - oy)))

    for t in tiles:
        ax, ay = frame.anchor(t.x, t.y)
        depth = t.x + t.y
        for s, img, dx, dy in create_tile.unit_placements(ctx, t.x, t.y):
            fg_raw.append((s, depth, img, round(ax + dx), round(ay + dy)))

    # Ascending sublayer; within a layer, larger depth (back) first.
    fg_raw.sort(key=lambda e: (e[0], -e[1]))
    return bg_ops, fg_raw


def _paste_board(bg_ops, fg_ops, pad: int):
    all_ops = bg_ops + [(img, l, t) for _s, _d, img, l, t in fg_ops]
    if not all_ops:
        return None, 0, 0

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
    return canvas, off_x, off_y


def render_with_meta(gs, pad: int = 200, player_id: Optional[int] = None):
    """Same composite as render(), but also returns tile metadata.

    ``player_id`` — render from that player's perspective (fog, own-city pop bars).
    When omitted, uses ``gs.viewer`` from ``current_player_index`` (or omniscient).

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
    ctx   = context.TileContext(gs, viewer_id=player_id)
    tiles = _board_tiles(gs)

    bg_ops, fg_ops = _collect_ops(ctx, frame, tiles)
    canvas, off_x, off_y = _paste_board(bg_ops, fg_ops, pad)
    if canvas is None:
        return Image.new(1, 1, (0, 0, 0, 0)), {}, int(P.HALF_W)

    tile_centers = {}
    for t in tiles:
        ax, ay = frame.anchor(t.x, t.y)
        tile_centers[(t.x, t.y)] = (round(ax + off_x), round(ay + off_y))

    return canvas, tile_centers, int(P.HALF_W)


def render(gs, pad: int = 200, player_id: Optional[int] = None) -> Image:
    """Composite every tile of ``gs`` onto a single board canvas, back-to-front.

    ``player_id`` — render from that player's perspective (fog, own-city pop bars).
    When omitted, uses ``gs.viewer`` from ``current_player_index`` (or omniscient).

    Paint order mirrors Unity sorting layers:
      Pass 1 — all tile backgrounds (terrain … borders)
      Pass 2 — Units (outlines + bodies), back-to-front
      Pass 3 — CityStatusDisplays / text, back-to-front
      Pass 4 — UnitStatusDisplays / text, back-to-front

    Canvas size is computed from the actual sprite extents of every placement so
    tall buildings, edge tiles, and large units are never clipped.
    """
    frame = P.Frame(gs.map.width, gs.map.height, pad=pad)
    ctx   = context.TileContext(gs, viewer_id=player_id)
    tiles = _board_tiles(gs)

    bg_ops, fg_ops = _collect_ops(ctx, frame, tiles)
    canvas, _, _ = _paste_board(bg_ops, fg_ops, pad)
    if canvas is None:
        return Image.new(1, 1, (0, 0, 0, 0))
    return canvas


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    src = argv[0]
    out = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else \
        os.path.splitext(os.path.basename(src))[0] + ".png"
    pad = 200
    player_id = None
    if "--pad" in argv:
        pad = int(argv[argv.index("--pad") + 1])
    if "--player" in argv:
        player_id = int(argv[argv.index("--player") + 1])
    gs = GS.load(src)
    img = render(gs, pad=pad, player_id=player_id)
    img.save_png(out)
    print(f"rendered {gs.map.width}x{gs.map.height} board -> {out} ({img.w}x{img.h})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
