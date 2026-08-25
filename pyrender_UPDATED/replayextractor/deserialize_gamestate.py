#!/usr/bin/env python3
"""Deserialize Polytopia ``currentGameStateData`` bytes into ``gamestate.GameState``.

The API blob is uncompressed little-endian ``BinaryWriter`` output:

1. ``int`` format version (same value passed to ``Serialize``)
2. ``GameState.Serialize`` for that version (verified against GameAssembly v122)

Usage
-----
    python3 deserialize_gamestate.py finished.gamestate.bin
    python3 deserialize_gamestate.py finished.json -o state.json
    python3 get_game_data.py <share> --bin out.bin && python3 deserialize_gamestate.py out.bin
"""

from __future__ import annotations

import argparse
import base64
import json
import struct
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Allow importing pyrender_UPDATED.gamestate when run from this folder.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gamestate import (  # noqa: E402
    ActionRecord,
    CommandRecord,
    CommandTrigger,
    GameSettings,
    GameState,
    ImprovementState,
    MapData,
    PlayerState,
    ResourceState,
    TileData,
    UnitState,
    WorldCoordinates,
)
try:
    from .history_layouts import ACTION_LAYOUTS, COMMAND_LAYOUTS  # noqa: E402
except ImportError:  # running as a script from this folder
    from history_layouts import ACTION_LAYOUTS, COMMAND_LAYOUTS  # noqa: E402

# TaskData.Type values that carry an extra int after the two TaskBase bools.
_TASK_WITH_COUNTER = {1, 5, 7, 9}  # Pacifist, Killer, Explorer, Convert


class BinaryReader:
    """Little-endian reader matching ``System.IO.BinaryReader`` primitives."""

    def __init__(self, data: bytes, pos: int = 0) -> None:
        self.data = data
        self.pos = pos

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EOFError(
                f"need {n} bytes at {self.pos}, only {self.remaining()} left"
            )
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def u8(self) -> int:
        return self.take(1)[0]

    def i8(self) -> int:
        return struct.unpack("<b", self.take(1))[0]

    def bool(self) -> bool:
        return self.u8() != 0

    def u16(self) -> int:
        return struct.unpack("<H", self.take(2))[0]

    def i16(self) -> int:
        return struct.unpack("<h", self.take(2))[0]

    def u32(self) -> int:
        return struct.unpack("<I", self.take(4))[0]

    def i32(self) -> int:
        return struct.unpack("<i", self.take(4))[0]

    def f32(self) -> float:
        return struct.unpack("<f", self.take(4))[0]

    def string(self) -> str:
        # BinaryWriter 7-bit encoded length + UTF-8
        n = 0
        shift = 0
        while True:
            b = self.u8()
            n |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
            if shift > 35:
                raise ValueError("invalid 7-bit string length")
        return self.take(n).decode("utf-8")

    def coords(self) -> WorldCoordinates:
        return WorldCoordinates(self.i32(), self.i32())


def _read_improvement(r: BinaryReader) -> ImprovementState:
    typ = r.u16()
    level = r.u16()
    founded = r.u16()
    xp = r.i16()
    population = r.i16()
    production = r.u16()
    base_score = r.u16()
    border_size = r.u16()
    upgrade = r.u16()
    connected = r.u8()
    has_name = r.bool()
    name = r.string() if has_name else ""
    founder = r.u8()
    n_rewards = r.u16()
    rewards = [r.u16() for _ in range(n_rewards)]
    n_effects = r.u16()
    effects = [r.u16() for _ in range(n_effects)]
    return ImprovementState(
        type=typ,
        founder=founder,
        level=level,
        founded=founded,
        xp=xp,
        population=population,
        production=production,
        base_score=base_score,
        border_size=border_size,
        upgrade=upgrade,
        connected_to_capital_of_player=connected,
        name=name,
        rewards=rewards,
        effects=effects,
    )


