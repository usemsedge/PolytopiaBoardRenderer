"""Player base colours — a faithful reproduction of ``GameLogicData.GetTribeColor``.

The engine derives a player's colour from its tribe and (optional) skin, NOT from a
free-floating stored value. ``GameLogicData.GetTribeColor(tribe, skin)`` (binary
0x84A314, reached from ``PlayerState.GetPlayerColor``) resolves it as:

    skinData[skin].color   if that skin defines a positive colour
    else tribeData[tribe].color
    else 0xFFFFFF

The colour values are packed 0x00RRGGBB ints, extracted from the ``GameLogicData``
TextAsset in ``data.unity3d`` into ``tribe_colors.json`` by
``tools/extract_tribe_colors.py``. In the shipped data only the Swamp skin overrides
its tribe's colour; every other skin inherits the tribe colour, exactly as the game does.
"""
from __future__ import annotations
import json
import os
from typing import Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "tribe_colors.json")) as _f:
    _DATA = json.load(_f)

# Keyed by enum value (TribeType / SkinType) -> packed 0x00RRGGBB int.
TRIBE_COLOR = {int(k): v for k, v in _DATA.get("tribe", {}).items()}
SKIN_COLOR = {int(k): v for k, v in _DATA.get("skin", {}).items()}
# Each tribe's special (premium) skin: TribeType -> SkinType. The "normal" skin is
# SkinType.Default (0); the special skin recolours (via SKIN_COLOR) and re-skins the
# art (sprites resolve to the ``_<skin>`` variants, falling back to tribe/base).
TRIBE_SPECIAL_SKIN = {int(k): v for k, v in _DATA.get("tribe_skin", {}).items()}

WHITE = 0xFFFFFF


def special_skin(tribe: int) -> int:
    """The tribe's special skin id (SkinType), or 0 (Default) if it has none."""
    return TRIBE_SPECIAL_SKIN.get(tribe, 0)


def get_tribe_color(tribe: int, skin: int = 0) -> int:
    """Packed 0x00RRGGBB base colour for a tribe/skin, per GameLogicData.GetTribeColor."""
    sc = SKIN_COLOR.get(skin)
    if sc is not None and sc > 0:        # engine: skin colour wins only when > 0
        return sc
    tc = TRIBE_COLOR.get(tribe)
    if tc is not None:
        return tc
    return WHITE


def get_tribe_rgb(tribe: int, skin: int = 0) -> Tuple[int, int, int]:
    """get_tribe_color as an (r, g, b) tuple."""
    c = get_tribe_color(tribe, skin) & 0xFFFFFF
    return ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)