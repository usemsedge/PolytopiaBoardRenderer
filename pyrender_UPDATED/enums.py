"""Enum value tables — integers match the IL2CPP dump exactly (recon/gamestate_schema.md §5)."""
from enum import IntEnum


class Terrain(IntEnum):
    NONE = 0; WATER = 1; OCEAN = 2; FIELD = 3; MOUNTAIN = 4
    FOREST = 5; ICE = 6; WETLAND = 7; MANGROVE = 8


class Resource(IntEnum):
    NONE = 0; GAME = 1; CROP = 2; FISH = 3; WHALE = 4
    METAL = 5; FRUIT = 6; SPORES = 7; STARFISH = 8; AQUACROP = 9


class Improvement(IntEnum):
    NONE = 0; CITY = 1; RUIN = 2; ROAD = 3; CUSTOMS_HOUSE = 4; FARM = 5
    WINDMILL = 6; FISHING = 7; PORT = 8; HUNTING = 9; CLEAR_FOREST = 10
    BURN_FOREST = 11; LUMBER_HUT = 12; SAWMILL = 13; GROW_FOREST = 14
    HARVEST_FRUIT = 15; WHALE_HUNTING = 16; TEMPLE = 17; FOREST_TEMPLE = 18
    WATER_TEMPLE = 19; MOUNTAIN_TEMPLE = 20; MINE = 21; FORGE = 22
    MONUMENT1 = 23; MONUMENT2 = 24; MONUMENT3 = 25; MONUMENT4 = 26
    MONUMENT5 = 27; MONUMENT6 = 28; MONUMENT7 = 29; ENCHANT_ANIMAL = 30
    ENCHANT_WHALE = 31; SANCTUARY = 32; OUTPOST = 33; ICE_BANK = 34
    ICE_TEMPLE = 35; POLARIS_CLIMATE = 36; FUNGI = 37; ALGAE = 38
    MYCELIUM = 39; BURN_SPORES = 40; CLATHRUS = 41; HIDDEN_SANCTUARY = 42
    HARVEST_SPORES = 43; NULL_BUILDING = 44; CULTIVATE = 45; STAR_FISHING = 46
    LIGHTHOUSE = 47; BRIDGE = 48; AQUAFARM = 49; MARKET = 50; ATOLL = 51
    CANAL = 52; FERTILIZE = 53; LANDFILL = 54; ALGAE_SPAWN = 55


class Unit(IntEnum):
    NONE = 0; SCOUT = 1; WARRIOR = 2; RIDER = 3; KNIGHT = 4; DEFENDER = 5
    SHIP = 6; BATTLESHIP = 7; CATAPULT = 8; ARCHER = 9; MINDBENDER = 10
    SWORDSMAN = 11; GIANT = 12; BUNNY = 13; BOAT = 14; POLYTAUR = 15
    NAVALON = 16; DRAGON_EGG = 17; BABY_DRAGON = 18; FIRE_DRAGON = 19
    AMPHIBIAN = 20; TRIDENTION = 21; MOONI = 22; BATTLE_SLED = 23
    ICE_FORTRESS = 24; ICE_ARCHER = 25; CRAB = 26; GAAMI = 27; HEXAPOD = 28
    DOOMUX = 29; PHYCHI = 30; KITON = 31; EXIDA = 32; CENTIPEDE = 33
    SEGMENT = 34; RAYCHI = 35; SHAMAN = 36; DAGGER = 37; CLOAK = 38
    CLOAK_BOAT = 39; PIRATE = 40; BOMBERSHIP = 41; SCOUTSHIP = 42
    TRANSPORTSHIP = 43; RAMMERSHIP = 44; JUGGERNAUT = 45; MERMAID_WARRIOR = 46
    MERMAID_ARCHER = 47; MERMAID_SWORDSMAN = 48; MERMAID_DEFENDER = 49
    MERMAID_CLOAK = 50; MERMAID_DAGGER = 51; JELLY = 52; SHARK = 53
    SIREN = 54; AQUAPULT = 55; BOOMCHI = 56; ISLAND = 57; CIRU = 58
    MANTIS = 59; BUG_EGG = 60; MOTH = 61; LARVA = 62


class Tribe(IntEnum):
    NONE = 0; NATURE = 1; AIMO = 2; AQUARION = 3; BARDUR = 4; ELYRION = 5
    HOODRICK = 6; IMPERIUS = 7; KICKOO = 8; LUXIDOOR = 9; OUMAJI = 10
    QUETZALI = 11; VENGIR = 12; XINXI = 13; YADAKK = 14; ZEBASI = 15
    POLARIS = 16; CYMANTI = 17


