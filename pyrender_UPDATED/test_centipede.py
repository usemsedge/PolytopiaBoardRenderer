"""Centipede head + segments with dynamic SegmentConnector stretches.

Layout (y=1 row): head at x=1, segment at x=2 (leader=head), segment at x=3 (leader=seg1).
Also a lone segment at x=5 with no leader (no connector).

Output: /tmp/test_centipede.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import render
import gamestate as GS
from enums import Terrain, Tribe, Unit

TRIBE = int(Tribe.CYMANTI)
OWNER = 1
WIDTH = 7
HEIGHT = 3
ROW = 1

# id, type, x, leader_id, follower_id
_CHAIN = [
    (1, Unit.CENTIPEDE, 1, 0, 2),
    (2, Unit.SEGMENT,   2, 1, 3),
    (3, Unit.SEGMENT,   3, 2, 0),
    (4, Unit.SEGMENT,   5, 0, 0),  # lone — no connector
]


def _make_unit(uid, utype, leader, follower) -> GS.UnitState:
    return GS.UnitState(
        id=int(uid),
        type=int(utype),
        owner=OWNER,
        health=100,
        leader=int(leader),
        follower=int(follower),
    )


def build_gamestate() -> GS.GameState:
    by_x = {x: (uid, utype, leader, follower)
            for uid, utype, x, leader, follower in _CHAIN}
    tiles = []
    for y in range(HEIGHT):
        for x in range(WIDTH):
            unit = None
            if y == ROW and x in by_x:
                uid, utype, leader, follower = by_x[x]
                unit = _make_unit(uid, utype, leader, follower)
            tiles.append(GS.TileData(
                coordinates=GS.WorldCoordinates(x, y),
                terrain=int(Terrain.FIELD),
                climate=TRIBE,
                explorers=[OWNER],
                unit=unit,
            ))
    return GS.GameState(
        map=GS.MapData(width=WIDTH, height=HEIGHT, tiles=tiles),
        player_states=[GS.PlayerState(id=OWNER, tribe=TRIBE)],
        current_player_index=0,
    )


if __name__ == "__main__":
    out = "/tmp/test_centipede.png"
    img = render.render(build_gamestate(), pad=40)
    img.save_png(out)
    print(f"rendered -> {out} ({img.w}x{img.h})")
    print("chain: head@1 —conn— seg@2 —conn— seg@3 ; lone seg@5")
