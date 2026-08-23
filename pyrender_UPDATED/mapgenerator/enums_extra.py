"""MapGenerationType — dump.cs MapGenerator.MapGenerationType."""
from __future__ import annotations

from enum import IntEnum

# Re-export map enums from the shared module so `from mapgenerator import MapPreset` works.
from enums import MapPreset, MapSize, MAP_SIZE_WIDTH  # noqa: F401


class MapGenerationType(IntEnum):
    """dump.cs MapGenerator.MapGenerationType."""
    DEFAULT = 0
    TUTORIAL = 1
