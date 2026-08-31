"""Terrain component: base surface + features + fog, in TILE-LOCAL space.

Ported faithfully from pyrender/layers.py (terrain_items, _base_terrain_name,
_water_recess, _ppu_scaled, fog_items, _trim_pivot) onto the create_* interface
in context.py. Replaces the old Item/global-sort design: this returns baked
Images placed at tile-local top-lefts (diamond centre = origin (0,0), +y down).

Faithful to Tile.RenderTerrain + TerrainRenderer.UpdateGraphics:
  - base terrain (or `hidden` fog when the tile is hidden)  -> SORT_TERRAIN (1)
  - mountain / forest / algae feature toppers               -> SORT_TERRAIN_FEATURE (3)

Seating maps the old canvas-coord placement (frame.anchor + place_base/place_planted)
into local space, where the anchor is the origin (0,0):
  - place_base   -> ctx.seat_base   (full-tile diamond centre)
  - place_planted-> ctx.seat_planted (horizontally centred, bottom at foot)

Scale: the old code pre-scaled feature/fog sprites by SM.render_scale via _ppu_scaled;
ctx.bake already applies render_scale, so features bake at the default scale=1.0 (no
extra scale beyond render_scale). The base terrain sprite was NOT ppu-scaled in the
old code, but bake applies render_scale uniformly — for terrain base sprites that is
the measured world scale, which is the correct local size to tessellate.

Tint: enemy-owned land (not water/ocean/ice) gets a mild opaque dim (~0.85×)
matching live boards; own / unowned / omniscient view stay full bright.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional, Tuple

import context
import enums as E
import projection as P
import spritemeta as SM
from context import Placement
from image import Image

# Trim-corrected sprite pivots (against the alpha-trimmed PNG). m_Pivot in the bundle is
# normalized to the UNtrimmed rect, so the raw centre (0.5,0.5) misplaces trimmed art;
# sprite_reg.json carries the pivot recomputed in trimmed-PNG space.
_HERE = os.path.dirname(os.path.abspath(__file__))
try:
    with open(os.path.join(_HERE, "sprite_reg.json")) as _f:
        _SPRITE_REG = json.load(_f)
except Exception:
    _SPRITE_REG = {}

# Manual pixel nudge applied on top of the source-faithful fog seat: (dx, dy), +x = right,
# +y = down. (0, 0) = exactly the trim-corrected pivot placement. Hand-tuned offset only.
FOG_OFFSET_PX = (3, 17)

# Per-mountain-sprite vertical nudge (pixels, + = down) on top of seat_base.
# Keyed by the resolved sprite name from DoSpriteLookup("mountain", …); missing → 0.
MOUNTAIN_DY = {
    "mountain_aimo": 0,
    "mountain_aquarion": 0,
    "mountain_bardur": 0,
    "mountain_cute": 0,
    "mountain_cymanti": 0,
    "mountain_darkelf": 0,
    "mountain_elyrion": 0,
    "mountain_hoodrick": 0,
    "mountain_imperius": 0,
    "mountain_kickoo": -20,
    "mountain_luxidoor": 0,
    "mountain_magma": 0,
    "mountain_mercenary": 0,
    "mountain_oumaji": 0,
    "mountain_polaris": 0,
    "mountain_quetzali": 0,
    "mountain_swamp": 0,
    "mountain_vengir": 0,
    "mountain_xinxi": 0,
    "mountain_yadakk": 0,
    "mountain_zebasi": 0,
}

# RenderTerrain desaturate tint (packed ARGB 0x7FF3F3F3 ÷ 255).
# Engine multiplies sprite by RGBA(0.953, 0.953, 0.953, 0.498). Over a dark
# clear that would crush to ~0.48×; live boards read ~0.84× on enemy grass, so
# bake a mild opaque RGB scale that matches the screenshot (keep alpha solid
# for isometric paste on a transparent canvas).
_DESAT_FACTOR = 1.00


def _trim_pivot(name: str) -> Tuple[float, float]:
    """Trimmed-PNG pivot (bottom-left origin, normalized); falls back to rect pivot then centre."""
    r = _SPRITE_REG.get(name)
    if r:
        return tuple(r["pivot"])
    return SM.pivot(name) or (0.5, 0.5)


def _should_desaturate(ctx: context.TileContext, tile) -> bool:
    """Enemy-owned land dim — RenderTerrain ownership / IsWater / Ice gates."""
    if ctx.viewer_id == 0xFF:
        return False
    owner = int(tile.owner)
    if owner == 0 or owner == ctx.viewer_id:
        return False
    if tile.terrain in (E.Terrain.WATER, E.Terrain.OCEAN, E.Terrain.ICE):
        return False
    return True


def _maybe_desat(img: Image, desat: bool) -> Image:
    if not desat:
        return img
    c = max(0, min(255, int(round(_DESAT_FACTOR * 255))))
    return img.tinted((c, c, c))


def _base_terrain_name(ctx: context.TileContext, tile) -> Optional[str]:
    """Base surface sprite, faithful to TerrainRenderer.UpdateGraphics (0x2CDBD9C).

    Water(1)/Ocean(2)/Ice(6) each take their own sprite family. Every other terrain
    (Field/Mountain/Forest/Wetland/Mangrove/None) uses the land base, which is "ground"
    unless the tile is Flooded -> "wetland" (or "wetland_swamp" when also Swamped). The
    Flooded override lives ONLY in the land branch; water/ocean/ice are never reclassified.
    Then DoSpriteLookup themes by the tile's climate tribe/skin.
    """
    t = tile.terrain
    tribe, skin = ctx.tile_theme(tile)
    if t == E.Terrain.WATER:
        base = "water"
    elif t == E.Terrain.OCEAN:
        base = "ocean"
    elif t == E.Terrain.ICE:
        base = "ice"
    else:  # FIELD / MOUNTAIN / FOREST / WETLAND / MANGROVE / NONE -> land base
        if E.TileEffect.FLOODED in tile.effects:
            base = "wetland_swamp" if E.TileEffect.SWAMPED in tile.effects else "wetland"
        else:
            base = "ground"
    name, _ = ctx.resolve(base, tribe, skin)
    return name


def _water_recess(ctx: context.TileContext, water_name: str) -> int:
    """Recession (px) of a water/ocean surface below the land surface.

    The game positions every terrain tile at the same world point with Z=0; the recession
    is encoded in the sprite art (land and water share a common underground base, the water
    block is shorter, so its surface sits lower by exactly the block-height difference).
    We recover that from the RAW sprites (no magic constant) and then scale it by the base
    sprite's render-scale so it stays proportional to the render-scaled (baked) base.
    """
    if not (ctx.exists("ground") and ctx.exists(water_name)):
        return 0
    g = ctx.store.get("ground")
    w = ctx.store.get(water_name)
    surf = lambda im: im.h * P.diamond_center_pivot_y(im)  # surface above sprite bottom
    raw = max(0, round(surf(g) - surf(w)))
    return round(raw * SM.render_scale(water_name))


def items(ctx: context.TileContext, x: int, y: int) -> List[Placement]:
    """One tile's terrain stack (or fog if hidden), in tile-local coordinates."""
    tile = ctx.tile_at(x, y)
    if tile is None:
        return []

    # --- fog of war (hidden tile shows only the `hidden` sprite IN PLACE OF terrain) ---
    if ctx.is_hidden(tile):
        return _fog_items(ctx)

    out: List[Placement] = []
    tribe, skin = ctx.tile_theme(tile)
    is_water_surface = tile.terrain in (E.Terrain.WATER, E.Terrain.OCEAN)
    desat = _should_desaturate(ctx, tile)

    # --- base surface (SORT_TERRAIN +1) ---
    recess = 0
    name = _base_terrain_name(ctx, tile)
    if name:
        img = ctx.bake(name)
        if img is not None:
            img = _maybe_desat(img, desat)
            left, top = ctx.seat_base(name, img.w, img.h)
            if is_water_surface:
                # Recess by the art-derived block-height difference so a recessed water
                # tile sits lower than its up-screen land neighbour (which then reads as
                # shore/cliff). Same recess is reused by an algae overlay below.
                recess = _water_recess(ctx, name)
                top += recess
            out.append(Placement(E.SORT_TERRAIN, img, left, top))

    # --- feature "toppers" (SORT_TERRAIN_FEATURE +3) ---
    # ctx.bake already applies SM.render_scale, which is exactly what the old _ppu_scaled
    # did; pass no extra scale.
    if tile.terrain == E.Terrain.MOUNTAIN:
        # Mountain anchors by its base-diamond centre (uniform scale keeps the pivot centred).
        feat, _ = ctx.resolve("mountain", tribe, skin)
        if feat:
            fimg = ctx.bake(feat)
            if fimg is not None:
                fimg = _maybe_desat(fimg, desat)
                fl, ft = ctx.seat_base(feat, fimg.w, fimg.h)
                ft += MOUNTAIN_DY.get(feat, 0)
                out.append(Placement(E.SORT_TERRAIN_FEATURE, fimg, fl, ft))
    elif tile.terrain == E.Terrain.FOREST:
        # Forest is a tree cluster planted on the diamond surface (foot = FEATURE_FOOT).
        feat, _ = ctx.resolve("Forest", tribe, skin)
        if feat:
            fimg = ctx.bake(feat)
            if fimg is not None:
                fimg = _maybe_desat(fimg, desat)
                fl, ft = ctx.seat_planted(fimg.w, fimg.h, foot=context.FEATURE_FOOT)
                out.append(Placement(E.SORT_TERRAIN_FEATURE, fimg, fl, ft))

    # Algae is an EFFECT overlay (independent of terrain type), so it co-exists with the
    # water/ocean base it rides — same base-diamond seat and the same water recess.
    if E.TileEffect.ALGAE in tile.effects:
        alg, _ = ctx.resolve("algae", tribe, skin)
        if alg:
            aimg = ctx.bake(alg)
            if aimg is not None:
                aimg = _maybe_desat(aimg, desat)
                al, at = ctx.seat_base(alg, aimg.w, aimg.h)
                out.append(Placement(E.SORT_TERRAIN_FEATURE, aimg, al, at + recess))

    return out


def _fog_items(ctx: context.TileContext) -> List[Placement]:
    """Fog of war: the single `hidden` sprite seated full-tile, at SORT_TERRAIN.

    The fogOfWarRenderer shares the base terrain renderer's transform and sort (depth+1),
    drawing `hidden` like any tile sprite: its pivot lands at the diamond-centre anchor and
    the PNG is drawn at its measured render scale. ctx.bake applies render_scale; the seat
    uses the trim-corrected pivot (m_Pivot is normalized to the untrimmed rect, so the raw
    centre lifts the trimmed cloud too high) plus a hand-tuned FOG_OFFSET_PX nudge.
    """
    img = ctx.bake("hidden")
    if img is None:
        return []
    nw, nh = img.w, img.h
    pvx, pvy = _trim_pivot("hidden")
    # In local space the anchor (tile transform / diamond-centre) is the origin (0, 0).
    left = round(-pvx * nw + FOG_OFFSET_PX[0])      # sprite pivot lands at the anchor (+nudge)
    top = round(-(1.0 - pvy) * nh + FOG_OFFSET_PX[1])
    return [Placement(E.SORT_TERRAIN, img, left, top)]
