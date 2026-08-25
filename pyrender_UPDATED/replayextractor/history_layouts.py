"""Binary field layouts for CommandBase / ActionBase Serialize bodies.

Each layout is an ordered list of ``(kind, name)`` after the leading type
``ushort`` written by ``GameState.SerializeCommand`` / ``SerializeAction``.

Kinds
-----
player, byte, bool, ushort, int, uint, coords, coords_list, byte_list,
trigger_list

``player`` is Write(byte) of ``PlayerId`` (same wire size as ``byte``).
``coords_list`` / ``byte_list`` use Write(int) count; ``trigger_list`` uses
Write(ushort) count then each ``CommandTrigger.Serialize``.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

Field = Tuple[str, str]
Layout = List[Field]

# CommandType -> body layout (from Command*.Serialize, GameAssembly).
COMMAND_LAYOUTS: Dict[int, Layout] = {
    1: [("player", "player_id"), ("ushort", "type"), ("coords", "coordinates")],
    2: [
        ("player", "player_id"),
        ("uint", "unit_id"),
        ("coords", "origin"),
        ("coords", "target"),
    ],
    3: [("player", "player_id"), ("coords", "coordinates")],
    4: [("player", "player_id"), ("coords", "coordinates")],
    5: [("player", "player_id"), ("ushort", "type"), ("coords", "coordinates")],
    6: [
        ("player", "player_id"),
        ("coords", "from"),
        ("coords", "to"),
        ("uint", "unit_id"),
    ],
    7: [
        ("player", "player_id"),
        ("uint", "unit_id"),
        ("coords", "coordinates"),
    ],
    8: [("player", "player_id"), ("ushort", "type")],
    9: [("player", "player_id"), ("coords", "coordinates")],
    10: [("player", "player_id"), ("coords", "coordinates")],
    # CityReward: coordinates then reward (Serialize order).
    11: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("ushort", "reward"),
    ],
    13: [("player", "player_id"), ("coords", "coordinates")],
    14: [("player", "player_id"), ("coords", "coordinates")],
    15: [("player", "player_id")],
    16: [("player", "player_id"), ("ushort", "type"), ("coords", "coordinates")],
    17: [("player", "player_id"), ("coords", "coordinates")],
    # BreakIce: What is not serialized.
    18: [("player", "player_id"), ("coords", "coordinates")],
    20: [("player", "player_id")],
    21: [("player", "player_id"), ("coords", "coordinates")],
    22: [("player", "player_id")],
    24: [("player", "player_id"), ("coords", "coordinates")],
    25: [("player", "player_id"), ("coords", "coordinates")],
    26: [("player", "player_id"), ("coords", "coordinates")],
    27: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("byte", "opponent_id"),
    ],
    28: [
        ("player", "player_id"),
        ("byte", "opponent_id"),
        ("bool", "accepted"),
    ],
    29: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("byte", "opponent_id"),
    ],
    30: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("byte", "opponent_id"),
    ],
    32: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("byte", "opponent_id"),
    ],
    33: [("player", "player_id"), ("coords", "coordinates")],
    # Resign: kicker + was_kicked only when version >= 0x5d (handled in reader).
    35: [
        ("player", "player_id"),
        ("byte", "resigned_player_id"),
        ("byte", "kicker_player_id"),
        ("bool", "was_kicked"),
    ],
    36: [("player", "player_id"), ("coords", "coordinates")],
    37: [("player", "player_id"), ("coords", "coordinates")],
    38: [("player", "player_id"), ("coords", "coordinates")],
    # ClearTileEffect: effect ushort before coordinates.
    39: [
        ("player", "player_id"),
        ("ushort", "effect"),
        ("coords", "coordinates"),
    ],
}

# ActionType -> body layout (Action*.Serialize). Hand-checked for common types;
# remaining entries mirror Serialize field order from GameAssembly.
ACTION_LAYOUTS: Dict[int, Layout] = {
    1: [
        ("player", "player_id"),
        ("ushort", "type"),
        ("coords", "coordinates"),
        ("bool", "deduct_cost"),
    ],
    2: [
        ("player", "player_id"),
        ("int", "damage"),
        ("coords", "origin"),
        ("coords", "target"),
        ("ushort", "animation"),
        ("bool", "should_move_to_target"),
        ("ushort", "delay"),
    ],
    3: [("player", "player_id"), ("coords", "coordinates")],
    4: [("player", "player_id"), ("coords", "coordinates")],
    5: [
        ("player", "player_id"),
        ("ushort", "type"),
        ("coords", "coordinates"),
        ("int", "cost"),
    ],
    6: [
        ("player", "player_id"),
        ("uint", "unit_id"),
        ("coords_list", "path"),
        ("bool", "should_animate"),
        ("byte", "reason"),
    ],
    7: [("player", "player_id"), ("coords", "coordinates")],
    8: [("player", "player_id"), ("ushort", "type"), ("int", "cost")],
    9: [("player", "player_id"), ("coords", "coordinates")],
    10: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("coords", "home_coordinates"),
        ("bool", "get_paid"),
    ],
    11: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("ushort", "reward"),
    ],
    12: [
        ("player", "player_id"),
        ("byte", "other_player_id"),
        ("coords", "coordinates"),
    ],
    13: [("player", "player_id"), ("coords", "coordinates")],
    14: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("ushort", "reward"),
    ],
    15: [("player", "player_id")],
    16: [
        ("player", "player_id"),
        ("ushort", "type"),
        ("coords", "coordinates"),
        ("int", "cost"),
    ],
    17: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("ushort", "radius"),
        ("bool", "freeze_units"),
        ("bool", "only_owned_tiles"),
    ],
    18: [("player", "player_id")],
    19: [("player", "player_id"), ("coords", "coordinates")],
    20: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("byte", "old_owner_id"),
    ],
    21: [("player", "player_id"), ("coords", "coordinates")],
    22: [("player", "player_id")],
    23: [("player", "player_id"), ("coords", "coordinates")],
    24: [("player", "player_id"), ("coords", "source")],
    25: [("player", "player_id"), ("coords", "coordinates")],
    26: [
        ("player", "player_id"),
        ("int", "delay"),
        ("coords", "source"),
        ("coords", "target"),
    ],
    27: [
        ("player", "player_id"),
        ("int", "amount"),
        ("int", "delay"),
        ("coords", "source"),
    ],
    28: [
        ("player", "player_id"),
        ("int", "delay"),
        ("coords", "source"),
        ("int", "amount"),
    ],
    29: [("player", "player_id")],
    30: [
        ("player", "player_id"),
        ("uint", "unit_id"),
        ("uint", "remaining_moves"),
        ("uint", "seed"),
        ("coords", "from"),
        ("coords_list", "path"),
    ],
    31: [("player", "player_id"), ("byte_list", "players_to_update")],
    32: [
        ("player", "player_id"),
        ("int", "delay"),
        ("coords", "target"),
    ],
    34: [("player", "player_id"), ("coords", "coordinates")],
    35: [("player", "player_id"), ("coords", "coordinates")],
    36: [("player", "player_id"), ("ushort", "tribe")],
    37: [("player", "player_id"), ("byte", "winning_player_id")],
    38: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("ushort", "fixed_heal_amount"),
    ],
    39: [("player", "player_id")],
    40: [("player", "player_id"), ("coords", "coordinates")],
    41: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("ushort", "amount"),
    ],
    42: [
        ("player", "player_id"),
        ("coords", "origin"),
        ("coords", "target"),
    ],
    43: [
        ("player", "player_id"),
        ("int", "damage"),
        ("coords", "origin"),
        ("coords", "target"),
    ],
    44: [("player", "player_id"), ("int", "type")],
    45: [("player", "player_id")],
    46: [("player", "player_id"), ("coords", "coordinates")],
    47: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("int", "climate"),
    ],
    48: [("player", "player_id"), ("uint", "unit_id")],
    49: [("player", "player_id"), ("byte", "target_player_id")],
    50: [
        ("player", "player_id"),
        ("ushort", "type"),
        ("coords", "coordinates"),
        ("ushort", "reason"),
    ],
    51: [("player", "player_id"), ("coords", "coordinates")],
    52: [("player", "player_id"), ("coords", "target")],
    53: [("player", "player_id")],
    54: [("player", "player_id"), ("coords", "coordinates")],
    55: [("player", "player_id"), ("coords", "coordinates")],
    56: [("player", "player_id"), ("coords", "coordinates")],
    57: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("ushort", "radius"),
    ],
    58: [("player", "player_id")],
    59: [("player", "player_id"), ("int", "amount")],
    60: [("player", "player_id")],
    61: [("player", "player_id"), ("byte", "target_player_id")],
    62: [("player", "player_id"), ("ushort", "command_type")],
    63: [
        ("player", "player_id"),
        ("coords", "origin"),
        ("coords", "target"),
    ],
    64: [
        ("player", "player_id"),
        ("ushort", "eater"),
        ("coords", "coordinates"),
    ],
    66: [("player", "player_id"), ("coords", "coordinates")],
    68: [("player", "player_id"), ("coords", "coordinates")],
    69: [("player", "player_id"), ("coords", "coordinates")],
    70: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("coords", "home_coordinates"),
    ],
    71: [("player", "player_id"), ("coords", "coordinates")],
    72: [("player", "player_id"), ("byte", "sender_id")],
    73: [
        ("player", "player_id"),
        ("byte", "sender_id"),
        ("bool", "accepted"),
    ],
    74: [("player", "player_id"), ("byte", "opponent_id")],
    75: [("player", "player_id"), ("byte", "opponent_id")],
    76: [("player", "player_id"), ("byte", "opponent_id")],
    77: [("player", "player_id"), ("coords", "coordinates")],
    79: [("player", "player_id"), ("byte", "opponent_id")],
    80: [("player", "player_id"), ("coords", "coordinates")],
    81: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("coords", "origin"),
        ("bool", "show_reveal_popup"),
    ],
    82: [("player", "player_id"), ("coords", "coordinates")],
    83: [
        ("player", "player_id"),
        ("coords", "coordinates"),
        ("ushort", "reward"),
        ("ushort", "unit_type"),
    ],
    # Resign: trigger list then ids when version >= 0x5d (handled in reader).
    84: [
        ("player", "player_id"),
        ("trigger_list", "pending_command_triggers"),
        ("byte", "resigned_player_id"),
        ("byte", "kicker_player_id"),
        ("bool", "was_kicked"),
    ],
    85: [("player", "player_id")],
    86: [("player", "player_id"), ("uint", "unit_id"), ("bool", "add_bubble")],
    87: [("player", "player_id"), ("coords", "coordinates")],
    88: [
        ("player", "player_id"),
        ("ushort", "effect"),
        ("coords", "target"),
    ],
}
