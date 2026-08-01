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
    """dump.cs WorldCoordinates — int x @0x0, int y @0x4."""
    x: int = 0
    y: int = 0


@dataclass
class Shoreline:
    """TileData.Shoreline."""
    visible: bool = False
    sprite_ext: str = ""          # "" or "_swamp"


@dataclass
class Shorelines:
    """TileData.Shorelines."""
    any: bool = False
    N: Shoreline = field(default_factory=Shoreline)
    S: Shoreline = field(default_factory=Shoreline)
    E: Shoreline = field(default_factory=Shoreline)
    W: Shoreline = field(default_factory=Shoreline)


@dataclass
class ResourceState:
    """dump.cs ResourceState — ResourceData.Type type @0x10."""
    type: int


@dataclass
class ImprovementState:
    """dump.cs ImprovementState (TypeDef 10628)."""
    type: int
    owner: int = 0                          # obsolete in C#; tile.owner is authoritative
    founder: int = 0
    level: int = 1
    founded: int = 0
    xp: int = 0
    population: int = 0
    production: int = 0
    base_score: int = 0
    border_size: int = 0
    upgrade: int = 0
    connected_to_capital_of_player: int = 0
    name: str = ""
    rewards: List[int] = field(default_factory=list)   # CityReward
    effects: List[int] = field(default_factory=list)   # ImprovementEffect

    def has_reward(self, reward: int) -> bool:
        """ImprovementDataExtensions.HasReward."""
        return reward in self.rewards

    def reward_count(self, reward: int) -> int:
        """ImprovementDataExtensions.RewardCount."""
        return sum(1 for r in self.rewards if r == reward)


@dataclass
class UnitState:
    """dump.cs UnitState (TypeDef 10633)."""
    id: int = 0
    leader: int = 0
    follower: int = 0
    owner: int = 0
    birth_climate: int = 0                  # TribeType
    birth_climate_skin_type: int = 0        # SkinType
    type: int = 0
    previous_turn_end_coordinates: WorldCoordinates = field(
        default_factory=WorldCoordinates)
    coordinates: WorldCoordinates = field(default_factory=WorldCoordinates)
    home: WorldCoordinates = field(default_factory=WorldCoordinates)
    passenger_unit: Optional["UnitState"] = None
    health: int = 10
    promotion_level: int = 0
    xp: int = 0
    moved: bool = False
    attacked: bool = False
    direction: int = 8                      # GridDirection.NONE
    flipped: bool = False
    created_turn: int = 0
    unit_data: Any = None                   # UnitData ref — not modeled
    effects: List[int] = field(default_factory=list)
    is_temporary_explorer_unit: bool = False

    # Ergonomic aliases for the embedded WorldCoordinates (not extra C fields).
    @property
    def x(self) -> int:
        return self.coordinates.x

    @property
    def y(self) -> int:
        return self.coordinates.y


@dataclass
class WorldContinent:
    """dump.cs WorldContinent — render does not consume these; kept for schema parity."""
    tiles: List[WorldCoordinates] = field(default_factory=list)
    climate: int = 0
    skin_type: int = 0
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
class TileData:
    """dump.cs TileData (TypeDef 10588)."""
    coordinates: WorldCoordinates
    terrain: int
    climate: int = 0
    skin: int = 0                           # _skin
    effects: List[int] = field(default_factory=list)
    altitude: int = 0
    owner: int = 0
    capital_of: int = 0
    explorers: List[int] = field(default_factory=list)
    shorelines: Shorelines = field(default_factory=Shorelines)
    ruling_city_coordinates: WorldCoordinates = field(
        default_factory=lambda: WorldCoordinates(-1, -1))
    improvement: Optional[ImprovementState] = None
    resource: Optional[ResourceState] = None
    unit: Optional[UnitState] = None
    has_road: bool = False
    has_route: bool = False
    continent: Optional[WorldContinent] = None
    had_route: bool = False
    upgrade_tech: Dict[int, float] = field(default_factory=dict)
    last_population_check: int = 0
    available_population: int = 0

    @property
    def x(self) -> int:
        return self.coordinates.x

    @property
    def y(self) -> int:
        return self.coordinates.y


@dataclass
class PlayerState:
    """dump.cs PlayerState (TypeDef 10630) — full field list; unused stay at defaults."""
    NO_PLAYER_ID: ClassVar[int] = 0
    NATURE_PLAYER_ID: ClassVar[int] = 255

    id: int = 0
    user_name: str = ""
    account_id: Any = None
    auto_play: bool = False
    start_tile: WorldCoordinates = field(default_factory=WorldCoordinates)
    tribe: int = 0
    tribe_mix: int = 0
    climate: int = 0                        # _climate
    has_chosen_tribe: bool = False
    handicap: int = 0
    resigned_turn: int = 0
    resigned_at_command_index: int = 0
    wiped_at_command_index: int = 0
    available_tech: List[int] = field(default_factory=list)
    tasks: List[Any] = field(default_factory=list)
    aggressions: Dict[int, int] = field(default_factory=dict)
    known_players: List[int] = field(default_factory=list)
    built_unique_improvements: List[int] = field(default_factory=list)
    relations: Dict[int, Any] = field(default_factory=dict)
    messages: List[Any] = field(default_factory=list)
    skin_type: int = 0
    currency: int = 0
    score: int = 0
    end_score: int = 0
    cities: int = 0
    kills: int = 0
    casualities: int = 0
    wipe_outs: int = 0
    killer_id: int = 0
    killed_turn: int = 0
    color: int = 0
    ai_state: Any = None
    unlocked_tech_cache: List[Any] = field(default_factory=list)
    block_train_units: bool = False
    capital_count_cache: int = 0
    opinions: Any = None


@dataclass
class MapData:
    """dump.cs MapData (TypeDef 10577)."""
    width: int
    height: int
    tiles: List[TileData]
    continents: List[WorldContinent] = field(default_factory=list)

    def tile_at(self, x: int, y: int) -> Optional[TileData]:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y * self.width + x]
        return None


@dataclass
class GameState:
    """dump.cs GameState (TypeDef 10622)."""
    # GameState.State: Unknown=0 Lobby=1 Started=2 FinalTurn=3 Ended=4
    version: int = 0
    seed: int = 0
    village_name_seed: int = 0
    current_turn: int = 0
    current_player_index: int = 0
    current_unit_id: int = 0
    current_state: int = 0
    settings: Any = None
    map: Optional[MapData] = None
    player_states: List[PlayerState] = field(default_factory=list)
    current_command: int = 0
    command_stack: List[Any] = field(default_factory=list)
    action_stack: List[Any] = field(default_factory=list)
    pending_command_triggers: List[Any] = field(default_factory=list)
    has_flagged_need_for_update_routes: bool = False
    random_hash: Any = None
    village_name_hash: Any = None
    mocked_game_logic_data: Any = None

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
        health=d.get("health", 10),
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
    return GameState(
        version=d.get("version", 0),
        seed=d.get("seed", 0),
        village_name_seed=d.get("village_name_seed", 0),
        current_turn=d.get("current_turn", 0),
        current_player_index=d.get("current_player_index", 0),
        current_unit_id=d.get("current_unit_id", 0),
        current_state=d.get("current_state", 0),
        map=mapdata,
        player_states=[_player(p) for p in plist],
    )


def load(path: str) -> GameState:
    with open(path) as f:
        return from_dict(json.load(f))
