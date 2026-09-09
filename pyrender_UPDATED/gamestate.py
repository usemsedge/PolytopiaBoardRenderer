"""GameState input schema — field-for-field mirror of the IL2CPP dump structs.

Names are Python snake_case of the C# fields; enum integers match dump.cs.
Complex sim-only nested types we do not model are typed as Optional[Any].
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional



# ---------------------------------------------------------------------------
# Shared value types
# ---------------------------------------------------------------------------

@dataclass
class WorldCoordinates:
    """dump.cs ``struct WorldCoordinates`` (TypeDef 10710)."""
    x: int = 0                             # C#: int x
    y: int = 0                             # C#: int y


@dataclass
class Shoreline:
    """dump.cs ``class TileData.Shoreline`` (TypeDef 10585)."""
    visible: bool = False                   # C#: bool visible
    sprite_ext: str = ""                   # C#: string spriteExt  ("" or "_swamp")


@dataclass
class Shorelines:
    """dump.cs ``class TileData.Shorelines`` (TypeDef 10586)."""
    any: bool = False                       # C#: bool any
    N: Shoreline = field(default_factory=Shoreline)  # C#: TileData.Shoreline N
    S: Shoreline = field(default_factory=Shoreline)  # C#: TileData.Shoreline S
    E: Shoreline = field(default_factory=Shoreline)  # C#: TileData.Shoreline E
    W: Shoreline = field(default_factory=Shoreline)  # C#: TileData.Shoreline W


@dataclass
class ResourceState:
    """dump.cs ``class ResourceState`` (TypeDef 10631)."""
    type: int                               # C#: ResourceData.Type type


@dataclass
class ImprovementState:
    """dump.cs ``class ImprovementState`` (TypeDef 10628)."""
    type: int                               # C#: ImprovementData.Type type
    owner: int = 0                          # C#: byte owner  (obsolete; tile.owner is authoritative)
    founder: int = 0                       # C#: byte founder
    level: int = 1                         # C#: ushort level
    founded: int = 0                       # C#: ushort founded
    xp: int = 0                            # C#: short xp
    population: int = 0                    # C#: short population
    production: int = 0                    # C#: ushort production
    base_score: int = 0                    # C#: ushort baseScore
    border_size: int = 0                    # C#: ushort borderSize
    upgrade: int = 0                       # C#: ushort upgrade
    connected_to_capital_of_player: int = 0  # C#: byte connectedToCapitalOfPlayer
    name: str = ""                         # C#: string name
    rewards: List[int] = field(default_factory=list)   # C#: List<CityReward> rewards
    effects: List[int] = field(default_factory=list)   # C#: List<ImprovementEffect> effects
    # Renderer-only (not in dump). Ordered player ids who discovered this
    # LightHouse (tower drums). Empty = fall back to built_unique_improvements.
    discovered_by: List[int] = field(default_factory=list)

    def has_reward(self, reward: int) -> bool:
        """ImprovementDataExtensions.HasReward."""
        return reward in self.rewards

    def reward_count(self, reward: int) -> int:
        """ImprovementDataExtensions.RewardCount."""
        return sum(1 for r in self.rewards if r == reward)


@dataclass
class UnitState:
    """dump.cs ``class UnitState`` (TypeDef 10633)."""
    id: int = 0                            # C#: uint id
    leader: int = 0                        # C#: uint leader
    follower: int = 0                      # C#: uint follower
    owner: int = 0                         # C#: byte owner
    birth_climate: int = 0                # C#: TribeType birthClimate
    birth_climate_skin_type: int = 0      # C#: SkinType birthClimateSkinType
    type: int = 0                          # C#: UnitData.Type type
    previous_turn_end_coordinates: WorldCoordinates = field(
        default_factory=WorldCoordinates)     # C#: WorldCoordinates previousTurnEndCoordinates
    coordinates: WorldCoordinates = field(default_factory=WorldCoordinates)  # C#: WorldCoordinates coordinates
    home: WorldCoordinates = field(default_factory=WorldCoordinates)  # C#: WorldCoordinates home
    passenger_unit: Optional["UnitState"] = None  # C#: UnitState passengerUnit
    health: int = 100                      # C#: ushort health  (tenths; display HP = ceil(health/10))
    promotion_level: int = 0              # C#: ushort promotionLevel
    xp: int = 0                            # C#: ushort xp
    moved: bool = False                    # C#: bool moved
    attacked: bool = False                  # C#: bool attacked
    direction: int = 8                    # C#: GridDirection direction  (NONE=8)
    flipped: bool = False                   # C#: bool flipped
    created_turn: int = 0                 # C#: ushort createdTurn
    unit_data: Any = None                   # C#: UnitData UnitData  (not modeled)
    effects: List[int] = field(default_factory=list)  # C#: List<UnitEffect> effects
    is_temporary_explorer_unit: bool = False  # C#: bool isTemporaryExplorerUnit

    # Ergonomic aliases for the embedded WorldCoordinates (not extra C fields).
    @property
    def x(self) -> int:
        return self.coordinates.x

    @property
    def y(self) -> int:
        return self.coordinates.y


@dataclass
class WorldContinent:
    """dump.cs ``class WorldContinent`` (TypeDef 10709)."""
    tiles: List[WorldCoordinates] = field(default_factory=list)  # C#: List<WorldCoordinates> tiles
    climate: int = 0                       # C#: TribeType climate
    skin_type: int = 0                     # C#: SkinType skinType
    crop: float = 0.0                      # C#: float crop
    fish: float = 0.0                      # C#: float fish
    fruit: float = 0.0                     # C#: float fruit
    game: float = 0.0                      # C#: float game
    metal: float = 0.0                     # C#: float metal
    whale: float = 0.0                     # C#: float whale
    spores: float = 0.0                    # C#: float spores
    aquacrop: float = 0.0                  # C#: float aquacrop
    water: float = 0.0                     # C#: float water
    ocean: float = 0.0                     # C#: float ocean
    field: float = 0.0                     # C#: float field
    mountain: float = 0.0                  # C#: float mountain
    forest: float = 0.0                    # C#: float forest
    ice: float = 0.0                       # C#: float ice
    has_alien_climate: bool = False         # C#: bool hasAlienClimate
    land_tile_count: int = 0               # C#: int LandTileCount
    number_of_capitals: int = 0            # C#: int NumberOfCapitals
    max_size: int = 0                      # C#: int MaxSize


@dataclass
class TileData:
    """dump.cs ``class TileData`` (TypeDef 10588)."""
    coordinates: WorldCoordinates            # C#: WorldCoordinates coordinates
    terrain: int                            # C#: TerrainData.Type terrain
    climate: int = 0                       # C#: TribeType climate  (in-memory; save file is legacy index)
    skin: int = 0                          # C#: SkinType _skin
    effects: List[int] = field(default_factory=list)  # C#: List<TileData.EffectType> effects
    altitude: int = 0                      # C#: int altitude
    owner: int = 0                         # C#: byte owner
    capital_of: int = 0                    # C#: byte capitalOf
    explorers: List[int] = field(default_factory=list)  # C#: List<byte> explorers
    shorelines: Shorelines = field(default_factory=Shorelines)  # C#: TileData.Shorelines shorelines
    ruling_city_coordinates: WorldCoordinates = field(
        default_factory=lambda: WorldCoordinates(-1, -1))  # C#: WorldCoordinates rulingCityCoordinates
    improvement: Optional[ImprovementState] = None  # C#: ImprovementState improvement
    resource: Optional[ResourceState] = None  # C#: ResourceState resource
    unit: Optional[UnitState] = None        # C#: UnitState unit
    has_road: bool = False                   # C#: bool hasRoad
    has_route: bool = False                  # C#: bool hasRoute
    continent: Optional[WorldContinent] = None  # C#: WorldContinent continent
    had_route: bool = False                  # C#: bool hadRoute
    upgrade_tech: Dict[int, float] = field(default_factory=dict)  # C#: Dictionary<TechData.Type, float> upgradeTech
    last_population_check: int = 0         # C#: long lastPopulationCheck
    available_population: int = 0         # C#: int availablePopulation

    @property
    def x(self) -> int:
        return self.coordinates.x

    @property
    def y(self) -> int:
        return self.coordinates.y

    def is_owner_capital(self) -> bool:
        """True when this is the current owner's own capital, not a captured one.

        ``capital_of`` is the founding player and stays set after capture; the
        crown/icon only belongs to that player while they still own the tile.
        """
        cap = int(self.capital_of or 0)
        return cap != 0 and cap == int(self.owner or 0)


@dataclass
class PlayerState:
    """dump.cs ``class PlayerState`` (TypeDef 10630)."""
    NO_PLAYER_ID: ClassVar[int] = 0        # C#: const byte NO_PLAYER_ID
    NATURE_PLAYER_ID: ClassVar[int] = 255  # C#: const byte NATURE_PLAYER_ID

    id: int = 0                            # C#: byte Id
    user_name: str = ""                    # C#: string UserName
    account_id: Any = None                  # C#: Nullable<Guid> AccountId
    auto_play: bool = False                 # C#: bool AutoPlay
    start_tile: WorldCoordinates = field(default_factory=WorldCoordinates)  # C#: WorldCoordinates startTile
    tribe: int = 0                         # C#: TribeType tribe
    tribe_mix: int = 0                     # C#: TribeType tribeMix
    climate: int = 0                      # C#: TribeType _climate
    has_chosen_tribe: bool = False          # C#: bool hasChosenTribe
    handicap: int = 0                     # C#: int handicap
    resigned_turn: int = 0                # C#: int resignedTurn
    resigned_at_command_index: int = 0      # C#: int resignedAtCommandIndex
    wiped_at_command_index: int = 0        # C#: int wipedAtCommandIndex
    available_tech: List[int] = field(default_factory=list)  # C#: List<TechData.Type> availableTech
    tasks: List[Any] = field(default_factory=list)  # C#: List<TaskBase> tasks
    aggressions: Dict[int, int] = field(default_factory=dict)  # C#: Dictionary<byte, int> aggressions
    known_players: List[int] = field(default_factory=list)  # C#: List<byte> knownPlayers
    built_unique_improvements: List[int] = field(default_factory=list)  # C#: List<ImprovementData.Type> builtUniqueImprovements
    relations: Dict[int, Any] = field(default_factory=dict)  # C#: Dictionary<byte, DiplomacyRelation> relations
    messages: List[Any] = field(default_factory=list)  # C#: List<DiplomacyMessage> messages
    skin_type: int = 0                     # C#: SkinType skinType
    currency: int = 0                     # C#: int currency
    score: int = 0                         # C#: uint score
    end_score: int = 0                     # C#: uint endScore
    cities: int = 0                        # C#: int cities
    kills: int = 0                         # C#: uint kills
    casualities: int = 0                   # C#: uint casualities
    wipe_outs: int = 0                     # C#: uint wipeOuts
    killer_id: int = 0                     # C#: byte killerId
    killed_turn: int = 0                   # C#: uint killedTurn
    color: int = 0                         # C#: int color
    ai_state: Any = None                    # C#: AIState aiState
    unlocked_tech_cache: List[Any] = field(default_factory=list)  # C#: List<TechData> unlockedTechCache
    block_train_units: bool = False          # C#: bool blockTrainUnits
    capital_count_cache: int = 0          # C#: int capitalCountCache
    opinions: Any = None                   # C#: OpinionManager opinions


@dataclass
class MapData:
    """dump.cs ``class MapData`` (TypeDef 10577)."""
    width: int                             # C#: ushort width
    height: int                            # C#: ushort height
    tiles: List[TileData]                  # C#: TileData[] tiles
    continents: List[WorldContinent] = field(default_factory=list)  # C#: WorldContinent[] continents

    def tile_at(self, x: int, y: int) -> Optional[TileData]:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y * self.width + x]
        return None


@dataclass
class GameSettings:
    """dump.cs ``sealed class GameSettings`` (TypeDef 10606) — mapgen subset."""
    map_preset: int = 0                    # C#: MapPreset mapPreset
    map_size: int = 0                      # C#: int MapSize  (enum or raw width when > 6)
    game_name: str = ""                     # C#: string GameName
    game_type: int = 0                     # C#: GameType GameType
    opponent_count: int = 0                # C#: int OpponentCount
    disabled_tribes: List[int] = field(default_factory=list)  # C#: List<TribeType> disabledTribes
    west_map_placement_user_id: Any = None   # C#: Nullable<Guid> WestMapPlacementUserId

    def GetMapGeneratorSettings(self):
        """GameSettings.GetMapGeneratorSettings → CreateFromPreset(mapPreset)."""
        # Lazy import: mapgenerator.settings imports gamestate types.
        from mapgenerator.settings import MapGeneratorSettings
        return MapGeneratorSettings.CreateFromPreset(self.map_preset)

    def map_width(self) -> int:
        """Resolve MapSize enum or raw width to tile count (square maps)."""
        from enums import MAP_SIZE_MAX, MAP_SIZE_MIN, MAP_SIZE_WIDTH, MapSize
        ms = int(self.map_size)
        if 0 < ms <= int(MapSize.MASSIVE):
            w = MAP_SIZE_WIDTH.get(MapSize(ms), 0)
            if w:
                return w
        if MAP_SIZE_MIN <= ms <= MAP_SIZE_MAX:
            return ms
        return MAP_SIZE_WIDTH[MapSize.NORMAL]


@dataclass
class CommandTrigger:
    """dump.cs ``struct CommandTrigger`` (TypeDef 10610)."""
    player_id: int = 0                      # C#: byte playerId
    opponent_id: int = 0                    # C#: byte opponentId
    type: int = 0                          # C#: CommandTriggerType type
    coordinates: WorldCoordinates = field(default_factory=WorldCoordinates)  # C#: WorldCoordinates coordinates


@dataclass
class CommandRecord:
    """One ``GameState.CommandStack`` entry: ``CommandType`` ushort + ``CommandBase`` body."""
    type: int                              # C#: CommandType  (ushort on the wire)
    player_id: int = 0                     # C#: from CommandBase.playerId (byte)
    fields: Dict[str, Any] = field(default_factory=dict)  # flattened CommandBase subclass fields


@dataclass
class ActionRecord:
    """One ``GameState.ActionStack`` entry: ``ActionType`` ushort + ``ActionBase`` body."""
    type: int                              # C#: ActionType  (ushort on the wire)
    player_id: int = 0                     # C#: from ActionBase.playerId (byte)
    fields: Dict[str, Any] = field(default_factory=dict)  # flattened ActionBase subclass fields


@dataclass
class GameState:
    """dump.cs ``class GameState`` (TypeDef 10622)."""
    # GameState.State: Unknown=0 Lobby=1 Started=2 FinalTurn=3 Ended=4
    version: int = 0                       # C#: int Version
    seed: int = 0                          # C#: int Seed
    village_name_seed: int = 0            # C#: int VillageNameSeed
    current_turn: int = 0                 # C#: uint CurrentTurn
    current_player_index: int = 0         # C#: byte CurrentPlayerIndex
    current_unit_id: int = 0              # C#: uint CurrentUnitId
    current_state: int = 0                # C#: GameState.State CurrentState
    settings: Optional[GameSettings] = None  # C#: GameSettings Settings
    map: Optional[MapData] = None           # C#: MapData Map
    player_states: List[PlayerState] = field(default_factory=list)  # C#: List<PlayerState> PlayerStates
    current_command: int = 0              # C#: ushort CurrentCommand
    command_stack: List[CommandRecord] = field(default_factory=list)  # C#: List<CommandBase> CommandStack
    action_stack: List[ActionRecord] = field(default_factory=list)  # C#: List<ActionBase> ActionStack
    pending_command_triggers: List[CommandTrigger] = field(default_factory=list)  # C#: List<CommandTrigger> pendingCommandTriggers
    has_flagged_need_for_update_routes: bool = False  # C#: bool HasFlaggedNeedForUpdateRoutes
    random_hash: Any = None                 # C#: XXHash randomHash
    village_name_hash: Any = None           # C#: XXHash villageNameHash
    mocked_game_logic_data: Any = None       # C#: GameLogicData mockedGameLogicData

    def player_by_id(self, pid: int) -> Optional[PlayerState]:
        for p in self.player_states:
            if p.id == pid:
                return p
        return None

    @property
    def viewer(self) -> Optional[PlayerState]:
        if 0 <= self.current_player_index < len(self.player_states):
            return self.player_states[self.current_player_index]
        return None

    @property
    def PlayerCount(self) -> int:
        return sum(1 for p in self.player_states
                   if p.id != PlayerState.NATURE_PLAYER_ID
                   and p.id != PlayerState.NO_PLAYER_ID)


# ---------------------------------------------------------------------------
# JSON loader
# ---------------------------------------------------------------------------

def _coords(d: Optional[dict], default_x: int = 0, default_y: int = 0) -> WorldCoordinates:
    if d is None:
        return WorldCoordinates(default_x, default_y)
    return WorldCoordinates(int(d.get("x", default_x)), int(d.get("y", default_y)))


def _shoreline(d: dict) -> Shoreline:
    return Shoreline(visible=bool(d.get("visible", False)),
                     sprite_ext=d.get("sprite_ext", ""))


def _shorelines(d: Optional[dict]) -> Shorelines:
    if not d:
        return Shorelines()
    return Shorelines(
        any=bool(d.get("any", False)),
        N=_shoreline(d.get("N", {})), S=_shoreline(d.get("S", {})),
        E=_shoreline(d.get("E", {})), W=_shoreline(d.get("W", {})),
    )


def _improvement(d: Optional[dict]) -> Optional[ImprovementState]:
    if d is None:
        return None
    # Migrate legacy invented fields → rewards / connected_to_capital_of_player.
    rewards = list(d.get("rewards", []))
    if d.get("has_wall") and 1 not in rewards:          # CityReward.CityWall
        rewards.append(1)
    if d.get("has_workshop") and 3 not in rewards:      # CityReward.Workshop
        rewards.append(3)
    park_n = int(d.get("park_count", 0) or 0)
    while rewards.count(2) < park_n:                    # CityReward.Park
        rewards.append(2)
    connected = d.get("connected_to_capital_of_player",
                      d.get("connected_to_capital_of", 0))
    return ImprovementState(
        type=d["type"],
        owner=d.get("owner", 0),
        founder=d.get("founder", 0),
        level=d.get("level", 1),
        founded=d.get("founded", 0),
        xp=d.get("xp", 0),
        population=d.get("population", 0),
        production=d.get("production", 0),
        base_score=d.get("base_score", 0),
        border_size=d.get("border_size", 0),
        upgrade=d.get("upgrade", 0),
        connected_to_capital_of_player=connected,
        name=d.get("name", ""),
        rewards=rewards,
        effects=list(d.get("effects", [])),
        discovered_by=list(d.get("discovered_by", [])),
    )


def _unit(d: Optional[dict]) -> Optional[UnitState]:
    if d is None:
        return None
    coords = d.get("coordinates")
    if coords is None and ("x" in d or "y" in d):
        coords = {"x": d.get("x", 0), "y": d.get("y", 0)}
    home = d.get("home")
    # Legacy home_x / home_y
    if home is None and ("home_x" in d or "home_y" in d):
        home = {"x": d.get("home_x", 0), "y": d.get("home_y", 0)}
    passenger = d.get("passenger_unit")
    if passenger is None and d.get("passenger_type") is not None:
        passenger = {"type": d["passenger_type"]}
    skin = d.get("birth_climate_skin_type", d.get("skin_type", 0))
    return UnitState(
        id=d.get("id", 0),
        leader=d.get("leader", 0),
        follower=d.get("follower", 0),
        owner=d.get("owner", 0),
        birth_climate=d.get("birth_climate", 0),
        birth_climate_skin_type=skin,
        type=d["type"],
        previous_turn_end_coordinates=_coords(d.get("previous_turn_end_coordinates")),
        coordinates=_coords(coords),
        home=_coords(home, -1, -1) if home is not None else WorldCoordinates(-1, -1),
        passenger_unit=_unit(passenger),
        health=d.get("health", 100),
        promotion_level=d.get("promotion_level", 0),
        xp=d.get("xp", 0),
        moved=bool(d.get("moved", False)),
        attacked=bool(d.get("attacked", False)),
        direction=d.get("direction", 8),
        flipped=bool(d.get("flipped", False)),
        created_turn=d.get("created_turn", 0),
        effects=list(d.get("effects", [])),
        is_temporary_explorer_unit=bool(d.get("is_temporary_explorer_unit", False)),
    )


def _resource(d: Optional[dict]) -> Optional[ResourceState]:
    if d is None:
        return None
    return ResourceState(type=d["type"])


def _tile(d: dict) -> TileData:
    coords = d.get("coordinates")
    if coords is None:
        coords = {"x": d["x"], "y": d["y"]}
    ruling = d.get("ruling_city_coordinates")
    if ruling is None and ("ruling_city_x" in d or "ruling_city_y" in d):
        ruling = {"x": d.get("ruling_city_x", -1), "y": d.get("ruling_city_y", -1)}
    capital_of = d.get("capital_of", 0)
    # Legacy: improvement.is_capital_of → tile.capital_of
    imp = d.get("improvement")
    if not capital_of and isinstance(imp, dict):
        capital_of = imp.get("is_capital_of", imp.get("capital_of", 0)) or 0
    return TileData(
        coordinates=_coords(coords),
        terrain=d["terrain"],
        climate=d.get("climate", 0),
        skin=d.get("skin", 0),
        effects=list(d.get("effects", [])),
        altitude=d.get("altitude", 0),
        owner=d.get("owner", 0),
        capital_of=capital_of,
        explorers=list(d.get("explorers", [])),
        shorelines=_shorelines(d.get("shorelines")),
        ruling_city_coordinates=_coords(ruling, -1, -1),
        improvement=_improvement(d.get("improvement")),
        resource=_resource(d.get("resource")),
        unit=_unit(d.get("unit")),
        has_road=bool(d.get("has_road", False)),
        has_route=bool(d.get("has_route", False)),
        had_route=bool(d.get("had_route", False)),
        upgrade_tech={int(k): float(v) for k, v in (d.get("upgrade_tech") or {}).items()},
        last_population_check=d.get("last_population_check", 0),
        available_population=d.get("available_population", 0),
    )


def _player(d: dict) -> PlayerState:
    return PlayerState(
        id=d["id"],
        user_name=d.get("user_name", ""),
        auto_play=bool(d.get("auto_play", False)),
        start_tile=_coords(d.get("start_tile")),
        tribe=d["tribe"],
        tribe_mix=d.get("tribe_mix", 0),
        climate=d.get("climate", 0),
        has_chosen_tribe=bool(d.get("has_chosen_tribe", False)),
        handicap=d.get("handicap", 0),
        available_tech=list(d.get("available_tech", [])),
        known_players=list(d.get("known_players", [])),
        built_unique_improvements=list(d.get("built_unique_improvements", [])),
        skin_type=d.get("skin_type", 0),
        currency=d.get("currency", 0),
        score=d.get("score", 0),
        color=d.get("color", 0),
    )


def from_dict(d: dict) -> GameState:
    m = d["map"]
    tiles = [_tile(t) for t in m["tiles"]]
    mapdata = MapData(
        width=m["width"], height=m["height"], tiles=tiles,
        continents=[],  # not serialized in our JSON yet
    )
    # Accept legacy "players" key as alias for player_states.
    plist = d.get("player_states", d.get("players", []))

    def _trigger(t: dict) -> CommandTrigger:
        return CommandTrigger(
            player_id=int(t.get("player_id", 0)),
            opponent_id=int(t.get("opponent_id", 0)),
            type=int(t.get("type", 0)),
            coordinates=_coords(t.get("coordinates")),
        )

    def _command(c: dict) -> CommandRecord:
        return CommandRecord(
            type=int(c["type"]),
            player_id=int(c.get("player_id", 0)),
            fields=dict(c.get("fields") or {}),
        )

    def _action(a: dict) -> ActionRecord:
        return ActionRecord(
            type=int(a["type"]),
            player_id=int(a.get("player_id", 0)),
            fields=dict(a.get("fields") or {}),
        )

    return GameState(
        version=d.get("version", 0),
        seed=d.get("seed", 0),
        village_name_seed=d.get("village_name_seed", 0),
        current_turn=d.get("current_turn", 0),
        current_player_index=d.get("current_player_index", 0),
        current_unit_id=d.get("current_unit_id", 0),
        current_state=d.get("current_state", 0),
        current_command=d.get("current_command", 0),
        map=mapdata,
        player_states=[_player(p) for p in plist],
        pending_command_triggers=[
            _trigger(t) for t in d.get("pending_command_triggers", [])
        ],
        command_stack=[_command(c) for c in d.get("command_stack", [])],
        action_stack=[_action(a) for a in d.get("action_stack", [])],
        has_flagged_need_for_update_routes=bool(
            d.get("has_flagged_need_for_update_routes", False)
        ),
    )


def load(path: str) -> GameState:
    with open(path) as f:
        return from_dict(json.load(f))
