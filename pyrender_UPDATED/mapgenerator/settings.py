"""MapGeneratorSettings — dump.cs TypeDef 10665."""
from __future__ import annotations

from enums import MapPreset


class MapGeneratorSettings:
    """dump.cs MapGeneratorSettings — field names match C#."""

    DEFAULT_RICHNESS = 1.0
    DEFAULT_WETNESS = 0.45
    DEFAULT_SMOOTH_ITERATIONS = 2
    DEFAULT_PRE_TERRAIN_CITY_DENSITY = 0.3
    DEFAULT_POST_TERRAIN_CITY_DENSITY = 1.0
    DEFAULT_MIN_SUBURB_COUNT = 1
    DEFAULT_MAX_SUBURB_COUNT = 2
    DEFAULT_EMPTY_SPACE_VALUE = 0.5
    DEFAULT_SHALLOW_PERCENT_OF_WATER = 0.0

    def __init__(self) -> None:
        self.wetness: float = self.DEFAULT_WETNESS
        self.richness: float = self.DEFAULT_RICHNESS
        self.smoothIterations: int = self.DEFAULT_SMOOTH_ITERATIONS
        self.preTerrainCityDensity: float = self.DEFAULT_PRE_TERRAIN_CITY_DENSITY
        self.postTerrainCityDensity: float = self.DEFAULT_POST_TERRAIN_CITY_DENSITY
        self.minSuburbCount: int = self.DEFAULT_MIN_SUBURB_COUNT
        self.maxSuburbCount: int = self.DEFAULT_MAX_SUBURB_COUNT
        self.surroundingSpaceValue: float = self.DEFAULT_EMPTY_SPACE_VALUE
        self.shallowPercentOfWater: float = self.DEFAULT_SHALLOW_PERCENT_OF_WATER
        self.equalityIterations: int = 0
        self.equalityLimit: float = 0.0
        self.mapType: int = int(MapPreset.NONE)

    def ToString(self) -> str:
        return (
            f"MapGeneratorSettings: wetness {self.wetness}, "
            f"richness {self.richness}, smoothIterations {self.smoothIterations}"
        )

    def __str__(self) -> str:
        return self.ToString()

    @staticmethod
    def CreateFromPreset(mapPreset: int) -> "MapGeneratorSettings":
        """CreateFromPreset — wetness midpoints from in-game map-type ranges
        (wiki Map Generation; dump DEFAULT_WETNESS=0.45 for Lakes-like default).

        Exact ScriptableObject asset table still Phase-2 unverified against binary.
        """
        s = MapGeneratorSettings()
        s.mapType = int(mapPreset)
        # (wetness, richness, smooth, preCity, postCity, shallowFractionOfWater)
        table = {
            int(MapPreset.NONE): (0.45, 1.0, 2, 0.3, 1.0, 0.0),
            int(MapPreset.DRYLAND): (0.05, 1.0, 2, 0.3, 1.0, 0.0),
            int(MapPreset.LAKES): (0.27, 1.0, 2, 0.3, 1.0, 0.35),
            int(MapPreset.CONTINENTS): (0.55, 1.0, 2, 0.3, 1.0, 0.15),
            int(MapPreset.ARCHIPELAGO): (0.70, 1.0, 3, 0.25, 0.8, 0.20),
            int(MapPreset.WATER_WORLD): (0.95, 1.0, 3, 0.2, 0.6, 0.25),
            int(MapPreset.PANGEA): (0.50, 1.0, 2, 0.35, 1.0, 0.10),
        }
        wet, rich, smooth, pre, post, shallow = table.get(
            int(mapPreset), table[int(MapPreset.NONE)]
        )
        s.wetness = wet
        s.richness = rich
        s.smoothIterations = smooth
        s.preTerrainCityDensity = pre
        s.postTerrainCityDensity = post
        s.shallowPercentOfWater = shallow
        return s
