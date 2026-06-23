"""Map coordinate helpers mirroring MapExtensions and MapRenderer (PolytopiaAssembly)."""
from __future__ import annotations

from .game_state import MapData, WorldCoordinates

# MapRenderer constants (dump.cs ~371960)
TILE_WIDTH = 0.9622
TILE_HEIGHT = 0.576
TILE_WIDTH_HALF = 0.4811
TILE_HEIGHT_HALF = 0.288
TILE_HORIZONTAL_OFFSET = 0.0
TILE_VERTICAL_OFFSET = -0.223
DEPTH_INCREASE_PER_ROW = 100

# Sort layer offsets (added to row depth)
BORDERS_BACK_SORT_OFFSET = 0
TERRAIN_SORT_OFFSET = 1
TRANSPORT_SORT_OFFSET = 2
WORLD_OBJECT_SORT_OFFSET = 2
TERRAIN_FEATURE_SORT_OFFSET = 3
RESOURCES_OUTLINE_SORT_OFFSET = 4
RESOURCES_SORT_OFFSET = 5
HOUSES_SORT_OFFSET = 6
WALLS_SORT_OFFSET = 97
BUILDINGS_SORT_OFFSET = 98
BORDERS_FRONT_SORT_OFFSET = 99


def to_position(coords: WorldCoordinates, scale: float = 1.0) -> tuple[float, float]:
    """MapExtensions.ToPosition — isometric grid to world Vector2 (RVA 0x2CC11AC)."""
    x = (coords.x - coords.y) * TILE_WIDTH_HALF * scale + TILE_HORIZONTAL_OFFSET * scale
    y = (coords.x + coords.y) * TILE_HEIGHT_HALF * scale
    return x, y


def get_depth_for_tile(map_data: MapData, coords: WorldCoordinates, sort_offset: int = 0) -> int:
    """MapRenderer.GetDepthForTile — (RVA 0x2D507A4).

    Native Unity: ``height - (x + y) * DEPTH_INCREASE_PER_ROW``.
    PIL composite (y-down, ascending sort): ``(x + y) * 100 + x + sort_offset``.
    """
    return (coords.x + coords.y) * DEPTH_INCREASE_PER_ROW + coords.x + sort_offset


def map_pixel_bounds(width: int, height: int, scale: float) -> tuple[float, float, float, float]:
    """Compute axis-aligned bounds of the isometric map in pixel space."""
    corners = [
        WorldCoordinates(0, 0),
        WorldCoordinates(width - 1, 0),
        WorldCoordinates(0, height - 1),
        WorldCoordinates(width - 1, height - 1),
    ]
    xs = [to_position(c, scale)[0] for c in corners]
    ys = [to_position(c, scale)[1] for c in corners]
    pad = scale * max(TILE_WIDTH, TILE_HEIGHT) * 2
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad
