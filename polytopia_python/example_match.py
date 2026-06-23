"""Build example GameState instances for testing the board renderer."""
from __future__ import annotations

from .enums import (
    CLIMATE_STYLE_TO_TRIBE,
    ImprovementType,
    PLAYER_COLORS,
    ResourceType,
    TerrainType,
    TribeType,
    UnitType,
)
from .game_state import (
    GameSettings,
    GameState,
    GameStateState,
    ImprovementState,
    MapData,
    PlayerState,
    ResourceState,
    TileData,
    UnitState,
    WorldCoordinates,
)

# NW, NE, SW, SE — eight showcase boards, four tribes each.
BOARD_PRESETS: tuple[tuple[TribeType, TribeType, TribeType, TribeType], ...] = (
    (TribeType.Imperius, TribeType.Bardur, TribeType.Kickoo, TribeType.Zebasi),
    (TribeType.Xinxi, TribeType.Hoodrick, TribeType.Luxidoor, TribeType.Vengir),
    (TribeType.Oumaji, TribeType.Quetzali, TribeType.Elyrion, TribeType.Yadakk),
    (TribeType.Aquarion, TribeType.Polaris, TribeType.Cymanti, TribeType.Aimo),
    (TribeType.Imperius, TribeType.Vengir, TribeType.Quetzali, TribeType.Zebasi),
    (TribeType.Bardur, TribeType.Kickoo, TribeType.Hoodrick, TribeType.Oumaji),
    (TribeType.Luxidoor, TribeType.Elyrion, TribeType.Aquarion, TribeType.Xinxi),
    (TribeType.Yadakk, TribeType.Polaris, TribeType.Cymanti, TribeType.Aimo),
)

_CAPITAL_NAMES: dict[TribeType, str] = {
    TribeType.Imperius: "Rome",
    TribeType.Bardur: "Redfort",
    TribeType.Kickoo: "Panasua",
    TribeType.Zebasi: "Zebia",
    TribeType.Xinxi: "Xin-Xi",
    TribeType.Hoodrick: "Hoodrick",
    TribeType.Luxidoor: "Luxidoor",
    TribeType.Vengir: "Vengir",
    TribeType.Oumaji: "Oumaji",
    TribeType.Quetzali: "Quetzali",
    TribeType.Elyrion: "Elyrion",
    TribeType.Yadakk: "Yadakk",
    TribeType.Aquarion: "Aquarion",
    TribeType.Polaris: "Polaris",
    TribeType.Cymanti: "Cymanti",
    TribeType.Aimo: "Aimo",
}


def _blank_map(width: int, height: int, fill: TerrainType = TerrainType.Ocean) -> MapData:
    tiles: list[TileData] = []
    for y in range(height):
        for x in range(width):
            tiles.append(
                TileData(
                    coordinates=WorldCoordinates(x, y),
                    terrain=fill,
                    explorers=[1, 2, 3, 4],
                )
            )
    return MapData(width=width, height=height, tiles=tiles)


def _tile(map_data: MapData, x: int, y: int) -> TileData:
    t = map_data.get_tile_xy(x, y)
    assert t is not None
    return t


def _style_for_tribe(tribe: TribeType) -> int:
    for style, mapped in CLIMATE_STYLE_TO_TRIBE.items():
        if mapped == tribe:
            return style
    return 2


def _patch_player(x: int, y: int) -> int:
    """Assign quadrant ownership on the shared landmass (NW/NE/SW/SE)."""
    west = x < 5
    north = y < 5
    if west and north:
        return 1
    if not west and north:
        return 2
    if west and not north:
        return 3
    return 4


# Diamond land (|x-5|+|y-5|<=4) plus axis tips — 4-adjacent coastal ring is 24 tiles.
_LAND_TIP_TILES = (
    (0, 5),
    (5, 0),
    (5, 10),
    (10, 5),
)

_SHALLOW_WATER_TILES = (
    (0, 4),
    (0, 6),
    (1, 4),
    (1, 6),
    (2, 3),
    (2, 7),
    (3, 2),
    (3, 8),
    (4, 0),
    (4, 1),
    (4, 9),
    (4, 10),
    (6, 0),
    (6, 1),
    (6, 9),
    (6, 10),
    (7, 2),
    (7, 8),
    (8, 3),
    (8, 7),
    (9, 4),
    (9, 6),
    (10, 4),
    (10, 6),
)


