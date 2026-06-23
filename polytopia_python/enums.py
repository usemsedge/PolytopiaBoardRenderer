"""Enums from GameLogicAssembly (IL2CPP dump.cs, Game v116)."""
from __future__ import annotations

from enum import IntEnum, IntFlag


class GameStateState(IntEnum):
    Unknown = 0
    Lobby = 1
    Started = 2
    FinalTurn = 3
    Ended = 4


class TerrainType(IntEnum):
    None_ = 0
    Water = 1
    Ocean = 2
    Field = 3
    Mountain = 4
    Forest = 5
    Ice = 6
    Wetland = 7
    Mangrove = 8


class TileEffectType(IntEnum):
    None_ = 0
    Flooded = 1
    Swamped = 2
    Tentacle = 3
    Algae = 4


class ImprovementType(IntEnum):
    None_ = 0
    City = 1
    Ruin = 2
    Road = 3
    CustomsHouse = 4
    Farm = 5
    Windmill = 6
    Fishing = 7
    Port = 8
    Hunting = 9
    ClearForest = 10
    BurnForest = 11
    LumberHut = 12
    Sawmill = 13
    GrowForest = 14
    HarvestFruit = 15
    WhaleHunting = 16
    Temple = 17
    ForestTemple = 18
    WaterTemple = 19
    MountainTemple = 20
    Mine = 21
    Forge = 22
    Monument1 = 23
    Monument2 = 24
    Monument3 = 25
    Monument4 = 26
    Monument5 = 27
    Monument6 = 28
    Monument7 = 29
    EnchantAnimal = 30
    EnchantWhale = 31
    Sanctuary = 32
    Outpost = 33
    IceBank = 34
    IceTemple = 35
    PolarisClimate = 36
    Fungi = 37
    Algae = 38
    Mycelium = 39
    BurnSpores = 40
    Clathrus = 41
    HiddenSanctuary = 42
    HarvestSpores = 43
    NullBuilding = 44
    Cultivate = 45
    StarFishing = 46
    LightHouse = 47
    Bridge = 48
    Aquafarm = 49
    Market = 50
    Atoll = 51
    Canal = 52
    Fertilize = 53
    LandFill = 54
    AlgaeSpawn = 55


class ResourceType(IntEnum):
    None_ = 0
    Game = 1
    Crop = 2
    Fish = 3
    Whale = 4
    Metal = 5
    Fruit = 6
    Spores = 7
    Starfish = 8
    AquaCrop = 9


class UnitType(IntEnum):
    None_ = 0
    Scout = 1
    Warrior = 2
    Rider = 3
    Knight = 4
    Defender = 5
    Ship = 6
    Battleship = 7
    Catapult = 8
    Archer = 9
    MindBender = 10
    Swordsman = 11
    Giant = 12
    Bunny = 13
    Boat = 14
    Polytaur = 15
    Navalon = 16
    DragonEgg = 17
    BabyDragon = 18
    FireDragon = 19
    Amphibian = 20
    Tridention = 21
    Mooni = 22
    BattleSled = 23
    IceFortress = 24
    IceArcher = 25
    Crab = 26
    Gaami = 27
    Hexapod = 28
    Doomux = 29
    Phychi = 30
    Kiton = 31
    Exida = 32
    Centipede = 33
    Segment = 34
    Raychi = 35
    Shaman = 36
    Dagger = 37
    Cloak = 38
    Cloak_Boat = 39
    Pirate = 40
    Bombership = 41
    Scoutship = 42
    Transportship = 43
    Rammership = 44
    Juggernaut = 45
    MermaidWarrior = 46
    MermaidArcher = 47
    MermaidSwordsman = 48
    MermaidDefender = 49
    MermaidCloak = 50
    MermaidDagger = 51
    Jelly = 52
    Shark = 53
    Siren = 54
    Aquapult = 55
    Boomchi = 56
    Island = 57
    Ciru = 58
    Mantis = 59
    BugEgg = 60
    Moth = 61
    Larva = 62


class UnitEffect(IntEnum):
    Frozen = 0
    Poisoned = 1
    Boosted = 2
    Invisible = 3
    Bubble = 4
    Petrified = 5
    Swift = 6
    DoubleReady = 7


