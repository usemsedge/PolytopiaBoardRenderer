"""Unit checks for RNG + domain helpers (no full map required)."""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mapgenerator.generator import MapGenerator
from mapgenerator.random_compat import SystemRandom
from mapgenerator.settings import MapGeneratorSettings
from enums import MapPreset


def test_system_random_deterministic() -> None:
    a = SystemRandom(42)
    b = SystemRandom(42)
    seq_a = [a.Next(1000) for _ in range(50)]
    seq_b = [b.Next(1000) for _ in range(50)]
    assert seq_a == seq_b
    # Classic Framework: seed 0 produces a known first InternalSample chain length.
    r = SystemRandom(0)
    assert 0 <= r.Next() <= 0x7FFFFFFF
    assert 0.0 <= r.NextDouble() < 1.0


def test_domain_sizes() -> None:
    assert MapGenerator._domain_grid_side(2) == 2
    assert MapGenerator._domain_grid_side(5) == 3
    assert MapGenerator._domain_grid_side(12) == 4
    assert MapGenerator.MinCapitalDistance(16, 2) >= MapGenerator.MINIMUM_DOMAIN_SIZE
    assert MapGenerator.DomainSize(16, 4) >= MapGenerator.MINIMUM_DOMAIN_SIZE


def test_create_from_preset_wetness_order() -> None:
    dry = MapGeneratorSettings.CreateFromPreset(int(MapPreset.DRYLAND))
    lakes = MapGeneratorSettings.CreateFromPreset(int(MapPreset.LAKES))
    arch = MapGeneratorSettings.CreateFromPreset(int(MapPreset.ARCHIPELAGO))
    water = MapGeneratorSettings.CreateFromPreset(int(MapPreset.WATER_WORLD))
    assert dry.wetness < lakes.wetness < arch.wetness < water.wetness


def main() -> None:
    test_system_random_deterministic()
    test_domain_sizes()
    test_create_from_preset_wetness_order()
    print("ok: random + domain + preset checks")


if __name__ == "__main__":
    main()
