"""Resource component — Tile.RenderResource / UIUtils.GetResourceSprite (recon/resources.md).

Tile-local port of the old layer_resources pipeline.

A tile draws at most one resource sprite from TileData.resource.type (1..9).
The base name comes from SpriteData.ResourceToString(type) and is resolved through
DoSpriteLookup(base, tribe, skin) where tribe/skin come from the tile's climate theme.

Cyan glow: when the viewer (ctx.viewer_id) owns the tile (or for Starfish, regardless
of ownership), AND the viewer's player has the corresponding harvesting tech in
`available_tech`, the resource's _Outline companion sprite is emitted tinted cyan
(#00F5F5, recovered from data.unity3d) at SORT_RESOURCE_OUTLINE, below the resource.
"""
from __future__ import annotations

from typing import List, Optional

import context
import enums as E
from context import Placement

# ResourceData.Type → base sprite string (ResourceToString jump table).
_RESOURCE_BASE = {
    E.Resource.GAME:     "animal",
    E.Resource.CROP:     "ResourceGFX_crop",
    E.Resource.FISH:     "ResourceGFX_fish",
    E.Resource.WHALE:    "ResourceGFX_whale",
    E.Resource.METAL:    "ResourceGFX_metal",
    E.Resource.FRUIT:    "ResourceGFX_fruit",
    E.Resource.SPORES:   "ResourceGFX_spores",
    E.Resource.STARFISH: "ResourceGFX_starfish",
    E.Resource.AQUACROP: "ResourceGFX_aquacrop",
}

# The Game resource ("animal") art reads oversized; render it at reduced size.
ANIMAL_RESOURCE_SCALE = 0.67

# Resource → ImprovementData.Type that harvests it (dump.cs line 777946+).
# When this improvement is already built on the tile, the resource is consumed
# and the glow is suppressed.
_RESOURCE_IMPROVEMENT = {
    E.Resource.GAME:     int(E.Improvement.HUNTING),        # 9
    E.Resource.CROP:     int(E.Improvement.FARM),           # 5
    E.Resource.FISH:     int(E.Improvement.FISHING),        # 7
    E.Resource.WHALE:    int(E.Improvement.WHALE_HUNTING),  # 16
    E.Resource.METAL:    int(E.Improvement.MINE),           # 21
    E.Resource.FRUIT:    int(E.Improvement.HARVEST_FRUIT),  # 15
    E.Resource.SPORES:   int(E.Improvement.HARVEST_SPORES), # 43
    E.Resource.STARFISH: int(E.Improvement.STAR_FISHING),   # 46
    E.Resource.AQUACROP: int(E.Improvement.AQUAFARM),       # 49
}

# Resource → required TechData.Type int (PlayerState.availableTech list).
# Values from TechData.Type enum (dump.cs line 778329+).
_RESOURCE_TECH = {
    E.Resource.GAME:     15,   # Hunting
    E.Resource.CROP:     8,    # Farming
    E.Resource.FISH:     10,   # Fishing
    E.Resource.WHALE:    11,   # Whaling
    E.Resource.METAL:    23,   # Mining
    E.Resource.FRUIT:    16,   # Forestry
    E.Resource.SPORES:   36,   # Recycling  (Cymanti)
    E.Resource.STARFISH: 25,   # FreeDiving (Aquarion / Polaris star-fishing)
    E.Resource.AQUACROP: 39,   # Aquaculture
}

# Cyan outline tint — recovered from data.unity3d float-RGBA at 0x111A8F8.
_CYAN = (0, 245, 245)

# Per-resource position nudge knobs (dx, dy) applied on top of seat_pivot.
RESOURCE_OFFSET = {
    E.Resource.GAME:     (0, 0),
    E.Resource.CROP:     (0, -10),
    E.Resource.FISH:     (0, 20),
    E.Resource.WHALE:    (0, 0),
    E.Resource.METAL:    (0, -10),
    E.Resource.FRUIT:    (0, 5),
    E.Resource.SPORES:   (0, 0),
    E.Resource.STARFISH: (0, 10),
    E.Resource.AQUACROP: (0, 10),
}

# Additional (dx, dy) added on top of RESOURCE_OFFSET for the cyan glow only.
RESOURCE_GLOW_OFFSET = {
    E.Resource.GAME:     (0, 0),
    E.Resource.CROP:     (0, 0),
    E.Resource.FISH:     (0, 0),
    E.Resource.WHALE:    (0, 0),
    E.Resource.METAL:    (0, 0),
    E.Resource.FRUIT:    (0, 0),
    E.Resource.SPORES:   (0, 0),
    E.Resource.STARFISH: (0, 8),
    E.Resource.AQUACROP: (0, 0),
}


def _glow_eligible(ctx, tile, res_type: int) -> bool:
    """True when the cyan harvestable glow should be drawn."""
    viewer = ctx.viewer_id
    if viewer == 0xFF:
        return False   # no viewer — omniscient render, skip glow

    player = ctx.gs.player_by_id(viewer)
    if player is None:
        return False

    # No glow if the harvesting improvement is already built on this tile.
    imp = tile.improvement
    harvest_imp = _RESOURCE_IMPROVEMENT.get(res_type)
    if imp is not None and harvest_imp is not None and imp.type == harvest_imp:
        return False

    # Tech check: viewer must have the harvesting tech researched.
    required = _RESOURCE_TECH.get(res_type)
    if required is None or required not in player.available_tech:
        return False

    # Starfish: glow regardless of tile ownership.
    if res_type == int(E.Resource.STARFISH):
        return True

    # All other resources: tile must be within the viewer's borders.
    return tile.owner == viewer


def items(ctx, x: int, y: int) -> List[Placement]:
    tile = ctx.tile_at(x, y)
    if tile is None:
        return []
    res = tile.resource
    if res is None or tile.improvement is not None:
        return []
    base = _RESOURCE_BASE.get(res.type)
    if base is None:
        return []

    tribe, skin = ctx.tile_theme(tile)
    scale = ANIMAL_RESOURCE_SCALE if base == "animal" else 1.0

    out: List[Placement] = []

    # Resolve the main sprite (no outline lookup here — outline handled below).
    name, _ = ctx.resolve(base, tribe, skin, check_outline=False)
    if name is None:
        return []

    # Cyan glow via _Outline sibling, tinted #00F5F5, when harvestable by viewer.
    kdx, kdy = RESOURCE_OFFSET.get(res.type, (0, 0))

    if _glow_eligible(ctx, tile, res.type):
        gdx, gdy = RESOURCE_GLOW_OFFSET.get(res.type, (0, 0))
        _, outline = ctx.resolve(base, tribe, skin, check_outline=True)
        if outline is not None:
            oimg = ctx.bake(outline, tint=_CYAN, scale=scale)
            if oimg is not None:
                ox, oy = ctx.seat_pivot(outline, oimg.w, oimg.h)
                out.append(Placement(E.SORT_RESOURCE_OUTLINE, oimg,
                                     ox + kdx + gdx, oy + kdy + gdy))

    img = ctx.bake(name, scale=scale)
    if img is None:
        return out
    sx, sy = ctx.seat_pivot(name, img.w, img.h)
    out.append(Placement(E.SORT_RESOURCE, img, sx + kdx, sy + kdy))
    return out
