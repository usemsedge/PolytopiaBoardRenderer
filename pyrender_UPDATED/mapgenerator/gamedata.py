"""GameLogicData accessors for mapgen — loads extracted GameLogic JSON.

Authoritative rates: ``polytopia_extracted/gamelogic/GameLogicData28.json``
(see ``recon/gamelogic_extract.md``). Falls back to the newest
``GameLogicData*.json`` present, then to empty modifiers if missing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from enums import Resource, Terrain, Tribe

# --------------------------------------------------------------------------- paths
_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]  # PolytopiaBoardRenderer/
_GAMELOGIC_DIR = _REPO / "polytopia_extracted" / "gamelogic"
_PREFERRED = _GAMELOGIC_DIR / "GameLogicData28.json"

# Base terrain conversion rates (multiplied by tribe terrainModifier).
_BASE_FOREST = 0.35
_BASE_MOUNTAIN = 0.20
# Polaris has empty terrainModifier in JSON; ice is climate-gated in AddTerrain.
_POLARIS_ICE = 0.40

# Specialty resources: only spawn when the climate tribe lists them in resourceModifier.
_SPECIALTY_RESOURCES = {int(Resource.SPORES), int(Resource.AQUACROP)}


@dataclass
class ResourceData:
    """dump.cs ResourceData — type + terrain affinity used by AddResource."""
    type: int = int(Resource.NONE)
    terrains: List[int] = field(default_factory=list)
    score: float = 1.0
    name: str = ""


@dataclass
class TechData:
    type: int = 0
    resource: int = int(Resource.NONE)


@dataclass
class TribeData:
    type: int = int(Tribe.NONE)
    starting_tech: List[int] = field(default_factory=list)


def _terrain_name_to_id(name: str) -> Optional[int]:
    key = name.strip().lower()
    try:
        return int(Terrain[key.upper()])
    except KeyError:
        return None


def _resource_name_to_id(name: str) -> Optional[int]:
    key = name.strip().lower()
    # JSON uses "game"; enum is GAME.
    try:
        return int(Resource[key.upper()])
    except KeyError:
        return None


def _tribe_id_to_key(tribe: int) -> Optional[str]:
    for t in Tribe:
        if int(t) == int(tribe):
            return t.name.lower()
    return None


def _find_gamelogic_path() -> Optional[Path]:
    if _PREFERRED.is_file():
        return _PREFERRED
    if not _GAMELOGIC_DIR.is_dir():
        return None
    versions: List[Tuple[int, Path]] = []
    for p in _GAMELOGIC_DIR.glob("GameLogicData*.json"):
        m = re.fullmatch(r"GameLogicData(\d+)\.json", p.name)
        if m:
            versions.append((int(m.group(1)), p))
    if not versions:
        return None
    versions.sort()
    return versions[-1][1]


class _GameLogicTables:
    """Cached parse of one GameLogicData JSON version."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or _find_gamelogic_path()
        self.version = 0
        self.resources: List[ResourceData] = []
        self.resources_by_type: Dict[int, ResourceData] = {}
        # tribe_id -> {resource_id -> float}
        self.resource_modifier: Dict[int, Dict[int, float]] = {}
        # tribe_id -> {terrain_name -> float}  (names: forest/mountain/water/…)
        self.terrain_modifier: Dict[int, Dict[str, float]] = {}
        # tribe_id -> list of ResourceData (may repeat)
        self.starting_resources: Dict[int, List[ResourceData]] = {}
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.is_file():
            self._load_fallback()
            return
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        m = re.search(r"GameLogicData(\d+)", self.path.name)
        self.version = int(m.group(1)) if m else 0

        # Resources + terrain requirements.
        for name, entry in (raw.get("resourceData") or {}).items():
            if name == "none":
                continue
            rid = _resource_name_to_id(name)
            if rid is None:
                continue
            terrains: List[int] = []
            for tname in entry.get("resourceTerrainRequirements") or []:
                tid = _terrain_name_to_id(str(tname))
                if tid is not None:
                    terrains.append(tid)
            rd = ResourceData(type=rid, terrains=terrains, score=1.0, name=name)
            self.resources.append(rd)
            self.resources_by_type[rid] = rd

        # Per-tribe modifiers + starting resources.
        for key, entry in (raw.get("tribeData") or {}).items():
            if key in ("none", "nature"):
                continue
            try:
                tribe_id = int(Tribe[key.upper()])
            except KeyError:
                # Prefer climate field when present (matches tile.climate).
                climate = entry.get("climate")
                if climate is None:
                    continue
                tribe_id = int(climate)

            rmods: Dict[int, float] = {}
            for rname, mult in (entry.get("resourceModifier") or {}).items():
                rid = _resource_name_to_id(str(rname))
                if rid is not None:
                    rmods[rid] = float(mult)
            self.resource_modifier[tribe_id] = rmods

            tmods = {
                str(tname).lower(): float(mult)
                for tname, mult in (entry.get("terrainModifier") or {}).items()
            }
            self.terrain_modifier[tribe_id] = tmods

            starts: List[ResourceData] = []
            for rname in entry.get("startingResource") or []:
                rid = _resource_name_to_id(str(rname))
                if rid is None:
                    continue
                base = self.resources_by_type.get(rid)
                if base is not None:
                    starts.append(
                        ResourceData(
                            type=base.type,
                            terrains=list(base.terrains),
                            score=base.score,
                            name=base.name,
                        )
                    )
                else:
                    starts.append(ResourceData(type=rid, name=str(rname)))
            self.starting_resources[tribe_id] = starts

        if not self.resources:
            self._load_fallback()

    def _load_fallback(self) -> None:
        """Minimal hard-coded table if JSON is absent."""
        self.resources = [
            ResourceData(int(Resource.FRUIT), [int(Terrain.FIELD)], 1.0, "fruit"),
            ResourceData(int(Resource.CROP), [int(Terrain.FIELD)], 1.0, "crop"),
            ResourceData(int(Resource.GAME), [int(Terrain.FOREST)], 1.0, "game"),
            ResourceData(int(Resource.METAL), [int(Terrain.MOUNTAIN)], 1.0, "metal"),
            ResourceData(int(Resource.FISH), [int(Terrain.WATER), int(Terrain.OCEAN)], 1.0, "fish"),
            ResourceData(int(Resource.SPORES), [int(Terrain.FIELD), int(Terrain.FOREST)], 1.0, "spores"),
            ResourceData(int(Resource.AQUACROP), [int(Terrain.WATER), int(Terrain.OCEAN)], 1.0, "aquacrop"),
            ResourceData(
                int(Resource.STARFISH),
                [int(Terrain.WATER), int(Terrain.OCEAN)],
                0.5,
                "starfish",
            ),
        ]
        self.resources_by_type = {r.type: r for r in self.resources}


