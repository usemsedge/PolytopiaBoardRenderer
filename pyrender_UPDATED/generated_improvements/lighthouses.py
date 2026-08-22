"""Procedural LightHouse tower — BuildingTowerHelper composite.

One white drum with a tribe-tinted centre gem per discovering player + lantern
roof. Layer 0 (untinted base drum) is not drawn. Discovery prefers
``tile.explorers``; if empty, players listing LightHouse in
``built_unique_improvements``.

Geometry mirrors Market SetupInternal (discoverer drums only, no base layer):
  section i  localY = sectionBaseY + i * sectionHeight
  roof       localY = sectionBaseY + max(0, n-1) * sectionHeight + roofOffsetY
"""
from __future__ import annotations

import json
import math
import os
from typing import List, Optional, Tuple

import enums as E
import projection as P
import spritemeta as SM
from image import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

with open(os.path.join(_ROOT, "sprite_reg.json")) as _f:
    _SPRITE_REG = json.load(_f)

_LIGHTHOUSE_MAX = 16
_LIGHTHOUSE_BASE_Y = 0.05
_LIGHTHOUSE_SECTION_H = 0.22       # world Y between stacked drums
_LIGHTHOUSE_ROOF_OFF = 0.16        # roof above the last drum
_LIGHTHOUSE_SCALE = (0.7, 0.7)
# Pixel nudge for the lantern roof (top segment), applied after world seating.
# Positive = down on screen (same convention as shoreline/border knobs).


def _lighthouse_discoverers(ctx, tile) -> List[int]:
    """Player ids who discovered this lighthouse, bottom → top (max 8).

    Prefer ``tile.explorers`` (per-instance visits). If that list is empty,
    fall back to players who have LightHouse in ``built_unique_improvements``.
    """
    found: List[int] = []
    seen = set()
    for pid in tile.explorers:
        if pid and pid not in seen and ctx.gs.player_by_id(pid) is not None:
            found.append(pid)
            seen.add(pid)
    if not found:
        kind = int(E.Improvement.LIGHTHOUSE)
        for p in ctx.gs.player_states:
            if kind in p.built_unique_improvements and p.id not in seen:
                found.append(p.id)
                seen.add(p.id)
    return found[:_LIGHTHOUSE_MAX]


def _lighthouse_pivot(name: str) -> Tuple[float, float]:
    r = _SPRITE_REG.get(name)
    if r:
        return tuple(r["pivot"])
    return SM.pivot(name) or (0.5, 0.5)


def _composite_tower(ctx, draw: List[tuple]):
    """Bake world-placed tower parts into one image.

    ``draw`` entries are
    ``(sprite, world_x, world_y, scale_xy, tint_rgb|None[, pixel_dy])``.
    Optional ``pixel_dy`` is a screen-space nudge (+ = down) applied after
    pivot seating. Returns ``(image, origin_x, origin_y)``.
    """
    PPU = P.PPU
    placed = []
    minx = miny = 1e18
    maxx = maxy = -1e18
    for entry in draw:
        sprite, px, py, scale, tint = entry[:5]
        pixel_dy = entry[5] if len(entry) > 5 else 0
        name = ctx.resolve(sprite, 0, 0)[0] or sprite
        if not ctx.exists(name):
            continue
        img = ctx.bake(name, tint=tint)
        if img is None:
            continue
        dw = max(1, round(img.w * scale[0]))
        dh = max(1, round(img.h * scale[1]))
        if dw != img.w or dh != img.h:
            img = img.resized(dw, dh)
        pvx, pvy = _lighthouse_pivot(name)
        piv_x = px * PPU
        piv_y = -py * PPU
        tlx = piv_x - pvx * dw
        tly = piv_y - (1.0 - pvy) * dh + pixel_dy
        placed.append((img, tlx, tly))
        minx = min(minx, tlx); miny = min(miny, tly)
        maxx = max(maxx, tlx + dw); maxy = max(maxy, tly + dh)

    if not placed:
        return None
    W = int(math.ceil(maxx - minx))
    H = int(math.ceil(maxy - miny))
    canvas = Image.new(W, H, (0, 0, 0, 0))
    for img, tlx, tly in placed:
        canvas.paste(img, round(tlx - minx), round(tly - miny))
    return canvas, -minx, -miny


def build(ctx, tile) -> Optional[Tuple[Image, float, float]]:
    """Composite the lighthouse tower.

    Returns ``(image, origin_x, origin_y)`` or None. Each discoverer adds one
    untinted white ``lighthouse_section`` plus a tribe-tinted
    ``lighthouse_section_tint`` gem. The lantern roof is always present; the
    untinted base drum (layer 0) is not drawn.
    """
    discoverers = _lighthouse_discoverers(ctx, tile)
    scale = _LIGHTHOUSE_SCALE
    n = len(discoverers)
    draw: List[tuple] = []
    for i, pid in enumerate(discoverers):
        y = _LIGHTHOUSE_BASE_Y + i * _LIGHTHOUSE_SECTION_H
        tint = ctx.player_color(pid)
        draw.append(("lighthouse_section", 0.0, y, scale, None))
        draw.append(("lighthouse_section_tint", 0.0, y, scale, tint))
    roof_y = (_LIGHTHOUSE_BASE_Y
              + max(0, n - 1) * _LIGHTHOUSE_SECTION_H
              + _LIGHTHOUSE_ROOF_OFF)
    draw.append(("lighthouse_roof", 0.0, roof_y, scale, None, 0))
    return _composite_tower(ctx, draw)