def _read_unit(r: BinaryReader, version: int) -> UnitState:
    uid = r.u32()
    owner = r.u8()
    typ = r.u16()
    follower = r.u32()
    leader = r.u32()
    coordinates = r.coords()
    home = r.coords()
    health = r.u16()
    promotion_level = r.u16()
    xp = r.u16()
    moved = r.bool()
    attacked = r.bool()
    flipped = r.bool()
    created_turn = r.u16()
    passenger = _read_unit(r, version) if r.bool() else None
    n_effects = r.u16()
    effects = [r.u16() for _ in range(n_effects)]
    birth_climate = r.i16() & 0xFFFF  # stored as int16; TribeType is unsigned-ish
    direction = r.u8()
    birth_skin = r.u16() if version >= 0x57 else 0
    return UnitState(
        id=uid,
        leader=leader,
        follower=follower,
        owner=owner,
        birth_climate=birth_climate,
        birth_climate_skin_type=birth_skin,
        type=typ,
        coordinates=coordinates,
        home=home,
        passenger_unit=passenger,
        health=health,
        promotion_level=promotion_level,
        xp=xp,
        moved=moved,
        attacked=attacked,
        direction=direction,
        flipped=flipped,
        created_turn=created_turn,
        effects=effects,
    )


def _read_tile(r: BinaryReader, version: int) -> TileData:
    coordinates = r.coords()
    terrain = r.u16()
    climate = r.i16() & 0xFFFF
    altitude = r.i16()
    owner = r.u8()
    capital_of = r.u8()
    ruling = r.coords()
    resource = ResourceState(type=r.u16()) if r.bool() else None
    improvement = _read_improvement(r) if r.bool() else None
    unit = _read_unit(r, version) if r.bool() else None
    n_vis = r.u8()
    explorers = [r.u8() for _ in range(n_vis)]
    has_road = r.bool()
    has_route = r.bool()
    skin = 0
    effects: List[int] = []
    if version >= 0x56:
        skin = r.i32()
        if version >= 0x69:
            n_eff = r.u8()
            effects = [r.i32() for _ in range(n_eff)]
    return TileData(
        coordinates=coordinates,
        terrain=terrain,
        climate=climate,
        skin=skin,
        effects=effects,
        altitude=altitude,
        owner=owner,
        capital_of=capital_of,
        explorers=explorers,
        ruling_city_coordinates=ruling,
        improvement=improvement,
        resource=resource,
        unit=unit,
        has_road=has_road,
        has_route=has_route,
    )


def _read_task(r: BinaryReader, version: int) -> Dict[str, Any]:
    """Read one task (type ushort + body). Returned as a plain dict."""
    typ = r.u16()
    is_started = r.bool()
    is_completed = r.bool()
    counter = None
    if typ in _TASK_WITH_COUNTER:
        counter = r.i32()
    return {
        "type": typ,
        "is_started": is_started,
        "is_completed": is_completed,
        "counter": counter,
    }


def _read_diplomacy_relation(r: BinaryReader, version: int) -> Dict[str, Any]:
    state = r.u8()
    last_attack = r.i32()
    embassy_level = r.u8()
    last_peace_broken = r.i32()
    first_meet = r.i32()
    embassy_build = r.i32()
    previous_attack = r.i32() if version >= 0x51 else -100
    return {
        "state": state,
        "last_attack_turn": last_attack,
        "embassy_level": embassy_level,
        "last_peace_broken_turn": last_peace_broken,
        "first_meet": first_meet,
        "embassy_build_turn": embassy_build,
        "previous_attack_turn": previous_attack,
    }


