"""GameState input schema (recon/gamestate_schema.md) + JSON loader.

A trimmed, render-only projection of the game's authoritative GameState. Field
names/enum integers match the IL2CPP dump so layer code can switch on them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Shoreline:
    visible: bool = False
    sprite_ext: str = ""          # "" or "_swamp"


@dataclass
class Shorelines:
    any: bool = False
    N: Shoreline = field(default_factory=Shoreline)
    S: Shoreline = field(default_factory=Shoreline)
    E: Shoreline = field(default_factory=Shoreline)
    W: Shoreline = field(default_factory=Shoreline)


@dataclass
class ResourceState:
    type: int


@dataclass
class ImprovementState:
    type: int
    level: int = 1
    population: int = 0
    border_size: int = 0
    founder: int = 0
    connected_to_capital_of: int = 0
    is_capital_of: int = 0
    has_wall: bool = False
    has_workshop: bool = False
    park_count: int = 0
    effects: List[int] = field(default_factory=list)
    name: str = ""
    xp: int = 0


@dataclass
class UnitState:
    id: int = 0
    type: int = 0
    owner: int = 0
    x: int = 0
    y: int = 0
    health: int = 10
    promotion_level: int = 0
    direction: int = 8
    flipped: bool = False
    moved: bool = False
    attacked: bool = False
    skin_type: int = 0
    style: int = 0
    effects: List[int] = field(default_factory=list)
    passenger_type: Optional[int] = None


@dataclass
class TileData:
    x: int
    y: int
    terrain: int
    climate: int = 0
    skin: int = 0
    altitude: int = 0
    owner: int = 0
    capital_of: int = 0
    effects: List[int] = field(default_factory=list)
    explorers: List[int] = field(default_factory=list)
    shorelines: Shorelines = field(default_factory=Shorelines)
    ruling_city_x: int = -1
    ruling_city_y: int = -1
    improvement: Optional[ImprovementState] = None
    resource: Optional[ResourceState] = None
    unit: Optional[UnitState] = None
    has_road: bool = False
    has_route: bool = False


@dataclass
class PlayerState:
    id: int
    tribe: int
    skin_type: int = 0
    color: int = 0
    known_players: List[int] = field(default_factory=list)
    available_tech: List[int] = field(default_factory=list)  # TechData.Type ints


@dataclass
class MapData:
    width: int
    height: int
    tiles: List[TileData]

    def tile_at(self, x: int, y: int) -> Optional[TileData]:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.tiles[y * self.width + x]
        return None


@dataclass
class GameState:
    map: MapData
    players: List[PlayerState]
    current_player_index: int = 0
    current_turn: int = 0

    def player_by_id(self, pid: int) -> Optional[PlayerState]:
        for p in self.players:
            if p.id == pid:
                return p
        return None

    @property
    def viewer(self) -> Optional[PlayerState]:
        if 0 <= self.current_player_index < len(self.players):
            return self.players[self.current_player_index]
        return None


# ----------------------------------------------------------------------
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
    return ImprovementState(
        type=d["type"], level=d.get("level", 1), population=d.get("population", 0),
        border_size=d.get("border_size", 0), founder=d.get("founder", 0),
        connected_to_capital_of=d.get("connected_to_capital_of", 0),
        is_capital_of=d.get("is_capital_of", d.get("capital_of", 0)),
        has_wall=bool(d.get("has_wall", False)),
        has_workshop=bool(d.get("has_workshop", False)),
        park_count=d.get("park_count", 0), effects=list(d.get("effects", [])),
        name=d.get("name", ""),
        xp=d.get("xp", 0),
    )


def _unit(d: Optional[dict]) -> Optional[UnitState]:
    if d is None:
        return None
    return UnitState(
        id=d.get("id", 0), type=d["type"], owner=d.get("owner", 0),
        x=d.get("x", 0), y=d.get("y", 0), health=d.get("health", 10),
        promotion_level=d.get("promotion_level", 0), direction=d.get("direction", 8),
        flipped=bool(d.get("flipped", False)), moved=bool(d.get("moved", False)),
        attacked=bool(d.get("attacked", False)), skin_type=d.get("skin_type", 0),
        style=d.get("style", 0), effects=list(d.get("effects", [])),
        passenger_type=d.get("passenger_type"),
    )


def _tile(d: dict) -> TileData:
    return TileData(
        x=d["x"], y=d["y"], terrain=d["terrain"], climate=d.get("climate", 0),
        skin=d.get("skin", 0), altitude=d.get("altitude", 0), owner=d.get("owner", 0),
        capital_of=d.get("capital_of", 0), effects=list(d.get("effects", [])),
        explorers=list(d.get("explorers", [])), shorelines=_shorelines(d.get("shorelines")),
        ruling_city_x=d.get("ruling_city_x", -1), ruling_city_y=d.get("ruling_city_y", -1),
        improvement=_improvement(d.get("improvement")), resource=_resource(d.get("resource")),
        unit=_unit(d.get("unit")), has_road=bool(d.get("has_road", False)),
        has_route=bool(d.get("has_route", False)),
    )


def _resource(d: Optional[dict]) -> Optional[ResourceState]:
    if d is None:
        return None
    return ResourceState(type=d["type"])


def _player(d: dict) -> PlayerState:
    return PlayerState(
        id=d["id"], tribe=d["tribe"], skin_type=d.get("skin_type", 0),
        color=d.get("color", 0), known_players=list(d.get("known_players", [])),
        available_tech=list(d.get("available_tech", [])),
    )


def from_dict(d: dict) -> GameState:
    m = d["map"]
    tiles = [_tile(t) for t in m["tiles"]]
    mapdata = MapData(width=m["width"], height=m["height"], tiles=tiles)
    players = [_player(p) for p in d.get("players", [])]
    return GameState(map=mapdata, players=players,
                     current_player_index=d.get("current_player_index", 0),
                     current_turn=d.get("current_turn", 0))


def load(path: str) -> GameState:
    with open(path) as f:
        return from_dict(json.load(f))
