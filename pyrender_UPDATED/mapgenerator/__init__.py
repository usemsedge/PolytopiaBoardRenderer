"""Python mirror of IL2CPP MapGenerator + MapGeneratorSettings (no PreNaval).

Public API matches the game:

    from mapgenerator import MapGenerator, MapGeneratorSettings
    gen = MapGenerator()
    gen.GenerateWithSeed(seed, state, settings, on_complete)
"""
from __future__ import annotations

from mapgenerator.enums_extra import MapGenerationType, MapPreset, MapSize
from mapgenerator.generator import MapGenerator
from mapgenerator.settings import MapGeneratorSettings

__all__ = [
    "MapGenerator",
    "MapGeneratorSettings",
    "MapGenerationType",
    "MapPreset",
    "MapSize",
]
