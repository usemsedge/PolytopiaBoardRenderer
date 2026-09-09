"""Render one Imperius warrior per column, each carrying a different visual modifier.

Column layout (x = 0..11, all in middle row y=1):
  x=0   untouched     !moved !attacked → cyan outline + white icon ring
  x=1   moved only    moved, no adjacent enemy → grey wash (dash needs a target)
  x=2   attacked only !moved, attacked → cyan outline, no white ring
  x=3   exhausted     moved+attacked → grey wash, no outline, no white ring
  x=4   Frozen        tint + UnitFrozen frame
  x=5   Poisoned      tint + UnitPoisoned frame
  x=6   Boosted       orange tint + UnitBoosted frame
  x=7   Petrified     dark tint + UnitPetrified frame
  x=8   Invisible     translucent (owner view)
  x=9   Swift         tint + UnitSwift frame
  x=10  Bubble        bubble frame
  x=11  moved+Frozen  Frozen RGB @ strength 0.4

Viewer/perspective is the warrior owner (player 1) so outline and icon ring fire.
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
WIDTH  = 12
HEIGHT = 3           # units in middle row y=1
UNIT_ROW = 1

# Per-column (warrior, effects list, moved flag, attacked flag)
_COLUMNS = [
    # x   effects                        moved  attacked
    (0,   [],                             False, False),
    (1,   [],                             True,  False),
    (2,   [],                             False, True),
    (3,   [],                             True,  True),
    (4,   [UnitEffect.FROZEN],            False, False),
    (5,   [UnitEffect.POISONED],          False, False),
    (6,   [UnitEffect.BOOSTED],           False, False),
    (7,   [UnitEffect.PETRIFIED],         False, False),
    (8,   [UnitEffect.INVISIBLE],         False, False),
    (9,   [UnitEffect.SWIFT],             False, False),
    (10,  [UnitEffect.BUBBLE],            False, False),
    (11,  [UnitEffect.FROZEN],            True,  False),
]

_UNIT_POSITIONS = {x for x, *_ in _COLUMNS}


def _make_unit(x: int) -> GS.UnitState:
    entry = next(row for row in _COLUMNS if row[0] == x)
    _, effects, moved, attacked = entry
    return GS.UnitState(
        type=int(Unit.WARRIOR),
        owner=OWNER,
        health=100,
        moved=moved,
        attacked=attacked,
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
    img = render.render(gs, pad=40, player_id=OWNER)
    img.save_png(out)
    print(f"rendered {WIDTH}x{HEIGHT} board -> {out} ({img.w}x{img.h} px)")
    print()
    print("Columns left→right:")
    for x, effects, moved, attacked in _COLUMNS:
        tags = [e.name for e in effects]
        if moved:
            tags.insert(0, "moved")
        if attacked:
            tags.insert(0, "attacked")
        print(f"  x={x:2d}  {', '.join(tags) or 'untouched'}")
