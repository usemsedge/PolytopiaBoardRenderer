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

# Enemy-land colour: not a straight multiply.
#   1. RGB *= 0xF3/255  (packed 0x7FF3F3F3; white 255 → 243)
#   2. lerp toward Rec.709 luma by 0.4  (chroma lift: (51,0,0) → G,B=4)
# Recovered from (153,51,51)→(115,57,57), (51,0,0)→(33,4,4), (255,255,255)→(243,243,243).
DESAT_RGB = (0xF3, 0xF3, 0xF3)
DESAT_LUMA_BLEND = 0.4


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
        # Whose turn/UI perspective for unit outlines / typeOutline. Defaults to
        # viewer_id; the editor keeps them in sync with the selected player.
        self.perspective_id = self.viewer_id
        self._pivot_cache = {}
        # (name, tint, flip, scale) → baked Image. Bake is pure; reuse across tiles.
        self._bake_cache: dict = {}

    # ----------------------------------------------------------------- queries
    def tile_at(self, x: int, y: int):
        return self.map.tile_at(x, y)

    def is_perspective_owner(self, owner_id: int) -> bool:
        """True when ``owner_id`` is the local/perspective player (unit action UI)."""
        pid = int(self.perspective_id)
        if pid == 0xFF:
            return False
        return int(owner_id) == pid

    def is_hidden(self, tile) -> bool:
        if self.viewer_id == 0xFF:
            return False
        return self.viewer_id not in tile.explorers

    def should_desaturate(self, tile) -> bool:
        """Enemy-owned land — RenderTerrain ownership / IsWater / Ice gates."""
        if tile is None or self.viewer_id == 0xFF:
            return False
        owner = int(tile.owner)
        if owner == 0 or owner == self.viewer_id:
            return False
        if tile.terrain in (E.Terrain.WATER, E.Terrain.OCEAN, E.Terrain.ICE):
            return False
        return True

    def apply_desat(self, img: Image) -> Image:
        """Enemy-land colour: × 0xF3/255, then lerp Rec.709 luma by 0.4."""
        return img.multiply_lerp_luma(DESAT_RGB, DESAT_LUMA_BLEND)

    def tile_theme(self, tile) -> Tuple[int, int]:
        """(tribe, skin) for a tile's terrain art.

        ``tile.climate`` is a TribeType (deserialize maps the live-game climate
        style through ``GetTribeTypeFromLegacyIndex`` first).

        Elyrion climate tiles keep the normal (default) skin even when the
        stored tile skin is DarkElf. That is overridden when the tile sits
        inside the border of a city currently owned by a DarkElf player:
        any climate then uses the DarkElf tile skin.
        """
        tribe = tile.climate if tile.climate else 0
        skin = tile.skin if tile.skin and tile.skin > 0 else 0
        if int(tribe) == int(E.Tribe.ELYRION) and int(skin) == int(E.Skin.DARKELF):
            skin = 0
        if self._ruled_by_darkelf_city(tile):
            skin = int(E.Skin.DARKELF)
        return tribe, skin

    def _ruled_by_darkelf_city(self, tile) -> bool:
        """True when this tile is in the territory of a DarkElf-owned city."""
        rc = getattr(tile, "ruling_city_coordinates", None)
        if rc is None or int(rc.x) < 0 or int(rc.y) < 0:
            return False
        city = self.tile_at(int(rc.x), int(rc.y))
        if city is None:
            return False
        imp = city.improvement
        if imp is None or int(imp.type) != int(E.Improvement.CITY):
            return False
        owner = int(city.owner or 0)
        if not owner:
            return False
        _tribe, pskin = self.player_tribe_skin(owner)
        return int(pskin) == int(E.Skin.DARKELF)

    def player_color(self, pid: int) -> Optional[Tuple[int, int, int]]:
        p = self.gs.player_by_id(pid)
        if p is None:
            return None
        # Packed ARGB. Replays often serialize 0 or -1 (0xFFFFFFFF) and the live
        # client fills the real colour in SetPlayerColors from tribe/skin.
        # -1 is truthy, so treating it as a stored colour tints every unit white.
        packed = int(p.color) & 0xFFFFFFFF
        if packed not in (0, 0xFFFFFFFF):
            c = packed & 0xFFFFFF
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
        (b) team ``tint`` multiply, (c) horizontal ``flip`` — returning a baked Image ready to
        composite. Results are cached and shared — callers must not mutate the returned Image
        (``paste`` / in-place pixel writes); use ``.copy()`` first if you need to edit.
        Returns None if the sprite is missing."""
        key = (name, tint, bool(flip), round(float(scale), 5))
        hit = self._bake_cache.get(key)
        if hit is not None:
            return hit
        if not self.store.exists(name):
            return None
        try:
            base = self.store.get(name)
        except KeyError:
            return None
        s = SM.render_scale(name) * scale
        nw, nh = max(1, round(base.w * s)), max(1, round(base.h * s))
        if (nw, nh) != (base.w, base.h):
            img = base.resized(nw, nh)
        else:
            img = base.copy()
        if tint is not None:
            img = img.tinted(tint)
        if flip:
            img = img.flipped_x()
        self._bake_cache[key] = img
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
