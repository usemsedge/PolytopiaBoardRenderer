"""Composite tile components in z-order.

Two public entry points:

  background(ctx, x, y) → (image, ox, oy)
      Terrain + improvements + borders only — no units, no labels.
      Called by render.py in its first pass (all tile backgrounds, back-to-front).

  unit_placements(ctx, x, y) → List[Placement]
      Connector (SORT_UNIT_CONNECTOR) + unit + label placements in tile-local space.
      Sublayers: SORT_UNIT_CONNECTOR, SORT_UNIT, SORT_CITY_STATUS, SORT_UNIT_STATUS.
      render.py sorts these globally by layer then depth
      (Unity: connectors under Units → CityStatus → UnitStatus).

  items(ctx, x, y) → (image, ox, oy)          [kept for tests / direct use]
      Full composite: background + units + labels in one image.

Separating background from units ensures that a unit on tile A is never accidentally
buried under the terrain of tile B when B has a smaller (x+y) depth value and is thus
drawn later (more in front) than A.
"""
from __future__ import annotations

import math

from image import Image
from context import Placement

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

# Enemy-land desat (packed ARGB 0x7FF3F3F3) applies to every background layer
# except territory borders. Units and labels are a separate pass and stay full colour.
_NO_DESAT_COMPONENTS = (create_border,)


def _desat_placements(ctx, tile, placements):
    """Tint placements with RenderTerrain 0x7FF3F3F3 when the tile is enemy land."""
    if not placements or ctx.is_hidden(tile) or not ctx.should_desaturate(tile):
        return placements
    return [
        Placement(p.sublayer, ctx.apply_desat(p.image), p.dx, p.dy)
        for p in placements
    ]


def _background_placements(ctx, x, y, tile):
    """All background-layer placements, with enemy-land desat except borders."""
    if ctx.is_hidden(tile):
        return list(create_terrain.items(ctx, x, y))
    placements = []
    for comp in _BG_COMPONENTS:
        comp_items = list(comp.items(ctx, x, y))
        if comp not in _NO_DESAT_COMPONENTS:
            comp_items = _desat_placements(ctx, tile, comp_items)
        placements.extend(comp_items)
    return placements


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
    return _composite(_background_placements(ctx, x, y, tile))


def unit_placements(ctx, x, y):
    """Unit + label Placements in tile-local space. Empty list when tile is hidden."""
    tile = ctx.tile_at(x, y)
    if tile is None or ctx.is_hidden(tile):
        return []
    result = []
    # Connectors under units (SegmentConnector.LateUpdate / website draw order).
    result.extend(create_unit.connector_items(ctx, x, y))
    result.extend(create_unit.items(ctx, x, y))
    result.extend(create_labels.items(ctx, x, y))
    return result


def items(ctx, x, y):
    """Full tile composite (background + units + labels). Returns (image, ox, oy)."""
    tile = ctx.tile_at(x, y)
    if tile is None:
        return Image.new(1, 1, (0, 0, 0, 0)), 0, 0
    placements = _background_placements(ctx, x, y, tile)
    if not ctx.is_hidden(tile):
        placements.extend(create_unit.connector_items(ctx, x, y))
        placements.extend(create_unit.items(ctx, x, y))
        placements.extend(create_labels.items(ctx, x, y))
    return _composite(placements)
