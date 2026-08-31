"""Board renderer: GameState -> Image.

render.py knows NOTHING about tile internals. It builds the canvas, asks
create_tile for each finished tile image, and pastes each at its correct board
location in back-to-front order (see CONTRACT.md).

The engine draws larger (x+y) first (further back) and smaller (x+y) last (front,
on top). So we sort tiles by (x+y) DESCENDING and paste in that order: lower/front
tiles paste last and cover the upper/back ones they overlap.

Foreground uses Unity sorting-layer bands (Units → CityStatus → UnitStatus) so
city/unit UI never interleaves under units on front tiles.

For interactive / replay use, prefer ``LiveBoard``: it caches per-tile backgrounds
and a flattened background layer. ``refresh_move()`` diffs GameState and only
rebuilds backgrounds that changed (any action — move, build, capture, …).

    python3 render.py <gamestate.json> [out.png] [--pad N] [--player ID]
"""
from __future__ import annotations

import sys
import os
from typing import Iterable, Optional, Set, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gamestate as GS  # noqa: E402
import projection as P  # noqa: E402
import context  # noqa: E402
import create_tile  # noqa: E402
from image import Image  # noqa: E402

Coord = Tuple[int, int]


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


def _collect_ops(ctx, frame, tiles, bg_cache=None, dirty_bg=None):
    """Backgrounds, then Units → CityStatus → UnitStatus (Unity sorting layers).

    Within each sorting-layer band, tiles stay back-to-front. Labels must not
    interleave with units per-tile (that would bury front units under back cities).

    ``bg_cache`` maps (x, y) -> (bg_img, ox, oy). When provided, backgrounds are
    taken from the cache unless ``dirty_bg`` contains that coord (or is None =
    rebuild everything). Updated entries are written back into ``bg_cache``.
    """
    bg_ops: list[tuple] = []
    # (sublayer, depth=x+y, img, left, top) — sorted later by (sublayer, -depth)
    fg_raw: list[tuple] = []

    rebuild_all = bg_cache is None or dirty_bg is None

    for t in tiles:
        key = (t.x, t.y)
        if rebuild_all or key in dirty_bg or key not in bg_cache:
            bg, ox, oy = create_tile.background(ctx, t.x, t.y)
            if bg_cache is not None:
                bg_cache[key] = (bg, ox, oy)
        else:
            bg, ox, oy = bg_cache[key]
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


def _ops_bounds(ops, pad: int):
    if not ops:
        return None
    min_l = min(l         for _, l, _ in ops)
    min_t = min(t         for _, _, t in ops)
    max_r = max(l + img.w for img, l, _ in ops)
    max_b = max(t + img.h for img, _, t in ops)
    off_x = -min_l + pad
    off_y = -min_t + pad
    cw = max_r - min_l + 2 * pad
    ch = max_b - min_t + 2 * pad
    return off_x, off_y, cw, ch


def _paste_ops(ops, off_x: int, off_y: int, cw: int, ch: int,
               base: Optional[Image] = None) -> Image:
    """Paste ``ops`` onto a new canvas, or onto a copy of ``base`` if given."""
    if base is not None:
        canvas = base.copy()
        if canvas.w != cw or canvas.h != ch:
            # Bounds shifted (rare) — fall back to fresh canvas + base paste.
            canvas = Image.new(cw, ch, (0, 0, 0, 0))
            canvas.paste(base, 0, 0)
    else:
        canvas = Image.new(cw, ch, (0, 0, 0, 0))
    for img, l, t in ops:
        canvas.paste(img, l + off_x, t + off_y)
    return canvas


def _paste_board(bg_ops, fg_ops, pad: int):
    all_ops = bg_ops + [(img, l, t) for _s, _d, img, l, t in fg_ops]
    bounds = _ops_bounds(all_ops, pad)
    if bounds is None:
        return None, 0, 0
    off_x, off_y, cw, ch = bounds
    canvas = _paste_ops(all_ops, off_x, off_y, cw, ch)
    return canvas, off_x, off_y


def neighbour_coords(coords: Iterable[Coord],
                     orth_only: bool = True) -> Set[Coord]:
    """Self + orthogonal (or 8-way) neighbours — for border/shoreline invalidation.

    Mirrors ``MapRendererInner.ReRenderShorelinesOnNeighbours``: when a tile's
    terrain/occupancy changes, orth neighbours must re-run shoreline/border/road
    graphics. Overhang is *not* handled by neighbour dirtying — the engine keeps
    each tile as its own sorted mesh (``Tile.BatchSprites`` / ``sortingOrder``).
    """
    out: Set[Coord] = set()
    deltas = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))
    if not orth_only:
        deltas = deltas + ((1, 1), (1, -1), (-1, 1), (-1, -1))
    for x, y in coords:
        for dx, dy in deltas:
            out.add((x + dx, y + dy))
    return out