def _read_player(r: BinaryReader, version: int) -> PlayerState:
    pid = r.u8()
    user_name = r.string()
    account_id = r.string()  # Nullable<Guid> as string (empty if none)
    auto_play = r.bool()
    start_tile = r.coords()
    tribe = r.u16()
    has_chosen_tribe = r.bool()
    handicap = r.i32()

    aggressions: Dict[int, int] = {}
    if version <= 0x70:
        n_agg = r.u16()
        for _ in range(n_agg):
            k = r.u8()
            v = r.i32()
            aggressions[k] = v

    currency = r.i32()
    score = r.u32()
    end_score = r.u32()
    cities = r.u16()

    n_tech = r.u16()
    available_tech = [r.u16() for _ in range(n_tech)]

    n_known = r.u16()
    known_players = [r.u8() for _ in range(n_known)]

    n_tasks = r.u16()
    tasks = [_read_task(r, version) for _ in range(n_tasks)]

    kills = r.u32()
    casualities = r.u32()
    wipe_outs = r.u32()
    color = r.i32()
    tribe_mix = r.u8()

    n_unique = r.u16()
    built_unique = [r.i16() & 0xFFFF for _ in range(n_unique)]

    relations: Dict[int, Any] = {}
    messages: List[Any] = []
    killer_id = 0
    killed_turn = 0
    resigned_at = 0
    wiped_at = 0
    skin_type = 0
    resigned_turn = 0
    climate = 0

    if version >= 0x3C:
        n_rel = r.u16()
        for _ in range(n_rel):
            other = r.u8()
            relations[other] = _read_diplomacy_relation(r, version)
        n_msg = r.u16()
        messages = [{"type": r.u8(), "sender": r.u8()} for _ in range(n_msg)]
        killer_id = r.u8()
        killed_turn = r.u32()
        if version > 0x45:
            resigned_at = r.i32()
            wiped_at = r.i32()
            if version >= 0x56:
                skin_type = r.u16()
                if version >= 0x5D:
                    resigned_turn = r.i32()
                    if version >= 0x79:
                        climate = r.u8()

    return PlayerState(
        id=pid,
        user_name=user_name,
        account_id=account_id or None,
        auto_play=auto_play,
        start_tile=start_tile,
        tribe=tribe,
        tribe_mix=tribe_mix,
        climate=climate or tribe,
        has_chosen_tribe=has_chosen_tribe,
        handicap=handicap,
        resigned_turn=resigned_turn,
        resigned_at_command_index=resigned_at,
        wiped_at_command_index=wiped_at,
        available_tech=available_tech,
        tasks=tasks,
        aggressions=aggressions,
        known_players=known_players,
        built_unique_improvements=built_unique,
        relations=relations,
        messages=messages,
        skin_type=skin_type,
        currency=currency,
        score=score,
        end_score=end_score,
        cities=cities,
        kills=kills,
        casualities=casualities,
        wipe_outs=wipe_outs,
        killer_id=killer_id,
        killed_turn=killed_turn,
        color=color,
    )


def _read_settings(r: BinaryReader, version: int) -> GameSettings:
    # GameRules.SerializeDefault
    _turn_limit = r.i32()
    _score_limit = r.i32()
    _win_by_capital = r.bool()
    _allow_mirror = r.bool()
    _allow_special = r.bool()
    _win_by_exterm = r.bool()
    _allow_tech_share = r.bool()
    _death_cond = r.u16()

    _base_mode = r.u8()
    _rules_mode = r.u8()
    game_name = r.string()
    map_size = r.i32()

    n_dis = r.u16()
    disabled = [r.u16() for _ in range(n_dis)]
    n_unl = r.u16()
    _unlocked = [r.u16() for _ in range(n_unl)]

    _difficulty = r.u16()
    opponent_count = r.i32()
    game_type = r.u16()
    map_preset = r.u8()
    _time_limit = r.i32()
    _tb_city = r.f32()
    _tb_pop = r.f32()
    _base_time = r.f32()
    _use_dyn = r.bool()
    _use_banks = r.bool()
    _live = r.bool()
    _autoskip = r.bool()

    if version >= 0x56:
        n_skins = r.i32()
        for _ in range(n_skins):
            r.u16()
            r.u16()
        if version >= 0x7A:
            west = r.string()
        else:
            west = ""
    else:
        west = ""

    return GameSettings(
        map_preset=map_preset,
        map_size=map_size,
        game_name=game_name,
        game_type=game_type,
        opponent_count=opponent_count,
        disabled_tribes=disabled,
        west_map_placement_user_id=west or None,
    )


def _read_coords(r: BinaryReader) -> WorldCoordinates:
    return WorldCoordinates(r.i32(), r.i32())


def _read_command_trigger(r: BinaryReader, version: int) -> CommandTrigger:
    """CommandTrigger.Serialize: playerId, type(ushort), coords, [opponentId]."""
    player_id = r.u8()
    trigger_type = r.u16()
    coordinates = _read_coords(r)
    opponent_id = r.u8() if version >= 0x3C else 0
    return CommandTrigger(
        player_id=player_id,
        opponent_id=opponent_id,
        type=trigger_type,
        coordinates=coordinates,
    )