class Skin(IntEnum):
    NONE = -1; DEFAULT = 0; RANGER = 1; NINJA = 2; BAERION = 3; SCHOLAR = 5
    MERCENARY = 7; SFINX = 8; SKELETON = 9; ARTY = 10; PIRATE = 11; AIBO = 12
    URKAZ = 13; IKARUS = 14; DARKELF = 15; SWAMP = 17; MAGMA = 18; CUTE = 19


class MapPreset(IntEnum):
    """dump.cs MapPreset (TypeDef 12153)."""
    NONE = 0; DRYLAND = 1; LAKES = 2; CONTINENTS = 3
    ARCHIPELAGO = 4; WATER_WORLD = 5; PANGEA = 6


class MapSize(IntEnum):
    """dump.cs MapSize (TypeDef 12155). Widths via MapSizeExtensions."""
    NONE = 0; TINY = 1; SMALL = 2; NORMAL = 3; LARGE = 4; HUGE = 5; MASSIVE = 6


# MapSizeExtensions constants (dump.cs 832027–832036).
MAP_SIZE_WIDTH = {
    MapSize.NONE: 0,
    MapSize.TINY: 11,
    MapSize.SMALL: 14,
    MapSize.NORMAL: 16,
    MapSize.LARGE: 18,
    MapSize.HUGE: 20,
    MapSize.MASSIVE: 30,
}
MAP_SIZE_MIN = 11
MAP_SIZE_MAX = 30


class TileEffect(IntEnum):
    NONE = 0; FLOODED = 1; SWAMPED = 2; TENTACLE = 3; ALGAE = 4; FOAM = 5


class CityReward(IntEnum):
    NONE = 0; CITY_WALL = 1; PARK = 2; WORKSHOP = 3; EXPLORER = 4
    BORDER_GROWTH = 5; SUPER_UNIT = 6; RESOURCES = 7; POPULATION_GROWTH = 8
    REBELLION = 11; POISON = 13; TUTORIAL_EXPLORER = 100


class ImprovementEffect(IntEnum):
    DECOMPOSING = 0; ROBBED = 1


class UnitEffect(IntEnum):
    FROZEN = 0; POISONED = 1; BOOSTED = 2; INVISIBLE = 3; BUBBLE = 4
    PETRIFIED = 5; SWIFT = 6; DOUBLE_READY = 7; CHARMED = 8


class GridDirection(IntEnum):
    SW = 0; W = 1; NW = 2; N = 3; NE = 4; E = 5; SE = 6; S = 7; NONE = 8


class CommandType(IntEnum):
    """dump.cs CommandType (TypeDef 10554). Gaps are unused in this build."""
    NONE = 0; BUILD = 1; ATTACK = 2; RECOVER = 3; HEAL_OTHERS = 4
    TRAIN = 5; MOVE = 6; CAPTURE = 7; RESEARCH = 8; DESTROY = 9
    DISBAND = 10; CITY_REWARD = 11; PROMOTE = 13; EXAMINE_RUINS = 14
    END_TURN = 15; UPGRADE = 16; FREEZE_AREA = 17; BREAK_ICE = 18
    SELECT_TRIBE = 19; START_MATCH = 20; STAY = 21; END_MATCH = 22
    HARVEST = 23; EXPLODE = 24; BOOST = 25; DECOMPOSE = 26
    PEACE_TREATY = 27; PEACE_REQUEST_RESPONSE = 28; BREAK_PEACE = 29
    ESTABLISH_EMBASSY = 30; DESTROY_EMBASSY = 32; HIDE = 33; RESIGN = 35
    DISEMBARK = 36; FLOOD = 37; SWARM = 38; CLEAR_TILE_EFFECT = 39


