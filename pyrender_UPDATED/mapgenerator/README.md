# MapGenerator Python mirror

Signature-faithful port of IL2CPP `MapGenerator` + `MapGeneratorSettings`
(no PreNaval). Uses `gamestate` / `enums` types from `pyrender_UPDATED`.

## Status: complete for practical use

| Item | Status |
|------|--------|
| Dump signatures + C# method names (incl. typos) | done |
| `Generate` / `GenerateWithSeed` → mutate `state.map` | done |
| Noise presets (Dryland / Lakes / Pangea) | done |
| Island presets (Continents / Archipelago / WaterWorld) | done |
| Capitals, villages, climates, ocean, resources, ruins, lighthouses | done |
| `.NET` Framework `System.Random` + render/dump harnesses | done |
| Seed-bit parity vs game binary | **blocked** — dump RVAs misaligned in this Mac `il2cpp` section |

## Usage

```bash
cd pyrender_UPDATED
python3 -m mapgenerator.test_unit
python3 -m mapgenerator.test_smoke
python3 -m mapgenerator.dump_seed --seed 12345 --preset continents --size normal -o /tmp/map.json
python3 -m mapgenerator.render_seed --seed 42 --preset continents -o /tmp/mapgen_continents.png
python3 -m mapgenerator.render_montage --seed 42 --size tiny -o /tmp/mapgen_montage.png
```

```python
from gamestate import GameState, GameSettings, PlayerState
from enums import MapPreset, MapSize, Tribe
from mapgenerator import MapGenerator, MapGeneratorSettings

state = GameState(
    version=1,
    settings=GameSettings(map_size=int(MapSize.NORMAL), map_preset=int(MapPreset.DRYLAND)),
    player_states=[
        PlayerState(id=1, tribe=int(Tribe.IMPERIUS), has_chosen_tribe=True),
        PlayerState(id=2, tribe=int(Tribe.BARDUR), has_chosen_tribe=True),
    ],
)
settings = MapGeneratorSettings.CreateFromPreset(int(MapPreset.DRYLAND))
MapGenerator().GenerateWithSeed(12345, state, settings, lambda: None)
```

## Notes

- `CreateFromPreset` wetness follows in-game map-type ranges (Dryland≪WaterWorld).
- Capital domains: 4 / 9 / 16 quadrants by player count (wiki Map Generation).
- Continents take climate from their capital owner; villages stay on land and spaced from capitals.
- `SystemRandom` mirrors classic .NET Framework subtractive RNG (MBIG/MSEED).
- Dump RVAs in `il2cpp_dump/dump.cs` (e.g. GenerateInternal `0x69CF40`) do **not**
  align to method prologues in `GameAssembly_arm64.dylib`’s `il2cpp` section for this
  build — re-bind addresses before claiming tile-exact parity.
