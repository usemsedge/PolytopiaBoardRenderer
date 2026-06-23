"""Python translation of GameLogicAssembly simulation state (GameState object graph).

Field names and types mirror IL2CPP dump.cs (Game v116). Method bodies are omitted;
use MapData/GameState helpers here for indexing and lookups.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

from .enums import (
    ActionType,
    CommandTriggerType,
    DiplomacyMessageType,
    DiplomacyRelationState,
    GameStateState,
    GridDirection,
    ImprovementEffect,
    ImprovementType,
    PlayerDataFriendshipState,
    PlayerDataType,
    ResourceType,
    SkinType,
    TerrainType,
    TileEffectType,
    TribeType,
    UnitEffect,
    UnitType,
)




@dataclass
class WorldCoordinates:
    x: int = 0
    y: int = 0

    def to_index(self, width: int) -> int:
        return self.y * width + self.x

    @staticmethod
    def to_index_xy(x: int, y: int, width: int) -> int:
        return y * width + x

    @staticmethod
    def from_index(index: int, width: int) -> WorldCoordinates:
        return WorldCoordinates(index % width, index // width)

    def is_valid(self, width: int, height: int) -> bool:
        return 0 <= self.x < width and 0 <= self.y < height

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WorldCoordinates):
            return NotImplemented
        return self.x == other.x and self.y == other.y


@dataclass
class TileShoreline:
    visible: bool = False
    sprite_ext: str = ""


@dataclass
class TileShorelines:
    any_visible: bool = False
    n: TileShoreline = field(default_factory=TileShoreline)
    s: TileShoreline = field(default_factory=TileShoreline)
    e: TileShoreline = field(default_factory=TileShoreline)
    w: TileShoreline = field(default_factory=TileShoreline)


@dataclass
class ResourceState:
    type: ResourceType = ResourceType.None_


@dataclass
class ImprovementState:
    type: ImprovementType = ImprovementType.None_
    owner: int = 0  # obsolete in C#; use tile.owner
    founder: int = 0
    level: int = 1
    founded: int = 0
    xp: int = 0
    population: int = 1
    production: int = 0
    base_score: int = 0
    border_size: int = 1
    upgrade: int = 0
    connected_to_capital_of_player: int = 0
    name: str = ""
    rewards: list[Any] = field(default_factory=list)
    effects: list[ImprovementEffect] = field(default_factory=list)


@dataclass
class UnitState:
    id: int = 0
    leader: int = 0
    follower: int = 0
    owner: int = 0
    style: int = 0
    skin_type: SkinType = SkinType.Default
    type: UnitType = UnitType.None_
    previous_turn_end_coordinates: WorldCoordinates = field(default_factory=WorldCoordinates)
    coordinates: WorldCoordinates = field(default_factory=WorldCoordinates)
    home: WorldCoordinates = field(default_factory=WorldCoordinates)
    passenger_unit: Optional[UnitState] = None
    health: int = 10
    promotion_level: int = 0
    xp: int = 0
    moved: bool = False
    attacked: bool = False
    direction: GridDirection = GridDirection.NONE
    flipped: bool = False
    created_turn: int = 0
    unit_data: Any = None  # UnitData ref (static rules)
    effects: list[UnitEffect] = field(default_factory=list)


@dataclass
class TileData:
    coordinates: WorldCoordinates = field(default_factory=WorldCoordinates)
    terrain: TerrainType = TerrainType.Field
    climate: int = 0
    skin: SkinType = SkinType.Default
    effects: list[TileEffectType] = field(default_factory=list)
    altitude: int = 0
    owner: int = 0
    capital_of: int = 0
    explorers: list[int] = field(default_factory=list)
    shorelines: TileShorelines = field(default_factory=TileShorelines)
    ruling_city_coordinates: WorldCoordinates = field(default_factory=WorldCoordinates)
    improvement: Optional[ImprovementState] = None
    resource: Optional[ResourceState] = None
    unit: Optional[UnitState] = None
    has_road: bool = False
    has_route: bool = False
    continent: Any = None  # WorldContinent ref
    had_route: bool = False
    upgrade_tech: dict[Any, float] = field(default_factory=dict)
    last_population_check: int = 0
    available_population: int = 0

    @property
    def is_water(self) -> bool:
        return self.terrain in (TerrainType.Water, TerrainType.Ocean)

    @property
    def is_land(self) -> bool:
        return not self.is_water and self.terrain != TerrainType.None_


@dataclass
class WorldContinent:
    tiles: list[WorldCoordinates] = field(default_factory=list)
    climate: int = 0
    skin_type: SkinType = SkinType.Default
    crop: float = 0.0
    fish: float = 0.0
    fruit: float = 0.0
    game: float = 0.0
    metal: float = 0.0
    whale: float = 0.0
    spores: float = 0.0
    aquacrop: float = 0.0
    water: float = 0.0
    ocean: float = 0.0
    field: float = 0.0
    mountain: float = 0.0
    forest: float = 0.0
    ice: float = 0.0
    has_alien_climate: bool = False
    land_tile_count: int = 0
    number_of_capitals: int = 0
    max_size: int = 0


@dataclass
class MapData:
    width: int = 0
    height: int = 0
    tiles: list[TileData] = field(default_factory=list)
    continents: list[WorldContinent] = field(default_factory=list)

    def get_tile(self, coords: WorldCoordinates) -> Optional[TileData]:
        if not coords.is_valid(self.width, self.height):
            return None
        return self.tiles[coords.to_index(self.width)]

    def get_tile_xy(self, x: int, y: int) -> Optional[TileData]:
        return self.get_tile(WorldCoordinates(x, y))


# --- Player & session ---


@dataclass
class AvatarPartState:
    type: int = 0
    color: int = 0


@dataclass
class AvatarState:
    layer0: AvatarPartState = field(default_factory=AvatarPartState)
    layer1: AvatarPartState = field(default_factory=AvatarPartState)
    layer2: AvatarPartState = field(default_factory=AvatarPartState)
    layer3: AvatarPartState = field(default_factory=AvatarPartState)
    layer4: AvatarPartState = field(default_factory=AvatarPartState)


@dataclass
class PlayerProfileState:
    id: UUID = field(default_factory=lambda: UUID(int=0))
    name: str = ""
    avatar_state: AvatarState = field(default_factory=AvatarState)
    num_games: int = 0
    num_multiplayer_games: int = 0
    num_friends: int = 0
    game_version: int = 0
    multiplayer_rating: int = 0
    platform: int = 0
    victories: dict[UUID, int] = field(default_factory=dict)
    defeats: dict[UUID, int] = field(default_factory=dict)


@dataclass
class PlayerData:
    type: PlayerDataType = PlayerDataType.None_
    friendship_state: PlayerDataFriendshipState = PlayerDataFriendshipState.None_
    is_spectating: bool = False
    known_tribe: bool = True
    tribe: TribeType = TribeType.None_
    tribe_mix: TribeType = TribeType.None_
    bot_difficulty: int = 0
    skin_type: SkinType = SkinType.Default
    profile: PlayerProfileState = field(default_factory=PlayerProfileState)
    default_name: str = ""


@dataclass
class DiplomacyMessage:
    type: DiplomacyMessageType = DiplomacyMessageType.None_
    sender: int = 0


@dataclass
class DiplomacyRelation:
    state: DiplomacyRelationState = DiplomacyRelationState.Neutral
    last_attack_turn: int = -100
    embassy_level: int = 0
    last_peace_broken_turn: int = 0
    first_meet: int = 0
    embassy_build_turn: int = 0
    previous_attack_turn: int = 0


@dataclass
class PlayerState:
    NO_PLAYER_ID: int = field(default=0, init=False, repr=False)
    NATURE_PLAYER_ID: int = field(default=255, init=False, repr=False)

    id: int = 0
    user_name: str = ""
    account_id: Optional[UUID] = None
    auto_play: bool = False
    start_tile: WorldCoordinates = field(default_factory=WorldCoordinates)
    tribe: TribeType = TribeType.None_
    tribe_mix: TribeType = TribeType.None_
    has_chosen_tribe: bool = True
    handicap: int = 0
    resigned_turn: int = -1
    resigned_at_command_index: int = -1
    wiped_at_command_index: int = -1
    available_tech: list[Any] = field(default_factory=list)
    tasks: list[Any] = field(default_factory=list)  # TaskBase subclasses
    aggressions: dict[int, int] = field(default_factory=dict)
    known_players: list[int] = field(default_factory=list)
    built_unique_improvements: list[ImprovementType] = field(default_factory=list)
    relations: dict[int, DiplomacyRelation] = field(default_factory=dict)
    messages: list[DiplomacyMessage] = field(default_factory=list)
    skin_type: SkinType = SkinType.Default
    currency: int = 5
    score: int = 0
    end_score: int = 0
    cities: int = 1
    kills: int = 0
    casualities: int = 0
    wipe_outs: int = 0
    killer_id: int = 0
    killed_turn: int = 0
    color: int = 0
    ai_state: Any = None
    unlocked_tech_cache: list[Any] = field(default_factory=list)
    block_train_units: bool = False
    capital_count_cache: int = 1


# --- Commands & actions ---


@dataclass
class CommandBase:
    """Base for MoveCommand, AttackCommand, etc. (50+ subclasses in C#)."""

    player_id: int = 0

    def execute(self, state: GameState) -> None:
        pass

    def is_valid(self, state: GameState) -> bool:
        return True


@dataclass
class ActionBase:
    """Base for KillUnitAction, CaptureCityAction, etc."""

    player_id: int = 0
    sub_actions: list[ActionBase] = field(default_factory=list)

    def execute(self, state: GameState) -> None:
        pass

    def is_valid(self, state: GameState) -> bool:
        return True

    def get_action_type(self) -> ActionType:
        return ActionType.None_


@dataclass
class CommandTrigger:
    player_id: int = 0
    opponent_id: int = 0
    type: CommandTriggerType = CommandTriggerType.None_
    coordinates: WorldCoordinates = field(default_factory=WorldCoordinates)


@dataclass
class GameSettings:
    DEFAULT_MATCHMAKING_MAPSIZE: int = field(default=0, init=False, repr=False)
    DEFAULT_MATCHMAKING_OPPONENT_COUNT: int = field(default=1, init=False, repr=False)

    base_game_mode: int = 0
    rules_game_mode: int = 0
    disabled_tribes: list[TribeType] = field(default_factory=list)
    unlocked_tribes: list[TribeType] = field(default_factory=list)
    selected_skins: dict[TribeType, SkinType] = field(default_factory=dict)
    players: list[PlayerData] = field(default_factory=list)
    spectators: list[PlayerData] = field(default_factory=list)
    map_preset: int = 0
    rules: int = 0
    game_name: str = ""
    game_type: int = 0
    map_size: int = 11
    time_limit: int = 0
    time_bonus_per_population: float = 0.0
    time_bonus_per_city: float = 0.0
    base_time_seconds: float = 0.0
    use_dynamic_timers: bool = False
    use_time_banks: bool = False
    live_game_preset: bool = False
    is_auto_skip_enabled: bool = False
    difficulty: int = 0
    opponent_count: int = 1


@dataclass
class XXHash:
    """Random stream state (XXHash in C#)."""

    state: int = 0


@dataclass
class GameStateSummary:
    game_name: str = ""
    current_turn: int = 0
    current_player: int = 0
    current_command: int = 0
    map_width: int = 0
    map_height: int = 0
    map_preset: int = 0
    game_mode: int = 0
    game_type: int = 0
    rules: int = 0
    is_auto_skip_enabled: bool = False
    player_summaries: list[Any] = field(default_factory=list)


@dataclass
class GameState:
    version: int = 116
    seed: int = 0
    current_turn: int = 1
    current_player_index: int = 0
    current_unit_id: int = 1
    current_state: GameStateState = GameStateState.Started
    settings: GameSettings = field(default_factory=GameSettings)
    map: MapData = field(default_factory=MapData)
    player_states: list[PlayerState] = field(default_factory=list)
    current_command: int = 0
    command_stack: list[CommandBase] = field(default_factory=list)
    action_stack: list[ActionBase] = field(default_factory=list)
    pending_command_triggers: list[CommandTrigger] = field(default_factory=list)
    has_flagged_need_for_update_routes: bool = False
    random_hash: XXHash = field(default_factory=XXHash)
    mocked_game_logic_data: Any = None

    @property
    def player_count(self) -> int:
        return len(self.player_states)

    @property
    def current_player(self) -> int:
        if not self.player_states:
            return 0
        idx = self.current_player_index % len(self.player_states)
        return self.player_states[idx].id

    def try_get_player(self, player_id: int) -> Optional[PlayerState]:
        for p in self.player_states:
            if p.id == player_id:
                return p
        return None

    def try_get_unit(self, unit_id: int) -> Optional[UnitState]:
        for tile in self.map.tiles:
            if tile.unit and tile.unit.id == unit_id:
                return tile.unit
        return None

    def get_tile(self, coords: WorldCoordinates) -> Optional[TileData]:
        return self.map.get_tile(coords)