_TABLES: Optional[_GameLogicTables] = None


def get_tables() -> _GameLogicTables:
    global _TABLES
    if _TABLES is None:
        _TABLES = _GameLogicTables()
    return _TABLES


def reload_tables(path: Optional[Path] = None) -> _GameLogicTables:
    """Force re-read (tests / alternate versions)."""
    global _TABLES
    _TABLES = _GameLogicTables(path)
    return _TABLES


# --------------------------------------------------------------------------- public API


def default_resources() -> List[ResourceData]:
    return list(get_tables().resources)


def resources_for_terrain(terrain: int) -> List[ResourceData]:
    return [
        r
        for r in get_tables().resources
        if terrain in r.terrains or not r.terrains
    ]


def resource_allowed_for_climate(climate: int, resource_type: int) -> bool:
    """Gate specialty / removed resources using GameLogic modifiers + hard rules."""
    rt = int(resource_type)
    cl = int(climate)
    if rt == int(Resource.WHALE):
        return False
    tables = get_tables()
    mods = tables.resource_modifier.get(cl, {})
    if rt in _SPECIALTY_RESOURCES:
        # Only tribes that list the specialty (e.g. cymanti→spores, aquarion→aquacrop).
        return rt in mods and mods[rt] > 0
    # Explicit zero in modifier disables (e.g. bardur/cymanti crop: 0).
    if rt in mods and mods[rt] <= 0:
        return False
    return True


def tribe_terrain_bias(tribe: int) -> Tuple[float, float, float]:
    """(forest, mountain, ice) probabilities for FIELD conversion.

    ``terrainModifier`` values from JSON multiply base forest/mountain rates.
    Ice is only for Polaris climate (JSON has no ice modifier).
    """
    mods = get_tables().terrain_modifier.get(int(tribe), {})
    forest = _BASE_FOREST * float(mods.get("forest", 1.0))
    mountain = _BASE_MOUNTAIN * float(mods.get("mountain", 1.0))
    ice = _POLARIS_ICE if int(tribe) == int(Tribe.POLARIS) else 0.0
    return (forest, mountain, ice)


def resource_weight(tribe: int, resource_type: int, base: float = 1.0) -> float:
    if not resource_allowed_for_climate(tribe, resource_type):
        return 0.0
    mods = get_tables().resource_modifier.get(int(tribe), {})
    mult = float(mods.get(int(resource_type), 1.0))
    return base * mult


def starting_resources_for_tribe(tribe: int) -> List[ResourceData]:
    starts = get_tables().starting_resources.get(int(tribe))
    if starts:
        return list(starts)
    # Generic fallback when tribe missing from JSON.
    return [
        ResourceData(int(Resource.FRUIT), [int(Terrain.FIELD)], 1.0, "fruit"),
        ResourceData(int(Resource.CROP), [int(Terrain.FIELD)], 1.0, "crop"),
    ]


class GameLogicData:
    def __init__(self, version: int = 0) -> None:
        tables = get_tables()
        self.version = version or tables.version
        self.resources = default_resources()

    def GetResources(self) -> List[ResourceData]:
        return list(self.resources)


def resolve_game_logic(state) -> GameLogicData:
    if getattr(state, "mocked_game_logic_data", None) is not None:
        gld = state.mocked_game_logic_data
        if isinstance(gld, GameLogicData):
            return gld
    return GameLogicData(getattr(state, "version", 0))
