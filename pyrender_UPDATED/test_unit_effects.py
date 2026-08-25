"""Render one Imperius warrior per column, each carrying a different visual modifier.

Column layout (x = 0..10, all in middle row y=1):
  x=0   baseline      untouched, no effects → outline visible (viewer owns unit)
  x=1   exhausted     unit.moved=True, no effects → grey overlay, no outline
  x=2   Frozen        effect 0 → blue-white overlay
  x=3   Poisoned      effect 1 → green overlay
  x=4   Boosted       effect 2 → purple overlay
  x=5   Petrified     effect 5 → near-black overlay
  x=6   Invisible     effect 3 → translucent (viewer = owner; enemy view skips render)
  x=7   Swift         effect 6 → no body overlay in current impl
  x=8   DoubleReady   effect 7 → no body overlay in current impl
  x=9   Charmed       effect 8 → no body overlay in current impl
  x=10  moved+Frozen  unit.moved=True + effect 0 → Frozen takes priority over grey

Viewer is set to the warrior owner (player 1) so outline and invisible-alpha both fire.
Output: /tmp/test_unit_effects.png
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
from enums import Terrain, Tribe, Unit, UnitEffect

TRIBE  = int(Tribe.IMPERIUS)
OWNER  = 1           # player id — also the viewer
WIDTH  = 11
HEIGHT = 3           # units in middle row y=1
UNIT_ROW = 1

# Per-column (warrior, effects list, moved flag)
_COLUMNS = [
    # x   effects                        moved
    (0,   [],                             False),   # baseline (outline shown)
    (1,   [],                             True),    # exhausted grey
    (2,   [UnitEffect.FROZEN],            False),   # blue-white
    (3,   [UnitEffect.POISONED],          False),   # green
    (4,   [UnitEffect.BOOSTED],           False),   # purple
    (5,   [UnitEffect.PETRIFIED],         False),   # near-black
    (6,   [UnitEffect.INVISIBLE],         False),   # translucent (owner view)
    (7,   [UnitEffect.SWIFT],             False),   # no body overlay
    (8,   [UnitEffect.DOUBLE_READY],      False),   # no body overlay
    (9,   [UnitEffect.CHARMED],           False),   # no body overlay
    (10,  [UnitEffect.FROZEN],            True),    # Frozen wins over grey
]

_UNIT_POSITIONS = {x for x, *_ in _COLUMNS}


def _make_unit(x: int) -> GS.UnitState:
    entry = next(row for row in _COLUMNS if row[0] == x)
    _, effects, moved = entry
    return GS.UnitState(
        type=int(Unit.WARRIOR),
        owner=OWNER,
        health=100,
        moved=moved,
        effects=[int(e) for e in effects],
    )


def _tile(x: int, y: int) -> GS.TileData:
    unit = _make_unit(x) if y == UNIT_ROW and x in _UNIT_POSITIONS else None
    return GS.TileData(
        coordinates=GS.WorldCoordinates(x, y),
        terrain=int(Terrain.FIELD),
        climate=TRIBE,
        explorers=[OWNER],   # fully visible to the viewer
        unit=unit,
    )


def build_gamestate() -> GS.GameState:
    tiles = [_tile(x, y) for y in range(HEIGHT) for x in range(WIDTH)]
    mapdata = GS.MapData(width=WIDTH, height=HEIGHT, tiles=tiles)
    # Player 1 is both the warrior owner and the viewer.
    players = [GS.PlayerState(id=OWNER, tribe=TRIBE)]
    return GS.GameState(map=mapdata, player_states=players, current_player_index=0)


if __name__ == "__main__":
    out = "/tmp/test_unit_effects.png"
    gs = build_gamestate()
    img = render.render(gs, pad=40)
    img.save_png(out)
    print(f"rendered {WIDTH}x{HEIGHT} board -> {out} ({img.w}x{img.h} px)")
    print()
    print("Columns left→right:")
    for x, effects, moved in _COLUMNS:
        tags = [e.name for e in effects]
        if moved:
            tags.insert(0, "moved")
        print(f"  x={x:2d}  {', '.join(tags) or 'baseline'}")
