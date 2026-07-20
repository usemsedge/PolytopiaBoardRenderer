#!/usr/bin/env python3
"""Build recon/example_gamestate.json from the hand-specified 7x5 scene.

Grid convention (per request): row index = y (top row y=0), column index = x
(left column x=0) -> map is 5 wide x 7 tall. One Imperius player (id 1) owns
everything; both cities are level 2 with no border growth, so each owns its
3x3 founded territory (own tile + 8 neighbours, clipped to the map).
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "recon", "example_gamestate.json")

W, H = 5, 7
OWNER = 1
CLIMATE = 7          # Imperius (themes terrain art)

# Terrain: WATER=1 FIELD=3 MOUNTAIN=4 FOREST=5   (rows = y, cols = x)
_ = 0
WA, FI, MT, FO = 1, 3, 4, 5
TERRAIN = [
    [WA, WA, WA, WA, WA],
    [WA, WA, WA, FI, MT],
    [WA, WA, FI, FI, FO],
    [WA, WA, FI, MT, FO],
    [WA, FI, FI, FI, FI],
    [WA, FI, FI, FI, FI],
    [FI, FI, FI, FI, FI],
]

# Resource: GAME(animal)=1 CROP=2 FISH=3 METAL=5 FRUIT=6 STARFISH=8 AQUACROP=9
RESOURCE = [
    [_, _, _, 8, _],
    [_, _, 3, _, 5],
    [_, 8, _, 6, 1],
    [_, 9, _, 6, _],
    [_, _, 2, _, _],
    [_, _, _, _, _],
    [_, _, _, 2, _],
]

# Improvement: CITY=1 RUIN=2 FARM=5 WINDMILL=6 LUMBER_HUT=12 SAWMILL=13 MARKET=50
CITY, RUIN, FARM, WINDMILL, LUMBER_HUT, SAWMILL, MARKET = 1, 2, 5, 6, 12, 13, 50
IMPROVEMENT = [
    [_, _, _, _, _],
    [_, RUIN, _, _, _],
    [_, _, CITY, _, _],
    [_, _, FARM, _, LUMBER_HUT],
    [_, _, _, MARKET, SAWMILL],
    [_, _, CITY, WINDMILL, _],
    [_, _, _, FARM, _],
]

# Units: (x, y) -> (type, health).  SCOUT=1 WARRIOR=2 KNIGHT=4 CLOAK=38
UNITS = {
    (0, 1): (1, 10),    # scout
    (2, 2): (4, 7),     # knight (stands on the upper city)
    (3, 4): (2, 10),    # warrior
    (1, 5): (38, 5),    # cloak
}

CITIES = [(2, 2), (2, 5)]      # both level 2, no border growth


def owned_tiles():
    """Each city owns its 3x3 founded block (clipped to the map)."""
    owned = {}
    for (cx, cy) in CITIES:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                x, y = cx + dx, cy + dy
                if 0 <= x < W and 0 <= y < H:
                    owned[(x, y)] = (cx, cy)
    return owned


def build():
    owned = owned_tiles()
    tiles = []
    uid = 1
    for y in range(H):
        for x in range(W):
            t = {
                "x": x, "y": y, "terrain": TERRAIN[y][x], "climate": CLIMATE,
                "skin": 0, "altitude": 1,
                "owner": OWNER if (x, y) in owned else 0,
                "explorers": [OWNER],            # fully visible to the single player
            }
            if (x, y) in owned:
                cx, cy = owned[(x, y)]
                t["ruling_city_x"], t["ruling_city_y"] = cx, cy

            res = RESOURCE[y][x]
            if res:
                t["resource"] = {"type": res}

            imp = IMPROVEMENT[y][x]
            if imp == CITY:
                t["improvement"] = {"type": CITY, "level": 2, "founder": OWNER,
                                    "border_size": 1}      # founded, no border growth
            elif imp:
                t["improvement"] = {"type": imp, "level": 1}

            if (x, y) in UNITS:
                utype, hp = UNITS[(x, y)]
                t["unit"] = {"id": uid, "type": utype, "owner": OWNER,
                             "x": x, "y": y, "health": hp}
                uid += 1

            tiles.append(t)

    return {
        "_comment": "Hand-built 7x5 example scene (row=y, col=x). One Imperius "
                    "player owns all; two level-2 cities, no border growth (3x3 each).",
        "current_turn": 1,
        "current_player_index": 0,
        "players": [
            {"id": OWNER, "tribe": 7, "skin_type": 0, "color": 0, "known_players": []},
        ],
        "map": {"width": W, "height": H, "tiles": tiles},
    }


if __name__ == "__main__":
    data = build()
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1)
        f.write("\n")
    nu = sum(1 for t in data["map"]["tiles"] if "unit" in t)
    no = sum(1 for t in data["map"]["tiles"] if t["owner"])
    print(f"wrote {OUT}: {W}x{H} = {len(data['map']['tiles'])} tiles, "
          f"{no} owned, {nu} units, 2 cities")
