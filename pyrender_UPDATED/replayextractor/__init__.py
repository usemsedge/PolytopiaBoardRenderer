"""Share link → API blob → Python ``GameState``.

Typical use (with ``pyrender_UPDATED`` on ``sys.path``)::

    from replayextractor import fetch_gamestate, game_state_to_dict

    gs = fetch_gamestate("https://share.polytopia.io/g/<uuid>")
    print(gs.current_turn, len(gs.command_stack))

Or step by step::

    from replayextractor import load_jwt, fetch_game_data, deserialize, game_state_bytes

    out = fetch_game_data(share_link)
    gs = deserialize(game_state_bytes(out))
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from .get_jwt import find_jwt_files, load_jwt, newest_jwt
from .get_game_data import (
    STATE_ENDED,
    build_output,
    fetch_game_data,
    fetch_game_view_model,
    game_state_bytes,
    parse_game_id,
)
from .deserialize_gamestate import (
    BinaryReader,
    deserialize,
    game_state_summary,
    game_state_to_dict,
    load_bytes,
)

if TYPE_CHECKING:
    from gamestate import GameState

__all__ = [
    # JWT
    "find_jwt_files",
    "newest_jwt",
    "load_jwt",
    # Fetch
    "STATE_ENDED",
    "parse_game_id",
    "fetch_game_view_model",
    "build_output",
    "fetch_game_data",
    "game_state_bytes",
    # Deserialize
    "BinaryReader",
    "deserialize",
    "load_bytes",
    "game_state_to_dict",
    "game_state_summary",
    # One-shot
    "fetch_gamestate",
]


def fetch_gamestate(
    share_link: str,
    *,
    jwt: Optional[str] = None,
    allow_unfinished: bool = False,
) -> "GameState":
    """Share URL/UUID → deserialized ``gamestate.GameState``."""
    out = fetch_game_data(
        share_link, jwt=jwt, allow_unfinished=allow_unfinished
    )
    return deserialize(game_state_bytes(out))