def _read_layout_fields(
    r: BinaryReader,
    layout: List[tuple],
    version: int,
) -> Dict[str, Any]:
    """Read Serialize body fields into a plain dict (coords as {x,y})."""
    out: Dict[str, Any] = {}
    for kind, name in layout:
        if kind in ("player", "byte"):
            out[name] = r.u8()
        elif kind == "bool":
            out[name] = r.bool()
        elif kind == "ushort":
            out[name] = r.u16()
        elif kind == "int":
            out[name] = r.i32()
        elif kind == "uint":
            out[name] = r.u32()
        elif kind == "coords":
            c = _read_coords(r)
            out[name] = {"x": c.x, "y": c.y}
        elif kind == "coords_list":
            n = r.i32()
            if n < 0 or n > 10_000:
                raise ValueError(f"coords_list {name} count={n}")
            out[name] = [
                {"x": c.x, "y": c.y}
                for c in (_read_coords(r) for _ in range(n))
            ]
        elif kind == "byte_list":
            n = r.i32()
            if n < 0 or n > 10_000:
                raise ValueError(f"byte_list {name} count={n}")
            out[name] = [r.u8() for _ in range(n)]
        elif kind == "trigger_list":
            n = r.u16()
            out[name] = [
                {
                    "player_id": t.player_id,
                    "opponent_id": t.opponent_id,
                    "type": t.type,
                    "coordinates": {
                        "x": t.coordinates.x,
                        "y": t.coordinates.y,
                    },
                }
                for t in (
                    _read_command_trigger(r, version) for _ in range(n)
                )
            ]
        else:
            raise ValueError(f"unknown layout kind {kind!r}")
    return out


def _read_command(r: BinaryReader, version: int) -> CommandRecord:
    ctype = r.u16()
    layout = COMMAND_LAYOUTS.get(ctype)
    if layout is None:
        raise ValueError(f"unsupported CommandType {ctype} at pos {r.pos - 2}")
    fields_layout = list(layout)
    # ResignCommand: kicker + was_kicked only when version >= 0x5d.
    if ctype == 35 and version < 0x5D:
        fields_layout = fields_layout[:2]
    body = _read_layout_fields(r, fields_layout, version)
    player_id = int(body.pop("player_id", 0))
    return CommandRecord(type=ctype, player_id=player_id, fields=body)


def _read_action(r: BinaryReader, version: int) -> ActionRecord:
    atype = r.u16()
    layout = ACTION_LAYOUTS.get(atype)
    if layout is None:
        raise ValueError(f"unsupported ActionType {atype} at pos {r.pos - 2}")
    fields_layout = list(layout)
    # ResignAction: resigned/kicker/was_kicked only when version >= 0x5d.
    if atype == 84 and version < 0x5D:
        fields_layout = [
            f for f in fields_layout if f[0] in ("player", "trigger_list")
        ]
    body = _read_layout_fields(r, fields_layout, version)
    player_id = int(body.pop("player_id", 0))
    return ActionRecord(type=atype, player_id=player_id, fields=body)


def _read_history(
    r: BinaryReader, version: int
) -> tuple:
    """pendingCommandTriggers, CommandStack, ActionStack, then trailing flags."""
    n_triggers = r.u16()
    triggers = [_read_command_trigger(r, version) for _ in range(n_triggers)]

    n_commands = r.u16()
    commands = [_read_command(r, version) for _ in range(n_commands)]

    n_actions = r.u16()
    actions = [_read_action(r, version) for _ in range(n_actions)]

    flagged = False
    village_seed = 0
    if version >= 0x62:
        flagged = r.bool()
    if version >= 0x7A:
        village_seed = r.i32()

    return triggers, commands, actions, flagged, village_seed


