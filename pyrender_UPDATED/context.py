"""Shared render context + tile-local placement API for the create_* modules.

This is the single interface every ``create_{component}.py`` and ``create_tile.py`` builds
against, so the modules stay compatible. It replaces the old layer/Item/global-sort design:
components now return baked **images** placed in **tile-local** coordinates, and create_tile
composites them per tile (see CONTRACT.md).

Key concepts
------------
- **Tile-local space**: the tile's diamond CENTRE is the local origin (0, 0). +x = right,
  +y = DOWN (screen pixels). Components never know where the tile lands on the board;
  render.py places the finished tile via projection.Frame.

- **Placement** = ``(sublayer, image, dx, dy)``:
    sublayer : int   engine sub-layer offset (enums.SORT_*); lower = drawn first (further back)
    image    : Image already baked (themed sprite chosen, render-scaled, tinted, flipped)
    dx, dy   : int   top-left of ``image`` relative to the tile-local origin (diamond centre)
  A component returns ``List[Placement]`` (possibly empty, possibly several at different
  sub-layers — e.g. borders emit at sub-layer 0 and 99).

Contract for create_{component}.py
-----------------------------------
    def items(ctx: TileContext, x: int, y: int) -> list[Placement]
Resolve the component's sprite(s) for tile (x, y), bake each to an Image with ctx.bake(...),
compute a tile-local top-left with one of the ctx.seat_* helpers, and return Placements.
Return [] when the component has nothing on this tile. Do NOT read/írite the board canvas.

Contract for create_tile.py
----------------------------
    def items(ctx, x, y) -> tuple[Image, int, int]   # (tile_image, origin_x, origin_y)
Gather Placements from every component (or just fog when ctx.is_hidden), STABLE-sort by
sublayer (ties keep component/emit order), composite onto one canvas, and return the image
plus where the local origin (diamond centre) sits inside it.
"""
from __future__ import annotations

from typing import List, NamedTuple, Optional, Tuple

import enums as E
import projection as P
import spritemeta as SM
import spritelookup as SL
import tribecolors as TC
from assets import SpriteStore
from image import Image

# Foot offsets (px below diamond centre) for planted objects — mirror layerlib.
FEATURE_FOOT = P.HALF_H            # bottom vertex of the diamond
OBJECT_FOOT = P.HALF_H * 0.55      # buildings/resources sit a bit above the bottom vertex
SEAT_DROP = 0.0                    # global vertical nudge for pivot-seated objects (px, +down)

# Trim-corrected pivots for sprites whose stored m_Pivot mis-seats them (ported from layers.py).
_SEAT_PIVOT_OVERRIDE = {
    "MarketIcon": (0.58333, 0.56588),
}


class Placement(NamedTuple):
    sublayer: int          # enums.SORT_* (lower drawn first / further back)
    image: Image           # already baked (scaled/tinted/flipped)
    dx: int                # top-left x relative to tile-local origin (diamond centre)
    dy: int                # top-left y relative to tile-local origin


class TileContext:
    """Read view of the GameState + sprite services, shared by all create_* modules.

    Ported from the old render.RenderContext but with a TILE-LOCAL placement API (no board
    Frame here — render.py owns board placement)."""

    def __init__(self, gs, store: Optional[SpriteStore] = None,
                 viewer_id: Optional[int] = None):
        self.gs = gs
        self.map = gs.map
        self.store = store if store is not None else SpriteStore()
        if viewer_id is not None:
            self.viewer_id = int(viewer_id)
        else:
            viewer = getattr(gs, "viewer", None)
            self.viewer_id = viewer.id if viewer else 0xFF
        self._pivot_cache = {}

    # ----------------------------------------------------------------- queries
    def tile_at(self, x: int, y: int):
        return self.map.tile_at(x, y)

    def is_hidden(self, tile) -> bool:
        if self.viewer_id == 0xFF:
            return False
        return self.viewer_id not in tile.explorers

    def tile_theme(self, tile) -> Tuple[int, int]:
        """(tribe, skin) for a tile's terrain art — climate holds a Tribe value."""
        tribe = tile.climate if tile.climate else 0
        skin = tile.skin if tile.skin and tile.skin > 0 else 0
        return tribe, skin

    def player_color(self, pid: int) -> Optional[Tuple[int, int, int]]:
        p = self.gs.player_by_id(pid)
        if p is None:
            return None
        if p.color:
            c = p.color & 0xFFFFFF
            return ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)
        skin = p.skin_type if p.skin_type and p.skin_type > 0 else 0
        return TC.get_tribe_rgb(p.tribe, skin)

    def player_tribe_skin(self, pid: int) -> Tuple[int, int]:
        p = self.gs.player_by_id(pid)
        if p is None:
            return 0, 0
        return p.tribe, (p.skin_type if p.skin_type and p.skin_type > 0 else 0)

    # ----------------------------------------------------------------- sprites
    def resolve(self, base: str, tribe: int = 0, skin: int = 0, level: int = -1,
                check_outline: bool = False):
        """DoSpriteLookup: (sprite_name|None, outline_name|None)."""
        return SL.resolve(self.store, base, tribe, skin, level, check_outline)

    def exists(self, name: str) -> bool:
        return self.store.exists(name)

    def size(self, name: str) -> Tuple[int, int]:
        return self.store.size(name)

    def bake(self, name: str, tint: Optional[Tuple[int, int, int]] = None,
             flip: bool = False, scale: float = 1.0) -> Optional[Image]:
        """Load ``name`` and apply (a) measured render-scale * ``scale`` about its own size,
        (b) team ``tint`` multiply, (c) horizontal ``flip`` — returning a fresh Image ready to
        composite. Returns None if the sprite is missing."""
        if not self.store.exists(name):
            return None
        try:
            img = self.store.get(name)
        except KeyError:
            return None
        s = SM.render_scale(name) * scale
        nw, nh = max(1, round(img.w * s)), max(1, round(img.h * s))
        if (nw, nh) != (img.w, img.h):
            img = img.resized(nw, nh)
        if tint is not None:
            img = img.tinted(tint)
        if flip:
            img = img.flipped_x()
        return img

    # ----------------------------------------------------------- local seating
    # All return the (left, top) of a sprite of size (w, h) in TILE-LOCAL pixels
    # (diamond centre = origin). Pick the one matching the engine seating for that layer.
    def seat_planted(self, w: int, h: int, foot: float = FEATURE_FOOT,
                     dx: float = 0.0, dy: float = 0.0) -> Tuple[int, int]:
        """Horizontally centred; sprite bottom at foot. (ports layerlib.place_planted)"""
        return round(dx - w / 2.0), round(dy + foot - h)

    def seat_base(self, name: str, w: int, h: int) -> Tuple[int, int]:
        """Seat a full-tile base/terrain sprite on its diamond centre (ports place_base)."""
        pvx, pvy = self._diamond_pivot(name)
        return round(-pvx * w), round(-(1.0 - pvy) * h)

    def seat_pivot(self, name: str, w: int, h: int) -> Tuple[int, int]:
        """Seat a tile-centred object by its MEASURED pivot (ports layers._seat)."""
        pvx, pvy = _SEAT_PIVOT_OVERRIDE.get(name) or SM.pivot(name) or (0.5, 0.5)
        return round(-pvx * w), round(SEAT_DROP - (1.0 - pvy) * h)

    def _diamond_pivot(self, name: str):
        c = self._pivot_cache.get(name)
        if c is None:
            c = P.diamond_center_pivot(self.store.get(name))
            self._pivot_cache[name] = c
        return c