def preset_slug(preset: tuple[TribeType, TribeType, TribeType, TribeType]) -> str:
    from .enums import TRIBE_SKIN_SUFFIX

    return "_".join(TRIBE_SKIN_SUFFIX[t] for t in preset)


def build_four_tribe_board(
    nw: TribeType,
    ne: TribeType,
    sw: TribeType,
    se: TribeType,
    *,
    game_name: str | None = None,
) -> GameState:
    """11×11 map — four tribal quadrants with forest, mountain, and fruit each."""
    w, h = 11, 11
    m = _blank_map(w, h)
    cx, cy = 5, 5

    tribes = (
        (1, nw, WorldCoordinates(3, 4)),
        (2, ne, WorldCoordinates(7, 4)),
        (3, sw, WorldCoordinates(3, 7)),
        (4, se, WorldCoordinates(7, 7)),
    )
    tribe_by_player = {pid: tribe for pid, tribe, _ in tribes}

    for y in range(h):
        for x in range(w):
            if abs(x - cx) + abs(y - cy) <= 4 or (x, y) in _LAND_TIP_TILES:
                t = _tile(m, x, y)
                t.terrain = TerrainType.Field
                pid = _patch_player(x, y)
                t.owner = pid
                t.climate = _style_for_tribe(tribe_by_player[pid])

    for x, y in _SHALLOW_WATER_TILES:
        _tile(m, x, y).terrain = TerrainType.Water

    patch_features = (
        (1, (4, 4), (2, 4), (4, 3)),   # NW
        (2, (7, 3), (6, 2), (6, 3)),   # NE
        (3, (4, 6), (2, 6), (4, 8)),   # SW
        (4, (7, 6), (6, 7), (6, 8)),   # SE
    )
    for _pid, forest_xy, mountain_xy, fruit_xy in patch_features:
        _tile(m, *forest_xy).terrain = TerrainType.Forest
        _tile(m, *mountain_xy).terrain = TerrainType.Mountain
        _tile(m, *fruit_xy).resource = ResourceState(type=ResourceType.Fruit)

    player_states: list[PlayerState] = []
    for pid, tribe, cap in tribes:
        style = _style_for_tribe(tribe)
        city_name = _CAPITAL_NAMES.get(tribe, tribe.name)
        cap_tile = _tile(m, cap.x, cap.y)
        cap_tile.capital_of = pid
        cap_tile.improvement = ImprovementState(
            type=ImprovementType.City,
            level=2,
            population=3,
            name=city_name,
            founder=pid,
            founded=1,
        )
        cap_tile.unit = UnitState(
            id=pid,
            owner=pid,
            type=UnitType.Warrior if pid % 2 else UnitType.Swordsman,
            coordinates=cap,
            home=cap,
            health=10,
        )
        for x in range(w):
            for y in range(h):
                t = m.get_tile_xy(x, y)
                if t and t.owner == pid:
                    t.ruling_city_coordinates = cap
                    if t.climate == 0:
                        t.climate = style

        r, g, b = PLAYER_COLORS[pid]
        player_states.append(
            PlayerState(
                id=pid,
                user_name=city_name,
                tribe=tribe,
                currency=8 - pid,
                score=120 - pid * 8,
                start_tile=cap,
                color=(r << 16) | (g << 8) | b,
            )
        )

    if game_name is None:
        game_name = preset_slug((nw, ne, sw, se)).replace("_", " / ")

    return GameState(
        version=116,
        seed=42,
        current_turn=7,
        current_player_index=0,
        current_state=GameStateState.Started,
        settings=GameSettings(game_name=game_name, map_size=w),
        map=m,
        player_states=player_states,
    )


def build_board_preset(index: int) -> GameState:
    """Build one of the eight hard-coded four-tribe showcase boards."""
    nw, ne, sw, se = BOARD_PRESETS[index]
    return build_four_tribe_board(nw, ne, sw, se)


def build_example_match() -> GameState:
    """Default example — first four-tribe preset."""
    return build_board_preset(0)