class TribeType(IntEnum):
    None_ = 0
    Nature = 1
    Aimo = 2
    Aquarion = 3
    Bardur = 4
    Elyrion = 5
    Hoodrick = 6
    Imperius = 7
    Kickoo = 8
    Luxidoor = 9
    Oumaji = 10
    Quetzali = 11
    Vengir = 12
    Xinxi = 13
    Yadakk = 14
    Zebasi = 15
    Polaris = 16
    Cymanti = 17


class SkinType(IntEnum):
    None_ = -1
    Default = 0
    Ranger = 1
    Ninja = 2
    Baerion = 3
    Scholar = 5
    Mercenary = 7
    Sfinx = 8
    Skeleton = 9
    Arty = 10
    Pirate = 11
    Aibo = 12
    Urkaz = 13
    Ikarus = 14
    DarkElf = 15
    Swamp = 17
    Magma = 18
    Test = 2000


class CommandType(IntEnum):
    None_ = 0
    Build = 1
    Attack = 2
    Recover = 3
    HealOthers = 4
    Train = 5
    Move = 6
    Capture = 7
    Research = 8
    Destroy = 9
    Disband = 10
    CityReward = 11
    Promote = 13
    ExamineRuins = 14
    EndTurn = 15
    Upgrade = 16
    FreezeArea = 17
    BreakIce = 18
    SelectTribe = 19
    StartMatch = 20
    Stay = 21
    EndMatch = 22
    Harvest = 23
    Explode = 24
    Boost = 25
    Decompose = 26
    PeaceTreaty = 27
    PeaceRequestResponse = 28
    BreakPeace = 29
    EstablishEmbassy = 30
    DestroyEmbassy = 32
    Hide = 33
    Resign = 35
    Disembark = 36
    Flood = 37
    Swarm = 38
    ClearTileEffect = 39


class ActionType(IntEnum):
    None_ = 0
    Build = 1
    Attack = 2
    Recover = 3
    HealOthers = 4
    Train = 5
    Move = 6
    RuleArea = 7
    Research = 8
    DestroyImprovement = 9
    DisbandUnit = 10
    CityReward = 11
    Meet = 12
    Promote = 13
    ExamineRuins = 14
    EndTurn = 15
    Upgrade = 16
    FreezeArea = 17
    BreakIce = 18
    BuildRoad = 19
    CaptureCity = 20
    CityLevelUp = 21
    UpdateRoutes = 22
    KillUnit = 23
    ModifyProduction = 24
    Explore = 25
    IncreasePopulation = 26
    IncreaseScore = 27
    IncreaseCurrency = 28
    StartTurn = 29
    ScoutMove = 30
    UpdateCityConnections = 31
    DecreasePopulation = 32
    Embark = 34
    Disembark = 35
    SelectTribe = 36
    GameOver = 37
    Heal = 38
    StartMatch = 39
    ImprovementLevelUp = 40
    ImprovementLevelDown = 41
    Convert = 42
    FreezeUnit = 43
    EnableTask = 44
    TaskCompleted = 45
    FreezeTile = 46
    ClimateChange = 47
    Reselect = 48
    WipePlayer = 49
    CreateResource = 50
    DestroyResource = 51
    ModifyScore = 52
    PassPlayer = 53
    ConnectCity = 54
    DisconnectCity = 55
    ChangeCityConnection = 56
    BreakIceArea = 57
    ExpandCity = 58
    DecreaseScore = 59
    EndMatch = 60
    WipePlayerEnd = 61
    EndCommand = 62
    Poison = 63
    Eat = 64
    HarvestImprovement = 66
    Boost = 68
    BoostOthers = 69
    Explode = 70
    Decompose = 71
    ReceiveDiplomacyMessage = 72
    PeaceRequestResponse = 73
    PeaceTreaty = 74
    BreakPeace = 75
    EstablishEmbassy = 76
    RevealCapital = 77
    DestroyEmbassy = 79


class GridDirection(IntEnum):
    SW = 0
    W = 1
    NW = 2
    N = 3
    NE = 4
    E = 5
    SE = 6
    S = 7
    NONE = 8


