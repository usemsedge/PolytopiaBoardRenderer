"""Tile/UI text-label overlays — unit health badge + type-icon badge.

Health badge  — mirrors UnitStatusDisplay.SetState (RVA 0x2B81F28):
  - healthLabel (TextMeshPro at field 0x38): Roboto Light, white ≥5 HP / red <5 HP.
  - healthBg (SpriteRenderer at field 0x30): UnitHealthGFX_shield_1/_2 (defence tier)
    or bare text when no defence bonus.

Type-icon badge — mirrors UnitStatusDisplay (typeIcon / typeBg / typeOutline):
  - typeBg: circle_30 tinted with the player team colour.
  - typeIcon: <unitname>_icon sprite (e.g. "warrior_icon"), centred on the circle.
  - Position: upper-right of the unit (symmetric to health badge on the left).

Font: Roboto Light — game binary asset "Roboto-Light_Numbers".

Interface (CONTRACT.md):
    def items(ctx, x, y) -> list[Placement]
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

import enums as E
import projection as P
from context import Placement
from image import Image

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont as PILFont
    _PIL = True
except ImportError:
    _PIL = False

# ── font ──────────────────────────────────────────────────────────────────────
_HERE      = os.path.dirname(os.path.abspath(__file__))
_FONT_PATH = os.path.join(_HERE, "JosefinSans-Italic.ttf")
_FONT_SIZE = 24

# Drop-shadow offset in pixels: (right, down).
_SHADOW_OFFSET = (1, 2)

_font_cache: dict = {}


def _get_font():
    if "font" not in _font_cache:
        _font_cache["font"] = (
            PILFont.truetype(_FONT_PATH, _FONT_SIZE)
            if _PIL and os.path.exists(_FONT_PATH) else None
        )
    return _font_cache["font"]


def _render_text(text: str, color: tuple = (255, 255, 255, 255)) -> Image:
    """JosefinSans-Italic with a black drop shadow."""
    font = _get_font()
    if font is None:
        raise RuntimeError(f"Font not found at {_FONT_PATH}")
    sx, sy = _SHADOW_OFFSET
    tmp  = ImageDraw.Draw(PILImage.new("RGBA", (1, 1)))
    bbox = tmp.textbbox((0, 0), text, font=font)
    pad_l, pad_t = 1, 1
    pad_r = sx + 1
    pad_b = sy + 1
    ox0 = pad_l - bbox[0]
    oy0 = pad_t - bbox[1]
    w = bbox[2] - bbox[0] + pad_l + pad_r
    h = bbox[3] - bbox[1] + pad_t + pad_b
    canvas = PILImage.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(canvas)
    draw.text((ox0 + sx, oy0 + sy), text, font=font, fill=(0, 0, 0, 200))
    draw.text((ox0,      oy0),      text, font=font, fill=color)
    return Image(canvas.width, canvas.height, bytearray(canvas.tobytes()))


# ── defence-bonus tier (health badge background) ──────────────────────────────
_BG_SPRITE = {
    "shield": "UnitHealthGFX_shield_1",
    "fort":   "UnitHealthGFX_shield_2",
}
_SHIELD_TERRAIN = {
    int(E.Terrain.FOREST), int(E.Terrain.MOUNTAIN),
    int(E.Terrain.WETLAND), int(E.Terrain.MANGROVE),
}


def _defence_tier(tile) -> str:
    imp = tile.improvement
    if imp is not None and imp.type == int(E.Improvement.CITY):
        return "fort" if imp.has_wall else "shield"
    if tile.terrain in _SHIELD_TERRAIN:
        return "shield"
    return "none"


# ── unit-type icon mapping ────────────────────────────────────────────────────
# UnitData.Type → "<name>_icon" sprite (GetUnitIconAddress, stringliteral.json).
UNIT_ICON_NAME = {
    E.Unit.WARRIOR:         "warrior_icon",
    E.Unit.SCOUT:           "explorer_icon",
    E.Unit.RIDER:           "rider_icon",
    E.Unit.KNIGHT:          "knight_icon",
    E.Unit.DEFENDER:        "defender_icon",
    E.Unit.SWORDSMAN:       "swordsman_icon",
    E.Unit.ARCHER:          "archer_icon",
    E.Unit.CATAPULT:        "catapult_icon",
    E.Unit.MINDBENDER:      "mindbender_icon",
    E.Unit.GIANT:           "giant_icon",
    E.Unit.SHAMAN:          "shaman_icon",
    E.Unit.DAGGER:          "dagger_icon",
    E.Unit.CLOAK:           "cloak_icon",
    E.Unit.SHIP:            "unit_ship",
    E.Unit.BOAT:            "unit_boat",
    E.Unit.BATTLESHIP:      "unit_battleship",
    E.Unit.SCOUTSHIP:       "unit_scoutship",
    E.Unit.BOMBERSHIP:      "unit_bombership",
    E.Unit.RAMMERSHIP:      "unit_rammer",
    E.Unit.TRANSPORTSHIP:   "unit_transportship",
    E.Unit.JUGGERNAUT:      "unit_juggernaut",
    E.Unit.PIRATE:          "unit_pirate_ship",
    E.Unit.BUNNY:           "rebel_icon",
    E.Unit.POLYTAUR:        "polytaur_icon",
    E.Unit.NAVALON:         "navalon_icon",
    E.Unit.DRAGON_EGG:      "dragonegg_icon",
    E.Unit.BABY_DRAGON:     "babydragon_icon",
    E.Unit.FIRE_DRAGON:     "firedragon_icon",
    E.Unit.AMPHIBIAN:       "amphibian_icon",
    E.Unit.TRIDENTION:      "tridention_icon",
    E.Unit.MOONI:           "mooni_icon",
    E.Unit.BATTLE_SLED:     "battlesled_icon",
    E.Unit.ICE_FORTRESS:    "icefortress_icon",
    E.Unit.ICE_ARCHER:      "icearcher_icon",
    E.Unit.CRAB:            "crab_icon",
    E.Unit.GAAMI:           "gaami_icon",
    E.Unit.HEXAPOD:         "hexapod_icon",
    E.Unit.DOOMUX:          "doomux_icon",
    E.Unit.PHYCHI:          "phychi_icon",
    E.Unit.KITON:           "kiton_icon",
    E.Unit.EXIDA:           "exida_icon",
    E.Unit.CENTIPEDE:       "centipede_icon",
    E.Unit.SEGMENT:         "segment_icon",
    E.Unit.RAYCHI:          "raychi_icon",
    E.Unit.JELLY:           "jelly_icon",
    E.Unit.SHARK:           "shark_icon",
    E.Unit.SIREN:           "siren_icon",
    E.Unit.AQUAPULT:        "aquapult_icon",
    E.Unit.BOOMCHI:         "boomchi_icon",
    E.Unit.MANTIS:          "mantis_icon",
    E.Unit.BUG_EGG:         "bugegg_icon",
    E.Unit.LARVA:           "larva_icon",
    E.Unit.MERMAID_WARRIOR:  "mermaidwarrior_icon",
    E.Unit.MERMAID_ARCHER:   "mermaidarcher_icon",
    E.Unit.MERMAID_SWORDSMAN:"mermaidswordsman_icon",
    E.Unit.MERMAID_DEFENDER: "mermaiddefender_icon",
    E.Unit.MERMAID_CLOAK:    "mermaidcloak_icon",
    E.Unit.MERMAID_DAGGER:   "mermaiddagger_icon",
    E.Unit.CLOAK_BOAT:       "unit_cloak_boat",
    E.Unit.ISLAND:           "island_icon",
}

# Background circle sprite for the type badge.
# Engine: UnitStatusDisplay has three layers — typeOutline (white ring, back),
#         typeBg (team-colour fill), typeIcon (unit icon, front).
_ICON_BG            = "circle_30"
ICON_BG_SCALE       = 0.55    # typeBg  — circle fill scale relative to render_scale
ICON_BG_ALPHA       = 0.5     # typeBg  — fill opacity
ICON_OUTLINE_SCALE  = 0.60    # typeOutline — white ring; ~2 px wide at fill scale
#                               (exact ratio baked in prefab; TBD pixel verification)
ICON_SCALE          = 0.60    # typeIcon — icon fills this fraction of the circle


def _build_icon_badge(ctx, unit_type: int,
                      team: Optional[Tuple[int, int, int]]) -> Optional[Image]:
    """Composite typeOutline (white ring) + typeBg (team fill) + typeIcon.

    The white outline ring (typeOutline SpriteRenderer at field 0x60 in
    UnitStatusDisplay) is always rendered when the badge is visible.
    Visibility is governed by items(): enemy invisible units are never
    shown; invisible own units are handled by create_unit's alpha pass.
    """
    # --- typeOutline: white ring drawn behind the fill ---
    outline = ctx.bake(_ICON_BG, scale=ICON_OUTLINE_SCALE)  # white (circle_30 is white)
    if outline is None:
        return None
    outline = outline.copy()

    # --- typeBg: team-coloured fill ---
    fill = ctx.bake(_ICON_BG, tint=team, scale=ICON_BG_SCALE)
    if fill is None:
        return outline  # fallback: outline only
    fill = fill.copy()
    if ICON_BG_ALPHA < 1.0:
        factor = int(ICON_BG_ALPHA * 255)
        px = fill.px
        for i in range(3, len(px), 4):
            px[i] = (px[i] * factor) >> 8

    # Punch a transparent hole in the white disk at the fill radius so the
    # white is a true ring (not a disk) — prevents the white bleeding through
    # the semi-transparent fill in the center.
    cx = outline.w / 2.0
    cy = outline.h / 2.0
    r2 = (fill.w / 2.0) ** 2  # fill circle radius squared
    opx = outline.px
    ow = outline.w
    for y in range(outline.h):
        dy2 = (y - cy) ** 2
        for x in range(ow):
            if (x - cx) ** 2 + dy2 <= r2:
                opx[(y * ow + x) * 4 + 3] = 0  # clear alpha inside fill area

    # Composite fill centred on outline canvas.
    ox = (outline.w - fill.w) // 2
    oy = (outline.h - fill.h) // 2
    outline.paste(fill, ox, oy)

    # --- typeIcon: unit icon centred on fill ---
    icon_name = UNIT_ICON_NAME.get(E.Unit(unit_type))
    if icon_name and ctx.exists(icon_name):
        target_w = max(1, round(fill.w * ICON_SCALE))
        target_h = max(1, round(fill.h * ICON_SCALE))
        icon = ctx.bake(icon_name)
        if icon is not None:
            ratio = min(target_w / icon.w, target_h / icon.h)
            iw = max(1, round(icon.w * ratio))
            ih = max(1, round(icon.h * ratio))
            if (iw, ih) != (icon.w, icon.h):
                icon = icon.resized(iw, ih)
            # Centre icon on the full composite (not just the fill).
            ix = (outline.w - iw) // 2
            iy = (outline.h - ih) // 2
            outline.paste(icon, ix, iy)

    return outline


# ── placement knobs ───────────────────────────────────────────────────────────
BADGE_SCALE = 0.55   # shield sprite scale

_BADGE_CX = -50      # health badge centre: left of diamond centre
_BADGE_CY = -55      # health badge centre: above diamond centre

_ICON_CX  = +45      # type icon centre: right of diamond centre
_ICON_CY  = -55      # type icon centre: same height as health badge

SORT_LABELS = 110


# ── emission ──────────────────────────────────────────────────────────────────
def items(ctx, x: int, y: int) -> List[Placement]:
    tile = ctx.tile_at(x, y)
    if tile is None:
        return []
    unit = tile.unit
    if unit is None or unit.type == int(E.Unit.NONE) or ctx.is_hidden(tile):
        return []

    result = []

    # ── health badge ──────────────────────────────────────────────────────────
    health = max(0, int(unit.health))
    tier   = _defence_tier(tile)
    color    = (255, 60, 60, 255) if health <= 4 else (255, 255, 255, 255)
    text_img = _render_text(str(health), color)

    if tier == "none":
        badge = text_img
    else:
        badge = ctx.bake(_BG_SPRITE[tier], scale=BADGE_SCALE)
        if badge is not None:
            badge = badge.copy()
            badge.paste(text_img, (badge.w - text_img.w) // 2,
                                  (badge.h - text_img.h) // 2)
        else:
            badge = text_img

    result.append(Placement(
        SORT_LABELS, badge,
        round(_BADGE_CX - badge.w / 2),
        round(_BADGE_CY - badge.h / 2),
    ))

    # ── type-icon badge ───────────────────────────────────────────────────────
    # Show the carried unit's icon when a transport has a passenger.
    icon_type = unit.passenger_type if unit.passenger_type is not None else unit.type
    team = ctx.player_color(unit.owner)
    icon_badge = _build_icon_badge(ctx, icon_type, team)
    if icon_badge is not None:
        result.append(Placement(
            SORT_LABELS, icon_badge,
            round(_ICON_CX - icon_badge.w / 2),
            round(_ICON_CY - icon_badge.h / 2),
        ))

    return result