def deserialize(data: bytes) -> GameState:
    """Parse API / disk ``GameState`` bytes into a Python ``GameState``."""
    r = BinaryReader(data)
    # Disk/API wrapper writes the format version, then GameState.Serialize
    # which writes Version again (same int).
    outer_version = r.i32()
    version = r.i32()
    if version != outer_version:
        raise ValueError(
            f"version mismatch: outer={outer_version} GameState.Version={version}"
        )

    current_command = r.u16()
    current_turn = r.u32()
    current_player_index = r.u8()
    current_unit_id = r.u32()
    current_state = r.u8()
    seed = r.i32()

    settings = _read_settings(r, version)

    width = r.u16()
    height = r.u16()
    tiles = [_read_tile(r, version) for _ in range(width * height)]
    # Ensure row-major order by coordinates (serializer already emits x + y*w).
    tiles.sort(key=lambda t: (t.coordinates.y, t.coordinates.x))

    n_players = r.u16()
    players = [_read_player(r, version) for _ in range(n_players)]

    triggers, commands, actions, flagged, village_seed = _read_history(r, version)

    if r.remaining() != 0:
        raise ValueError(
            f"trailing {r.remaining()} bytes after GameState at pos {r.pos}"
        )

    return GameState(
        version=version,
        seed=seed,
        village_name_seed=village_seed,
        current_turn=current_turn,
        current_player_index=current_player_index,
        current_unit_id=current_unit_id,
        current_state=current_state,
        settings=settings,
        map=MapData(width=width, height=height, tiles=tiles),
        player_states=players,
        current_command=current_command,
        command_stack=commands,
        action_stack=actions,
        pending_command_triggers=triggers,
        has_flagged_need_for_update_routes=flagged,
    )


def load_bytes(path: Path) -> bytes:
    raw = path.read_bytes()
    if path.suffix.lower() == ".json" or raw[:1] in (b"{", b"["):
        obj = json.loads(raw.decode("utf-8"))
        b64 = obj.get("current_game_state_data") or obj.get("currentGameStateData")
        if not b64:
            raise ValueError(f"no current_game_state_data in {path}")
        return base64.b64decode(b64)
    return raw


def game_state_summary(gs: GameState) -> dict:
    m = gs.map
    assert m is not None
    cities = [
        {
            "x": t.x,
            "y": t.y,
            "name": t.improvement.name if t.improvement else "",
            "owner": t.owner,
            "type": t.improvement.type if t.improvement else None,
        }
        for t in m.tiles
        if t.improvement and t.improvement.name
    ]
    return {
        "version": gs.version,
        "seed": gs.seed,
        "turn": gs.current_turn,
        "state": gs.current_state,
        "name": gs.settings.game_name if gs.settings else "",
        "map": f"{m.width}x{m.height}",
        "players": [
            {
                "id": p.id,
                "name": p.user_name,
                "tribe": p.tribe,
                "score": p.score,
                "currency": p.currency,
            }
            for p in gs.player_states
        ],
        "cities": cities,
        "units": sum(1 for t in m.tiles if t.unit),
        "improvements": sum(1 for t in m.tiles if t.improvement),
        "commands": len(gs.command_stack),
        "actions": len(gs.action_stack),
        "pending_triggers": len(gs.pending_command_triggers),
    }


def _tile_to_dict(t: TileData) -> dict:
    d: dict = {
        "coordinates": {"x": t.x, "y": t.y},
        "terrain": t.terrain,
        "climate": t.climate,
        "skin": t.skin,
        "effects": t.effects,
        "altitude": t.altitude,
        "owner": t.owner,
        "capital_of": t.capital_of,
        "explorers": t.explorers,
        "ruling_city_coordinates": {
            "x": t.ruling_city_coordinates.x,
            "y": t.ruling_city_coordinates.y,
        },
        "has_road": t.has_road,
        "has_route": t.has_route,
    }
    if t.resource:
        d["resource"] = {"type": t.resource.type}
    if t.improvement:
        imp = t.improvement
        d["improvement"] = {
            "type": imp.type,
            "founder": imp.founder,
            "level": imp.level,
            "founded": imp.founded,
            "xp": imp.xp,
            "population": imp.population,
            "production": imp.production,
            "base_score": imp.base_score,
            "border_size": imp.border_size,
            "upgrade": imp.upgrade,
            "connected_to_capital_of_player": imp.connected_to_capital_of_player,
            "name": imp.name,
            "rewards": imp.rewards,
            "effects": imp.effects,
        }
    if t.unit:
        u = t.unit
        d["unit"] = {
            "id": u.id,
            "leader": u.leader,
            "follower": u.follower,
            "owner": u.owner,
            "birth_climate": u.birth_climate,
            "birth_climate_skin_type": u.birth_climate_skin_type,
            "type": u.type,
            "coordinates": {"x": u.coordinates.x, "y": u.coordinates.y},
            "home": {"x": u.home.x, "y": u.home.y},
            "health": u.health,
            "promotion_level": u.promotion_level,
            "xp": u.xp,
            "moved": u.moved,
            "attacked": u.attacked,
            "direction": u.direction,
            "flipped": u.flipped,
            "created_turn": u.created_turn,
            "effects": u.effects,
        }
    return d