def _improvement_bg_key(imp) -> Optional[tuple]:
    if imp is None:
        return None
    return (
        int(imp.type), int(imp.level), int(imp.owner), int(imp.founder),
        int(imp.population), int(imp.production), int(imp.base_score),
        int(imp.border_size), int(imp.upgrade), int(imp.xp), int(imp.founded),
        int(imp.connected_to_capital_of_player), str(imp.name),
        tuple(imp.rewards), tuple(imp.effects), tuple(imp.discovered_by),
    )


def _shoreline_bg_key(sl) -> Optional[tuple]:
    if sl is None:
        return None

    def edge(e):
        return (bool(e.visible), str(e.sprite_ext))

    return (bool(sl.any), edge(sl.N), edge(sl.S), edge(sl.E), edge(sl.W))


def _tile_bg_key(tile, viewer_id: int) -> tuple:
    """Fingerprint of everything that affects a tile's *background* composite.

    Units/labels are redrawn every refresh, so they are intentionally omitted.
    Fog collapses to a single sentinel — only visibility matters when hidden.
    """
    if viewer_id != 0xFF and viewer_id not in tile.explorers:
        return ("hidden",)
    res = int(tile.resource.type) if tile.resource is not None else None
    return (
        int(tile.terrain), int(tile.climate), int(tile.skin),
        int(tile.owner), int(tile.capital_of),
        tuple(sorted(int(e) for e in tile.effects)),
        bool(tile.has_road), bool(tile.has_route),
        res,
        _improvement_bg_key(tile.improvement),
        _shoreline_bg_key(tile.shorelines),
        (int(tile.ruling_city_coordinates.x),
         int(tile.ruling_city_coordinates.y)),
    )


def _players_bg_key(gs) -> tuple:
    """Team colour / tribe/skin/tech — borders, themed art, resource visibility."""
    players = getattr(gs, "player_states", None) or ()
    return tuple(
        (int(p.id), int(p.color or 0), int(p.tribe), int(p.skin_type or 0),
         tuple(int(x) for x in (p.built_unique_improvements or ())),
         tuple(sorted(int(t) for t in (p.available_tech or ()))))
        for p in players
    )