class GridDirectionFlag(IntFlag):
    None_ = 0
    SW = 1
    W = 2
    NW = 4
    N = 8
    NE = 16
    E = 32
    SE = 64
    S = 128


class CommandTriggerType(IntEnum):
    None_ = 0
    CityLevelUp = 1
    PeaceRequest = 2


class DiplomacyMessageType(IntEnum):
    None_ = 0
    PeaceRequest = 1
    EstablishEmbassy = 5


class DiplomacyRelationState(IntEnum):
    Neutral = 0
    Peace = 1
    War = 2
    BrokenPeace = 3


class ImprovementEffect(IntEnum):
    decomposing = 0
    robbed = 1


class CityReward(IntEnum):
    """City level-up reward choices (enum in dump.cs)."""
    pass  # populated from game data JSON at runtime; values vary by version


class PlayerDataFriendshipState(IntEnum):
    None_ = 0
    IsYou = 1
    Accepted = 2
    SentRequest = 3
    ReceivedRequest = 4
    Rejected = 5


class PlayerDataType(IntEnum):
    None_ = 0
    Bot = 1
    LocalUser = 2
    OnlineUser = 4


class BotDifficulty(IntEnum):
    pass


class GameMode(IntEnum):
    pass


class GameType(IntEnum):
    pass


class MapPreset(IntEnum):
    pass


class RuinsReward(IntEnum):
    None_ = 0
    Resources = 1
    PopulationGrowth = 2
    Explorer = 3
    FreeTech = 4
    SuperUnit = 5
    Battleship = 6
    Seamonster = 7
    Swordsman = 8
    City = 9


# Default player territory tint colors (ARGB) when PlayerState.color is unset.
PLAYER_COLORS: dict[int, tuple[int, int, int]] = {
    1: (0x33, 0x77, 0xCC),  # Imperius blue
    2: (0xCC, 0x33, 0x33),  # Bardur red
    3: (0x33, 0xAA, 0x55),  # Kickoo green
    4: (0xCC, 0xAA, 0x22),  # Oumaji yellow
    5: (0x88, 0x44, 0xCC),  # Xin-xi purple
    6: (0xCC, 0x66, 0x22),  # Hoodrick orange
    7: (0x22, 0xAA, 0xAA),  # Aquarion teal
    8: (0xAA, 0x22, 0x66),  # Vengir magenta
}


TRIBE_SKIN_SUFFIX: dict[TribeType, str] = {
    TribeType.Aimo: "aimo",
    TribeType.Aquarion: "aquarion",
    TribeType.Bardur: "bardur",
    TribeType.Elyrion: "elyrion",
    TribeType.Hoodrick: "hoodrick",
    TribeType.Imperius: "imperius",
    TribeType.Kickoo: "kickoo",
    TribeType.Luxidoor: "luxidoor",
    TribeType.Oumaji: "oumaji",
    TribeType.Quetzali: "quetzali",
    TribeType.Vengir: "vengir",
    TribeType.Xinxi: "xinxi",
    TribeType.Yadakk: "yadakk",
    TribeType.Zebasi: "zebasi",
    TribeType.Polaris: "polaris",
    TribeType.Cymanti: "cymanti",
}

# TileData.climate / TribeData.style → primary tribe visuals (GameLogicData tribeData).
# GameLogicData$$GetTribeTypeFromStyle uses this style index for unowned tile art.
CLIMATE_STYLE_TO_TRIBE: dict[int, TribeType] = {
    1: TribeType.Xinxi,
    2: TribeType.Imperius,
    3: TribeType.Bardur,
    4: TribeType.Oumaji,
    5: TribeType.Kickoo,
    6: TribeType.Hoodrick,
    7: TribeType.Luxidoor,
    8: TribeType.Vengir,
    9: TribeType.Zebasi,
    10: TribeType.Aimo,
    11: TribeType.Aquarion,
    12: TribeType.Quetzali,
    13: TribeType.Elyrion,
    14: TribeType.Yadakk,
    15: TribeType.Polaris,
    16: TribeType.Cymanti,
}


def climate_skin(climate: int) -> str:
    tribe = CLIMATE_STYLE_TO_TRIBE.get(climate, TribeType.Imperius)
    return TRIBE_SKIN_SUFFIX.get(tribe, "imperius")
