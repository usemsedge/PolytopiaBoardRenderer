"""DoSpriteLookup — reproduce SpriteAtlasManager.DoSpriteLookup name resolution.

Per recon/terrain.md, resources.md, cities_improvements.md, units.md:
given a base name + tribe + skin (+ optional level), build an ordered candidate
list and return the first that exists in the atlas, falling back to the bare base.
Candidate order (skin wins over tribe; level-suffixed variants preferred when given):
  base_<skin>_<level>, base_<tribe>_<level>, base_<level>,
  base_<skin>, base_<tribe>, base
"""
from __future__ import annotations
from typing import Optional

from enums import Tribe, Skin, TRIBE_THEME, SKIN_THEME


def theme_suffix(tribe: int, skin: int) -> Optional[str]:
    """Lowercase theme token: skin name if a real skin is set, else tribe name."""
    if skin is not None and skin > Skin.DEFAULT:
        s = SKIN_THEME.get(skin)
        if s:
            return s
    if tribe:
        return TRIBE_THEME.get(tribe)
    return None


def _skin_token(skin: int) -> Optional[str]:
    if skin is not None and skin > 0:
        return SKIN_THEME.get(skin)
    return None


def _tribe_token(tribe: int) -> Optional[str]:
    if tribe:
        return TRIBE_THEME.get(tribe)
    return None


def resolve(store, base: str, tribe: int = 0, skin: int = 0,
            level: int = -1, check_outline: bool = False):
    """Return (sprite_name | None, outline_name | None).

    ``store`` is a SpriteStore (has .exists()). Mirrors DoSpriteLookup ordering.
    """
    skin_tok = _skin_token(skin)
    tribe_tok = _tribe_token(tribe)

    # Leveled families clamp down: try the requested level, then lower levels, then
    # unleveled. (ImprovementData.maxLevel isn't in the dump, so walk down to the
    # highest existing variant instead of rendering nothing for an over-max level.)
    levels = list(range(level, 0, -1)) if (level is not None and level >= 0) else []

    cands = []
    for lv in levels:                      # skin-themed leveled
        if skin_tok:
            cands.append(f"{base}_{skin_tok}_{lv}")
    if skin_tok:
        cands.append(f"{base}_{skin_tok}")
    for lv in levels:                      # tribe-themed leveled
        if tribe_tok:
            cands.append(f"{base}_{tribe_tok}_{lv}")
    if tribe_tok:
        cands.append(f"{base}_{tribe_tok}")
    for lv in levels:                      # bare leveled
        cands.append(f"{base}_{lv}")
    cands.append(base)

    chosen = None
    for c in cands:
        if store.exists(c):
            chosen = c
            break
    outline = None
    if check_outline and chosen is not None:
        o = chosen + "_Outline"
        if store.exists(o):
            outline = o
    return chosen, outline