def _trigger_to_dict(t: CommandTrigger) -> dict:
    return {
        "player_id": t.player_id,
        "opponent_id": t.opponent_id,
        "type": t.type,
        "coordinates": {"x": t.coordinates.x, "y": t.coordinates.y},
    }


def _command_to_dict(c: CommandRecord) -> dict:
    return {"type": c.type, "player_id": c.player_id, "fields": c.fields}


def _action_to_dict(a: ActionRecord) -> dict:
    return {"type": a.type, "player_id": a.player_id, "fields": a.fields}


def game_state_to_dict(gs: GameState) -> dict:
    """Export a JSON-friendly dict compatible with ``gamestate.from_dict`` basics."""
    assert gs.map is not None
    settings = gs.settings
    return {
        "version": gs.version,
        "seed": gs.seed,
        "village_name_seed": gs.village_name_seed,
        "current_turn": gs.current_turn,
        "current_player_index": gs.current_player_index,
        "current_unit_id": gs.current_unit_id,
        "current_state": gs.current_state,
        "current_command": gs.current_command,
        "has_flagged_need_for_update_routes": gs.has_flagged_need_for_update_routes,
        "settings": {
            "map_preset": settings.map_preset if settings else 0,
            "map_size": settings.map_size if settings else 0,
            "game_name": settings.game_name if settings else "",
            "game_type": settings.game_type if settings else 0,
            "opponent_count": settings.opponent_count if settings else 0,
            "disabled_tribes": list(settings.disabled_tribes) if settings else [],
        },
        "map": {
            "width": gs.map.width,
            "height": gs.map.height,
            "tiles": [_tile_to_dict(t) for t in gs.map.tiles],
        },
        "player_states": [
            {
                "id": p.id,
                "user_name": p.user_name,
                "account_id": p.account_id,
                "auto_play": p.auto_play,
                "start_tile": {"x": p.start_tile.x, "y": p.start_tile.y},
                "tribe": p.tribe,
                "tribe_mix": p.tribe_mix,
                "climate": p.climate,
                "has_chosen_tribe": p.has_chosen_tribe,
                "handicap": p.handicap,
                "available_tech": p.available_tech,
                "known_players": p.known_players,
                "built_unique_improvements": p.built_unique_improvements,
                "skin_type": p.skin_type,
                "currency": p.currency,
                "score": p.score,
                "end_score": p.end_score,
                "cities": p.cities,
                "kills": p.kills,
                "casualities": p.casualities,
                "wipe_outs": p.wipe_outs,
                "killer_id": p.killer_id,
                "killed_turn": p.killed_turn,
                "color": p.color,
                "resigned_turn": p.resigned_turn,
            }
            for p in gs.player_states
        ],
        "pending_command_triggers": [
            _trigger_to_dict(t) for t in gs.pending_command_triggers
        ],
        "command_stack": [_command_to_dict(c) for c in gs.command_stack],
        "action_stack": [_action_to_dict(a) for a in gs.action_stack],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        type=Path,
        help="Raw .bin from get_game_data.py --bin, or JSON containing "
        "current_game_state_data",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write full JSON GameState (renderer-oriented) to this path",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a short summary on stdout (default: full JSON)",
    )
    args = parser.parse_args()

    try:
        raw = load_bytes(args.input)
        gs = deserialize(raw)
    except Exception as e:
        print(f"deserialize failed: {e}", file=sys.stderr)
        return 1

    summary = game_state_summary(gs)
    print(
        f"{summary['name']!r} v{summary['version']} turn={summary['turn']} "
        f"{summary['map']} players={len(summary['players'])} "
        f"cities={len(summary['cities'])} units={summary['units']} "
        f"commands={summary['commands']} actions={summary['actions']}",
        file=sys.stderr,
    )

    if args.output:
        args.output.write_text(
            json.dumps(game_state_to_dict(gs), indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.output}", file=sys.stderr)

    payload = summary if args.summary else game_state_to_dict(gs)
    if args.summary or not args.output:
        json.dump(payload, sys.stdout, indent=2)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
