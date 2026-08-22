"""Composite tile components in z-order.

Two public entry points:

  background(ctx, x, y) → (image, ox, oy)
      Terrain + improvements + borders only — no units, no labels.
      Called by render.py in its first pass (all tile backgrounds, back-to-front).

  unit_placements(ctx, x, y) → List[Placement]
      Unit + label placements in tile-local space (diamond centre = (0,0)).
      Sublayers: SORT_UNIT, SORT_CITY_STATUS, SORT_UNIT_STATUS. render.py sorts
      these globally by layer then depth (Unity: Units → CityStatus → UnitStatus).

  items(ctx, x, y) → (image, ox, oy)          [kept for tests / direct use]
      Full composite: background + units + labels in one image.

Separating background from units ensures that a unit on tile A is never accidentally
buried under the terrain of tile B when B has a smaller (x+y) depth value and is thus
drawn later (more in front) than A.
"""
from __future__ import annotations

import math

from image import Image

import create_terrain
import create_shoreline
import create_transport
import create_resource
import create_border
import create_improvement
import create_unit
import create_labels

# Background-only components (no units, no labels).
# City / market / lighthouse composites come from create_improvement
# (via generated_improvements/).
_BG_COMPONENTS = (
    create_terrain,
    create_shoreline,
    create_transport,
    create_resource,
    create_border,
    create_improvement,
)

# Full component list (for items()).
_ALL_COMPONENTS = _BG_COMPONENTS + (create_unit, create_labels)


def _composite(placements):
    """Bake a sorted placement list into (image, origin_x, origin_y)."""
    if not placements:
        return Image.new(1, 1, (0, 0, 0, 0)), 0, 0
    placements = sorted(placements, key=lambda p: p.sublayer)
    minx = min(dx for (_s, _img, dx, _dy) in placements)
    miny = min(dy for (_s, _img, _dx, dy) in placements)
    maxx = max(dx + img.w for (_s, img, dx, _dy) in placements)
    maxy = max(dy + img.h for (_s, img, _dx, dy) in placements)
    canvas = Image.new(math.ceil(maxx - minx), math.ceil(maxy - miny), (0, 0, 0, 0))
    for (_s, img, dx, dy) in placements:
        canvas.paste(img, round(dx - minx), round(dy - miny))
    return canvas, round(-minx), round(-miny)


def background(ctx, x, y):
    """Terrain + improvements only (no units/labels). Returns (image, ox, oy)."""
    tile = ctx.tile_at(x, y)
    if tile is None:
        return Image.new(1, 1, (0, 0, 0, 0)), 0, 0
    if ctx.is_hidden(tile):
        placements = list(create_terrain.items(ctx, x, y))
    else:
        placements = []
        for comp in _BG_COMPONENTS:
            placements.extend(comp.items(ctx, x, y))
    return _composite(placements)


def unit_placements(ctx, x, y):
    """Unit + label Placements in tile-local space. Empty list when tile is hidden."""
    tile = ctx.tile_at(x, y)
    if tile is None or ctx.is_hidden(tile):
        return []
    result = []
    result.extend(create_unit.items(ctx, x, y))
    result.extend(create_labels.items(ctx, x, y))
    return result


def items(ctx, x, y):
    """Full tile composite (background + units + labels). Returns (image, ox, oy)."""
    tile = ctx.tile_at(x, y)
    if tile is None:
        return Image.new(1, 1, (0, 0, 0, 0)), 0, 0
    if ctx.is_hidden(tile):
        placements = list(create_terrain.items(ctx, x, y))
    else:
        placements = []
        for comp in _ALL_COMPONENTS:
            placements.extend(comp.items(ctx, x, y))
    return _composite(placements)