class LiveBoard:
    """Persistent board compositor with per-tile background caching.

    Typical use after *any* action (move, attack, build, capture, …)::

        board = LiveBoard(gs)
        img = board.render()       # cold
        # ... mutate gs ...
        img = board.refresh_move() # diffs tile state, dirties only what changed
    """

    def __init__(self, gs, pad: int = 200, player_id: Optional[int] = None,
                 store=None):
        self.gs = gs
        self.pad = pad
        self.player_id = player_id
        self.ctx = context.TileContext(gs, store=store, viewer_id=player_id)
        self.frame = P.Frame(gs.map.width, gs.map.height, pad=pad)
        self._bg_cache: dict[Coord, tuple] = {}
        self._bg_layer: Optional[Image] = None
        self._bg_keys: dict[Coord, tuple] = {}
        self._players_key: Optional[tuple] = None
        self._off_x = 0
        self._off_y = 0
        self._cw = 0
        self._ch = 0
        self._tiles = _board_tiles(gs)

    def bind(self, gs) -> None:
        """Point at a new / mutated GameState (same map size). Keeps bake + bg caches."""
        self.gs = gs
        self.ctx.gs = gs
        self.ctx.map = gs.map
        if self.player_id is not None:
            self.ctx.viewer_id = int(self.player_id)
        else:
            viewer = getattr(gs, "viewer", None)
            self.ctx.viewer_id = viewer.id if viewer else 0xFF
        self._tiles = _board_tiles(gs)

    def invalidate(self, coords: Iterable[Coord]) -> None:
        """Drop cached backgrounds for the given tiles (rebuild on next refresh)."""
        for c in coords:
            self._bg_cache.pop(c, None)
            self._bg_keys.pop(c, None)
        self._bg_layer = None

    def invalidate_all(self) -> None:
        self._bg_cache.clear()
        self._bg_keys.clear()
        self._bg_layer = None
        self._players_key = None

    def render(self) -> Image:
        """Full render; (re)builds every tile background into the cache."""
        return self.refresh(dirty_bg=None)

    def _snapshot_bg_keys(self) -> None:
        vid = self.ctx.viewer_id
        self._bg_keys = {
            (t.x, t.y): _tile_bg_key(t, vid) for t in self._tiles
        }
        self._players_key = _players_bg_key(self.gs)

    def dirty_from_state(self, extra: Iterable[Coord] = ()) -> Optional[Set[Coord]]:
        """Coords whose background art may have changed since the last refresh.

        Returns ``None`` when a full background rebuild is required (first frame,
        or player colours / tribe skins changed). Otherwise a (possibly empty)
        set — empty means only units/labels need redrawing.
        """
        if self._players_key is None or not self._bg_keys:
            return None
        if _players_bg_key(self.gs) != self._players_key:
            return None

        vid = self.ctx.viewer_id
        changed: Set[Coord] = set(extra)
        seen: Set[Coord] = set()
        for t in self._tiles:
            key = (t.x, t.y)
            seen.add(key)
            fp = _tile_bg_key(t, vid)
            if self._bg_keys.get(key) != fp:
                changed.add(key)
        # Tiles that disappeared from the map (shouldn't happen mid-game).
        for key in self._bg_keys:
            if key not in seen:
                changed.add(key)

        if not changed:
            return set()
        # Match MapRendererInner.ReRenderShorelinesOnNeighbours: rebuild the
        # changed tile plus its orth neighbours (shores / borders / roads).
        # Cross-tile overhang is handled by re-flattening *all* cached tile
        # sprites in sorting order (see refresh) — same as Unity drawing every
        # Tile mesh via sortingOrder, not by dirtying a −x/−y cone.
        return neighbour_coords(changed)

    def refresh(self, dirty_bg: Optional[Iterable[Coord]] = ()) -> Image:
        """Recomposite the board.

        Mirrors the engine loop:
          - ``Tile.isDirty`` → rebuild that tile's sprites (``BatchSprites``)
          - ``MapRendererInner.BatchDirtySprites`` → only dirty tiles re-batch
          - Unity still draws *every* tile mesh each frame via ``sortingOrder``

        So we rebuild art only for ``dirty_bg``, then always re-flatten the full
        cached background stack when anything changed (empty dirty = reuse the
        flattened layer and only redraw units/labels).

        ``dirty_bg``
          - ``None``  — rebuild every tile background
          - empty     — reuse all cached backgrounds + flattened bg layer
          - iterable  — rebuild those tile backgrounds, then re-flatten all
        """
        dirty_set: Optional[Set[Coord]]
        if dirty_bg is None:
            dirty_set = None
            self._bg_layer = None
        else:
            dirty_set = set(dirty_bg)
            for t in self._tiles:
                key = (t.x, t.y)
                if key not in self._bg_cache:
                    dirty_set.add(key)
            if dirty_set:
                # Any art change → drop flattened layer; re-paste all cached
                # tile sprites back→front (painter's algorithm / sortingOrder).
                self._bg_layer = None

        bg_ops, fg_ops = _collect_ops(
            self.ctx, self.frame, self._tiles,
            bg_cache=self._bg_cache, dirty_bg=dirty_set,
        )
        fg_flat = [(img, l, t) for _s, _d, img, l, t in fg_ops]
        all_ops = bg_ops + fg_flat
        bounds = _ops_bounds(all_ops, self.pad)
        if bounds is None:
            self._snapshot_bg_keys()
            return Image.new(1, 1, (0, 0, 0, 0))
        off_x, off_y, cw, ch = bounds
        self._off_x, self._off_y, self._cw, self._ch = off_x, off_y, cw, ch

        if self._bg_layer is None or self._bg_layer.w != cw or self._bg_layer.h != ch:
            self._bg_layer = _paste_ops(bg_ops, off_x, off_y, cw, ch)

        self._snapshot_bg_keys()

        if not fg_flat:
            return self._bg_layer.copy()
        return _paste_ops(fg_flat, off_x, off_y, cw, ch, base=self._bg_layer)

    def refresh_move(self, *tiles: Coord) -> Image:
        """Refresh after any action (move, attack, build, capture, end turn, …).

        Diffs the current ``GameState`` against the last render and rebuilds only
        backgrounds that changed (plus orth neighbours for shores/borders/roads).
        Units and labels are always redrawn. Optional ``*tiles`` are extra dirty
        hints merged into the auto-diff.
        """
        dirty = self.dirty_from_state(tiles)
        return self.refresh(dirty_bg=dirty)


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

    For repeated renders after moves, use ``LiveBoard`` instead of calling this
    each time — it caches tile backgrounds across updates.
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