class ActionType(IntEnum):
    """dump.cs ActionType (TypeDef 10517). Gaps are unused in this build."""
    NONE = 0; BUILD = 1; ATTACK = 2; RECOVER = 3; HEAL_OTHERS = 4
    TRAIN = 5; MOVE = 6; RULE_AREA = 7; RESEARCH = 8
    DESTROY_IMPROVEMENT = 9; DISBAND_UNIT = 10; CITY_REWARD = 11
    MEET = 12; PROMOTE = 13; EXAMINE_RUINS = 14; END_TURN = 15
    UPGRADE = 16; FREEZE_AREA = 17; BREAK_ICE = 18; BUILD_ROAD = 19
    CAPTURE_CITY = 20; CITY_LEVEL_UP = 21; UPDATE_ROUTES = 22
    KILL_UNIT = 23; MODIFY_PRODUCTION = 24; EXPLORE = 25
    INCREASE_POPULATION = 26; INCREASE_SCORE = 27; INCREASE_CURRENCY = 28
    START_TURN = 29; SCOUT_MOVE = 30; UPDATE_CITY_CONNECTIONS = 31
    DECREASE_POPULATION = 32; EMBARK = 34; DISEMBARK = 35
    SELECT_TRIBE = 36; GAME_OVER = 37; HEAL = 38; START_MATCH = 39
    IMPROVEMENT_LEVEL_UP = 40; IMPROVEMENT_LEVEL_DOWN = 41; CONVERT = 42
    FREEZE_UNIT = 43; ENABLE_TASK = 44; TASK_COMPLETED = 45
    FREEZE_TILE = 46; CLIMATE_CHANGE = 47; RESELECT = 48
    WIPE_PLAYER = 49; CREATE_RESOURCE = 50; DESTROY_RESOURCE = 51
    MODIFY_SCORE = 52; PASS_PLAYER = 53; CONNECT_CITY = 54
    DISCONNECT_CITY = 55; CHANGE_CITY_CONNECTION = 56; BREAK_ICE_AREA = 57
    EXPAND_CITY = 58; DECREASE_SCORE = 59; END_MATCH = 60
    WIPE_PLAYER_END = 61; END_COMMAND = 62; POISON = 63; EAT = 64
    HARVEST_IMPROVEMENT = 66; BOOST = 68; BOOST_OTHERS = 69
    EXPLODE = 70; DECOMPOSE = 71; RECEIVE_DIPLOMACY_MESSAGE = 72
    PEACE_REQUEST_RESPONSE = 73; PEACE_TREATY = 74; BREAK_PEACE = 75
    ESTABLISH_EMBASSY = 76; REVEAL_CAPITAL = 77; DESTROY_EMBASSY = 79
    HIDE = 80; REVEAL = 81; INFILTRATE = 82; INFILTRATION_REWARD = 83
    RESIGN = 84; RUN_DEFERRED = 85; BUBBLE = 86; FLOOD_TILE = 87
    CLEAR_EFFECT = 88


class CommandTriggerType(IntEnum):
    """dump.cs CommandTriggerType (TypeDef 10609)."""
    NONE = 0; CITY_LEVEL_UP = 1; PEACE_REQUEST = 2


# Sub-layer sort offsets (recon/draworder_color.md §2; MapRenderer constants).
# Within one tile: sortingOrder = rowDepth + offset (0..99 band).
SORT_BORDERS_BACK = 0
SORT_TERRAIN = 1
SORT_TRANSPORT = 2
SORT_TERRAIN_FEATURE = 3
SORT_RESOURCE_OUTLINE = 4
SORT_RESOURCE = 5
SORT_HOUSES = 6
SORT_WALLS = 97
SORT_BUILDINGS = 98
SORT_BORDERS_FRONT = 99

# Unity Sorting Layers above the world tile stack (TagManager order):
#   Units → CityStatusDisplays/Text → UnitStatusDisplays/Text
# Flattened into sublayer ints so a single ascending sort matches layer order.
SORT_UNIT = 100                 # Units sorting layer
SORT_CITY_STATUS = 110          # CityStatusDisplays + CityStatusText
SORT_UNIT_STATUS = 120          # UnitStatusDisplays + UnitStatusText


# Tribe value -> lowercase theme suffix (recon/asset_map.json tribe_theme).
# climate is assumed to hold a Tribe value (the standard 1:1 Polytopia climate->tribe map).
TRIBE_THEME = {
    Tribe.NATURE: "nature", Tribe.AIMO: "aimo", Tribe.AQUARION: "aquarion",
    Tribe.BARDUR: "bardur", Tribe.ELYRION: "elyrion", Tribe.HOODRICK: "hoodrick",
    Tribe.IMPERIUS: "imperius", Tribe.KICKOO: "kickoo", Tribe.LUXIDOOR: "luxidoor",
    Tribe.OUMAJI: "oumaji", Tribe.QUETZALI: "quetzali", Tribe.VENGIR: "vengir",
    Tribe.XINXI: "xinxi", Tribe.YADAKK: "yadakk", Tribe.ZEBASI: "zebasi",
    Tribe.POLARIS: "polaris", Tribe.CYMANTI: "cymanti",
}

SKIN_THEME = {
    Skin.RANGER: "ranger", Skin.NINJA: "ninja", Skin.BAERION: "baerion",
    Skin.SCHOLAR: "scholar", Skin.MERCENARY: "mercenary", Skin.SFINX: "sfinx",
    Skin.SKELETON: "skeleton", Skin.ARTY: "arty", Skin.PIRATE: "pirate",
    Skin.AIBO: "aibo", Skin.URKAZ: "urkaz", Skin.IKARUS: "ikarus",
    Skin.DARKELF: "darkelf", Skin.SWAMP: "swamp", Skin.MAGMA: "magma",
    Skin.CUTE: "cute",
}
