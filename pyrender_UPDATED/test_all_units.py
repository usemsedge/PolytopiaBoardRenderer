"""Render all 62 unit types on an 8×8 grid, one per tile.

Units are placed in enum order (SCOUT→LARVA). Water/naval units get OCEAN
terrain; land units get FIELD. Climate per tile is set to the unit's native
tribe so UseClimate parts (rider mount, etc.) resolve correctly.

All units are owned by a single Imperius player (blue tint, Imperius head).

Output: /tmp/test_all_units.png
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
from enums import Terrain, Tribe, Unit

COLS = 8
ROWS = 8

# --------------------------------------------------------------------- water units
# These get OCEAN terrain; all others get FIELD.
_WATER_UNITS = {
    Unit.SHIP, Unit.BATTLESHIP, Unit.BOAT, Unit.CLOAK_BOAT,
    Unit.PIRATE, Unit.BOMBERSHIP, Unit.SCOUTSHIP, Unit.TRANSPORTSHIP,
    Unit.RAMMERSHIP, Unit.JUGGERNAUT,
    Unit.NAVALON, Unit.AMPHIBIAN, Unit.TRIDENTION, Unit.CRAB,
    Unit.JELLY, Unit.SHARK, Unit.SIREN, Unit.AQUAPULT, Unit.ISLAND,
    Unit.MERMAID_WARRIOR, Unit.MERMAID_ARCHER, Unit.MERMAID_SWORDSMAN,
    Unit.MERMAID_DEFENDER, Unit.MERMAID_CLOAK, Unit.MERMAID_DAGGER,
}

# --------------------------------------------------------------------- native tribe per unit
# Sets both owner tribe (for head/body) and climate (for mount/terrain art).
_CYMANTI = {
    Unit.HEXAPOD, Unit.DOOMUX, Unit.PHYCHI, Unit.KITON, Unit.EXIDA,
    Unit.CENTIPEDE, Unit.SEGMENT, Unit.RAYCHI, Unit.BOOMCHI,
    Unit.BUG_EGG, Unit.MOTH, Unit.LARVA,
}
_POLARIS = {
    Unit.MOONI, Unit.BATTLE_SLED, Unit.ICE_FORTRESS, Unit.ICE_ARCHER, Unit.GAAMI,
}
_ELYRION = {
    Unit.POLYTAUR, Unit.DRAGON_EGG, Unit.BABY_DRAGON, Unit.FIRE_DRAGON,
}
_AQUARION = {
    Unit.AMPHIBIAN, Unit.TRIDENTION, Unit.CRAB,
    Unit.MERMAID_WARRIOR, Unit.MERMAID_ARCHER, Unit.MERMAID_SWORDSMAN,
    Unit.MERMAID_DEFENDER, Unit.MERMAID_CLOAK, Unit.MERMAID_DAGGER,
    Unit.JELLY, Unit.SHARK, Unit.SIREN, Unit.AQUAPULT, Unit.ISLAND, Unit.NAVALON,
}
_HOODRICK = {Unit.CIRU}
_BARDUR  = {Unit.BUNNY}


def _tribe_for(unit: Unit) -> int:
    if unit in _CYMANTI:  return int(Tribe.CYMANTI)
    if unit in _POLARIS:  return int(Tribe.POLARIS)
    if unit in _ELYRION:  return int(Tribe.ELYRION)
    if unit in _AQUARION: return int(Tribe.AQUARION)
    if unit in _HOODRICK: return int(Tribe.HOODRICK)
    if unit in _BARDUR:   return int(Tribe.BARDUR)
    return int(Tribe.IMPERIUS)


# --------------------------------------------------------------------- grid
_UNITS = [u for u in Unit if u != Unit.NONE]   # 62 units, enum order

_IMPERIUS_PLAYER = GS.PlayerState(id=1, tribe=int(Tribe.IMPERIUS))


def _make_tile(x: int, y: int) -> GS.TileData:
    idx = y * COLS + x
    if idx >= len(_UNITS):
        return GS.TileData(x=x, y=y, terrain=int(Terrain.FIELD),
                           climate=int(Tribe.IMPERIUS))
    unit_type = _UNITS[idx]
    # Climate stays per-unit so UseClimate parts (mounts, etc.) resolve correctly.
    climate = _tribe_for(unit_type)
    terrain = Terrain.OCEAN if unit_type in _WATER_UNITS else Terrain.FIELD
    passenger = int(Unit.WARRIOR) if unit_type in _WATER_UNITS else None
    unit = GS.UnitState(type=int(unit_type), owner=1, health=10, passenger_type=passenger)
    return GS.TileData(x=x, y=y, terrain=int(terrain), climate=climate, unit=unit)


def build_gamestate() -> GS.GameState:
    tiles = [_make_tile(x, y) for y in range(ROWS) for x in range(COLS)]
    mapdata = GS.MapData(width=COLS, height=ROWS, tiles=tiles)
    # current_player_index out of range → viewer=None → all tiles visible, no outline
    return GS.GameState(map=mapdata, players=[_IMPERIUS_PLAYER], current_player_index=99)


if __name__ == "__main__":
    out = "/tmp/test_all_units.png"
    # Build gamestate first so _PLAYERS is populated
    gs = build_gamestate()
    img = render.render(gs, pad=60)
    img.save_png(out)
    print(f"rendered {COLS}x{ROWS} grid -> {out} ({img.w}x{img.h} px)")
    print()
    print("Grid (row × col, left→right / back→front):")
    for row in range(ROWS):
        names = []
        for col in range(COLS):
            idx = row * COLS + col
            names.append(_UNITS[idx].name if idx < len(_UNITS) else "(empty)")
        print(f"  row {row}: {', '.join(names)}")
