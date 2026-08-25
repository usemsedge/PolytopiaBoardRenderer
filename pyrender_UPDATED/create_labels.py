"""Tile/UI text-label overlays — city status + unit health/type badges.

City status — mirrors City.cityOverlay → CityStatusDisplay.SetCity (RVA 0x2A7ED80):
  - NameContainer: JosefinSans-Italic TMP size 18 @ NameLabel scale 0.08 + Shadow;
    capital underline + crown; work stars from ImprovementState.production
    (SetWork / ResourceWidget: Roboto-Light 16 + UI_resource @ 0.2);
    team-tinted Square bg (α≈0.5, width from UpdateSize).
  - ProgressBar: segmented pop bar (totalFields=level+1,
    filledFields=pop leftover after levels 1..L, dots=GetCityUnitCount).
    Engine stores cumulative population; L→L+1 costs L+1 (1→2 needs 2, …).

Unit health badge — mirrors UnitStatusDisplay.SetState:
  - UnitState.health is stored in tenths; label shows ceil(health/10).
  - healthLabel: JosefinSans-Italic numbers, white ≥5 HP / red <5 HP.
  - healthBg: UnitHealthGFX_shield_1/_2 only when GetDefenceBonus > 1.0×:
      terrain (GameLogicData defenceBonusUnlocks): forest←Archery,
      mountain←Climbing, water/ocean←Aquatism (unit owner's tech);
      city: tile.owner == unit.owner and unit has Fortify → shield,
      CityWall → fort shield.

Type-icon badge — typeOutline + typeBg (circle_30, team tint) + typeIcon.

Interface (CONTRACT.md):
    def items(ctx, x, y) -> list[Placement]
"""
from __future__ import annotations

import math
import os
from typing import List, Optional, Tuple

import enums as E
import projection as P
import spritemeta as SM
from context import Placement
from image import Image

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont as PILFont
    _PIL = True
except ImportError:
    _PIL = False

# ── fonts ─────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_FONT_PATH = os.path.join(_HERE, "JosefinSans-Italic.ttf")
_FONT_WORK_PATH = os.path.join(_HERE, "Roboto-Light.ttf")
_FONT_SIZE_HP = 24          # unit health badge

# CityStatusNameContainer / NameLabel (prefab GO 2042):
#   TMP m_fontSize = 18, NameLabel localScale = (0.08, 0.08, 0.1)
# Cap-height in board px via TMP world factor + Josefin faceInfo (Numbers atlas).
_CITY_TMP_FONT_SIZE = 18.0
_CITY_LABEL_SCALE = 0.08
_TMP_WORLD_FACTOR = 0.1
_TMP_POINT_SIZE = 157.0
_TMP_CAP_LINE = 115.0
_CITY_CAP_PX = (
    _CITY_TMP_FONT_SIZE * _TMP_WORLD_FACTOR / _TMP_POINT_SIZE
    * _TMP_CAP_LINE * _CITY_LABEL_SCALE * P.PPU
)  # ≈ 28 px

# ResourceWidget workLabel (prefab Text TMP under ResourceWidget):
#   Roboto-Light_Numbers Shadow, m_fontSize = 16, localScale = 0.08
_WORK_TMP_FONT_SIZE = 16.0
_WORK_CAP_PX = (
    _WORK_TMP_FONT_SIZE * _TMP_WORLD_FACTOR / _TMP_POINT_SIZE
    * _TMP_CAP_LINE * _CITY_LABEL_SCALE * P.PPU
)  # ≈ 25 px

# Drop-shadow offset in pixels: (right, down). TMP Shadow material on city names.
_SHADOW_OFFSET = (1, 2)

_font_cache: dict = {}


def _get_font(size: int, path: str = _FONT_PATH):
    key = f"{path}:{size}"
    if key not in _font_cache:
        _font_cache[key] = (
            PILFont.truetype(path, size)
            if _PIL and os.path.exists(path) else None
        )
    return _font_cache[key]


def _pil_size_for_cap_height(target_px: float, path: str = _FONT_PATH,
                            probe: str = "H") -> int:
    """FreeType size whose probe glyph height matches ``target_px``."""
    if not _PIL or not os.path.exists(path) or target_px <= 0:
        return 18
    tmp = ImageDraw.Draw(PILImage.new("RGBA", (1, 1)))
    best, best_err = 18, 1e9
    for sz in range(max(8, int(target_px * 0.5)), int(target_px * 2.5) + 1):
        font = PILFont.truetype(path, sz)
        bbox = tmp.textbbox((0, 0), probe, font=font)
        err = abs((bbox[3] - bbox[1]) - target_px)
        if err < best_err:
            best, best_err = sz, err
    return best


_FONT_SIZE_CITY = _pil_size_for_cap_height(_CITY_CAP_PX)
_FONT_SIZE_WORK = _pil_size_for_cap_height(_WORK_CAP_PX, _FONT_WORK_PATH, "8")


def _render_text(text: str, color: tuple = (255, 255, 255, 255),
                 size: int = _FONT_SIZE_HP, *, underline: bool = False,
                 font_path: str = _FONT_PATH) -> Image:
    """TMP-style text with a black drop shadow (optional underline)."""
    font = _get_font(size, font_path)
    if font is None:
        raise RuntimeError(f"Font not found at {font_path}")
    sx, sy = _SHADOW_OFFSET
    tmp = ImageDraw.Draw(PILImage.new("RGBA", (1, 1)))
    bbox = tmp.textbbox((0, 0), text, font=font)
    pad_l, pad_t = 1, 1
    pad_r = sx + 1
    pad_b = sy + 1 + (3 if underline else 0)
    ox0 = pad_l - bbox[0]
    oy0 = pad_t - bbox[1]
    w = bbox[2] - bbox[0] + pad_l + pad_r
    h = bbox[3] - bbox[1] + pad_t + pad_b
    canvas = PILImage.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.text((ox0 + sx, oy0 + sy), text, font=font, fill=(0, 0, 0, 200))
    draw.text((ox0, oy0), text, font=font, fill=color)
    if underline:
        # TMP fontStyle Underline (4) — SetCity when City.IsCapital.
        y = oy0 + (bbox[3] - bbox[1]) + 1
        x0, x1 = ox0, ox0 + (bbox[2] - bbox[0])
        draw.line([(x0 + sx, y + sy), (x1 + sx, y + sy)], fill=(0, 0, 0, 200), width=2)
        draw.line([(x0, y), (x1, y)], fill=color, width=2)
    return Image(canvas.width, canvas.height, bytearray(canvas.tobytes()))

# ── defence-bonus tier (health badge background) ──────────────────────────────
# Mirrors GameState.GetDefenceBonus(Unit) + TechData.defenceBonusUnlocks.
_BG_SPRITE = {
    "shield": "UnitHealthGFX_shield_1",  # 1.5× (terrain / city without walls)
    "fort":   "UnitHealthGFX_shield_2",  # 4.0× (own city + Fortify + CityWall)
}

# TechData.Type (dump.cs / GameLogicData28 techData.*.defenceBonusUnlocks).
_TECH_AQUATISM = 12
_TECH_ARCHERY = 18
_TECH_CLIMBING = 20

_TERRAIN_DEFENCE_TECH = {
    int(E.Terrain.FOREST): _TECH_ARCHERY,
    int(E.Terrain.MOUNTAIN): _TECH_CLIMBING,
    int(E.Terrain.WATER): _TECH_AQUATISM,
    int(E.Terrain.OCEAN): _TECH_AQUATISM,
}

# UnitData.unitAbilities contains "fortify" (GameLogicData28).
_FORTIFY_UNITS = {
    int(E.Unit.WARRIOR), int(E.Unit.RIDER), int(E.Unit.KNIGHT),
    int(E.Unit.DEFENDER), int(E.Unit.ARCHER), int(E.Unit.POLYTAUR),
    int(E.Unit.DRAGON_EGG), int(E.Unit.ICE_ARCHER),
    int(E.Unit.MERMAID_WARRIOR), int(E.Unit.MERMAID_ARCHER),
    int(E.Unit.MERMAID_DEFENDER),
}


def _defence_tier(ctx, tile, unit) -> str:
    """Return 'none' | 'shield' | 'fort' for the HP badge background."""
    imp = tile.improvement
    if imp is not None and imp.type == int(E.Improvement.CITY):
        # Own city + Fortify ability → 1.5×, or 4× with CityWall.
        if tile.owner == unit.owner and int(unit.type) in _FORTIFY_UNITS:
            if imp.has_reward(int(E.CityReward.CITY_WALL)):
                return "fort"
            return "shield"
        return "none"

    required = _TERRAIN_DEFENCE_TECH.get(int(tile.terrain))
    if required is None:
        return "none"
    player = ctx.gs.player_by_id(unit.owner)
    if player is None or required not in player.available_tech:
        return "none"
    return "shield"


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
        fill = fill.multiply_alpha(ICON_BG_ALPHA)
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


# ── city status overlay (CityStatusDisplay) ───────────────────────────────────
# Prefab local Y under the city transform (Unity Y-up). Tile-local +y is down, so
# dy_px = -world_y * PPU.
_NAME_WORLD_Y = -0.08          # NameContainer localPosition.y
_BAR_WORLD_Y = -0.25           # ProgressBar localPosition.y

# CityStatusProgressBar.ctor / serialized defaults (sharedassets1 MB 9478).
_BAR_MIN_WIDTH = 0.59          # runtime minWidth @0x70
_BAR_CENTER_FIELD = 0.27       # runtime centerFieldWidth @0x74
_BAR_MAX_WIDTH = 0.9           # serialized maxWidth
_BAR_SEG_HEIGHT = 0.16         # Segment.Render y-scale (sprite h/ppu = 32/200)

# Prefab colours (baseColor / fillColor / negativeColor).
_BAR_BASE = (0.896, 0.896, 0.896, 1.0)
_BAR_FILL = (0.0, 0.6, 1.0, 1.0)
_BAR_NEG = (1.0, 0.2, 0.0, 1.0)

_SEG_SPRITES = ("cityProgressBg_0", "cityProgressBg_1", "cityProgressBg_2")  # L/M/R
_DOT_SPRITE = "cityProgressDots"
_DOT_SCALE = 0.80             # CityStatusSegment/Dot localScale
_CROWN_SPRITE = "UI_crown"
_CROWN_SCALE = 0.115           # CapitalIcon/Crown localScale
_CROWN_BG = "circle_30"
_CROWN_BG_SCALE = 0.48         # CapitalIcon/Background localScale
# ResourceWidget / SetWork — star icon next to workLabel (Int32.ToString(work)).
_WORK_STAR = "UI_resource"
_WORK_STAR_SCALE = 0.20        # ResourceWidget/Star localScale
_WORK_STAR_SHADOW_DY = 0.02    # StarShadow localPosition.y (world, down in Unity Y-up)
_WORK_GAP_WORLD = 0.015        # UpdateSize pad when workContainer is active
_NAME_BG = "Square"
# Prefab Background localScale Y=4.8 on Square (4×4 @ ppu 100) → fixed plate height.
# Width is NOT the prefab X=30 default — CityStatusNameContainer.UpdateSize sizes to text
# via bg.localScale.x = contentWidth * 26.4 → world ≈ content * 1.056.
_NAME_BG_HEIGHT_WORLD = 4.0 / 100.0 * 4.8          # 0.192
# UpdateSize: base pad 0.03; when LeftIcon active add 2*iconWidth + 0.012.
_NAME_PAD_BASE_WORLD = 0.03
_NAME_PAD_ICON_WORLD = 0.012
_NAME_BG_ALPHA = 0.502                              # SpriteRenderer.color.a on Background


def _bake_ui(ctx, name: str, local_scale: float,
             tint: Optional[Tuple[int, int, int]] = None) -> Optional[Image]:
    """Bake a UI sprite at prefab localScale using Unity sprite rect (not trimmed PNG).

    ``ctx.bake`` multiplies by render_scale on the *extracted* PNG size; atlas-trimmed
    sheets (e.g. UI_crown 72×90 vs rect 126×126) undersize. World size =
    (meta_w / ppu) * localScale.
    """
    meta = getattr(SM, "_DATA", {}).get(name)
    if meta is None:
        return ctx.bake(name, tint=tint, scale=local_scale)
    tw = max(1, round(meta["w"] / meta["ppu"] * local_scale * P.PPU))
    th = max(1, round(meta["h"] / meta["ppu"] * local_scale * P.PPU))
    if not ctx.store.exists(name):
        return None
    try:
        img = ctx.store.get(name)
    except KeyError:
        return None
    img = img.resized(tw, th)
    if tint is not None:
        img = img.tinted(tint)
    return img


def _mul_rgba(img: Image, rgba: Tuple[float, float, float, float]) -> Image:
    """SpriteRenderer.color multiply (RGB + alpha)."""
    r, g, b, a = rgba
    out = img.tinted((max(0, min(255, int(r * 255))),
                      max(0, min(255, int(g * 255))),
                      max(0, min(255, int(b * 255)))))
    if a >= 0.999:
        return out
    return out.multiply_alpha(a)

def _city_unit_count(ctx, cx: int, cy: int) -> int:
    """MapDataExtensions.GetCityUnitCount — units whose home == city coords.

    When a unit's home is unset (-1,-1), count it toward the city that rules its tile.
    """
    n = 0
    for t in ctx.map.tiles:
        u = t.unit
        if u is None or u.type == int(E.Unit.NONE):
            continue
        hx, hy = u.home.x, u.home.y
        if hx >= 0 and hy >= 0:
            if hx == cx and hy == cy:
                n += 1
        elif (t.ruling_city_coordinates.x == cx
              and t.ruling_city_coordinates.y == cy):
            n += 1
    return n


def _build_work_widget(ctx, work: int) -> Optional[Image]:
    """CityStatusNameContainer.SetWork — UI_resource star + workLabel.

    Engine: workContainer.SetActive(work > 0); workLabel.text = work.ToString().
    Prefab: Roboto-Light_Numbers size 16 @ scale 0.08; Star localScale 0.20.
    Plate order: name → star → number.
    """
    if work <= 0:
        return None
    label = _render_text(str(int(work)), (255, 255, 255, 255),
                         size=_FONT_SIZE_WORK, font_path=_FONT_WORK_PATH)
    star = _bake_ui(ctx, _WORK_STAR, _WORK_STAR_SCALE)
    if star is None:
        return label
    # StarShadow: same sprite, black, offset down by 0.02 world.
    shadow = star.tinted((0, 0, 0))
    sh_dy = max(1, round(_WORK_STAR_SHADOW_DY * P.PPU))
    gap = max(1, round(0.01 * P.PPU))
    w = star.w + gap + label.w
    h = max(label.h, star.h + sh_dy)
    out = Image.new(w, h)
    sy = (h - star.h) // 2
    out.paste(shadow, 0, sy + sh_dy)
    out.paste(star, 0, sy)
    out.paste(label, star.w + gap, (h - label.h) // 2)
    return out


def _build_name_plate(ctx, name: str, is_capital: bool,
                      team: Optional[Tuple[int, int, int]],
                      work: int = 0) -> Optional[Image]:
    """CityStatusNameContainer — name + optional crown + work stars on Square bg.

    Engine (SetCity + SetWork + UpdateSize, prefab NameContainer GO 1396):
      - NameLabel TMP fontSize 18, localScale 0.08, JosefinSans-Italic + Shadow
      - capital → TMP fontStyle Underline (4) + CapitalIcon (crown @ 0.115)
      - work → ResourceWidget when work > 0 (CalculateWork / ImprovementState.production)
      - bg SpriteRenderer: GetPlayerColor, alpha kept ≈ 0.502
      - bg width sized to content (UpdateSize); height from scale.y = 4.8
    """
    if not name and work <= 0:
        return None
    text = None
    if name:
        text = _render_text(name, (255, 255, 255, 255), size=_FONT_SIZE_CITY,
                            underline=is_capital)

    crown = None
    if is_capital:
        # CapitalIcon: Background = circle_30 @ 0.48 with prefab cyan
        # (r≈0.012, g=0.6, b=1) — same as CityStatusProgressBar fillColor;
        # Crown = UI_crown @ 0.115. Bake crown from the trimmed PNG (ctx.bake),
        # not Unity rect meta — meta includes transparent padding, which would
        # stretch the art to fill the whole circle.
        fill_rgb = (max(0, min(255, int(_BAR_FILL[0] * 255))),
                    max(0, min(255, int(_BAR_FILL[1] * 255))),
                    max(0, min(255, int(_BAR_FILL[2] * 255))))
        ring = _bake_ui(ctx, _CROWN_BG, _CROWN_BG_SCALE, tint=fill_rgb)
        icon = ctx.bake(_CROWN_SPRITE, scale=_CROWN_SCALE)
        if ring is not None and icon is not None:
            crown = ring.copy()
            crown.paste(icon,
                        (crown.w - icon.w) // 2,
                        (crown.h - icon.h) // 2)
        elif icon is not None:
            crown = icon

    work_img = _build_work_widget(ctx, work)

    gap = max(2, round(0.02 * P.PPU))
    work_gap = max(2, round(_WORK_GAP_WORLD * P.PPU))
    pad_x = max(4, round(_NAME_PAD_BASE_WORLD * P.PPU))
    if crown is not None:
        # LeftIcon path: 2 * leftIconBgWidth + 0.012 (UpdateSize).
        pad_x += max(2, round(_NAME_PAD_ICON_WORLD * P.PPU))

    content_w = 0
    content_h = 0
    if crown is not None:
        content_w += crown.w + gap
        content_h = max(content_h, crown.h)
    if text is not None:
        content_w += text.w
        content_h = max(content_h, text.h)
    if work_img is not None:
        content_w += work_gap + work_img.w
        content_h = max(content_h, work_img.h)

    if content_w <= 0:
        return None

    bg_h = max(round(_NAME_BG_HEIGHT_WORLD * P.PPU), content_h + 4)
    bg_w = content_w + 2 * pad_x

    bg = ctx.bake(_NAME_BG, tint=team)
    if bg is not None:
        bg = bg.resized(bg_w, bg_h)
    else:
        rgb = team or (80, 80, 80)
        bg = Image.new(bg_w, bg_h, (*rgb, 255))
    # ColorUtil.SetAlphaOnColor keeps prefab SpriteRenderer alpha (~0.5).
    bg = bg.multiply_alpha(_NAME_BG_ALPHA)

    plate = bg
    x = pad_x
    y = (plate.h - content_h) // 2
    if crown is not None:
        plate.paste(crown, x, y + (content_h - crown.h) // 2)
        x += crown.w + gap
    if text is not None:
        plate.paste(text, x, y + (content_h - text.h) // 2)
        x += text.w
    if work_img is not None:
        x += work_gap
        plate.paste(work_img, x, y + (content_h - work_img.h) // 2)
    return plate


def _opaque_center(img: Image, alpha_min: int = 30) -> Tuple[float, float]:
    """Centre of non-transparent pixels (fallback: geometric centre)."""
    px, w, h = img.px, img.w, img.h
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        row = y * w * 4
        for x in range(w):
            if px[row + x * 4 + 3] > alpha_min:
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
    if maxx < 0:
        return w / 2.0, h / 2.0
    return (minx + maxx) / 2.0, (miny + maxy) / 2.0


def _city_pop_fill(level: int, population: int) -> int:
    """Bar fill from cumulative population for a city at ``level``.

    Level L→L+1 costs L+1 pop (1→2 needs 2, 2→3 needs 3, …). Cumulative pop
    spent to reach level L is 2+3+…+L = L(L+1)/2 − 1 (0 for L≤1). Only the
    remainder toward the next level is rendered (negative → red deficit fill).

    Example: level 3 with total pop 6 → spent 2+3=5 → fill 1 of 4 bars.
    """
    level = max(0, int(level))
    baseline = max(0, level * (level + 1) // 2 - 1)
    return int(population) - baseline


def _build_progress_bar(ctx, total_fields: int, filled_fields: int,
                        dots: int) -> Optional[Image]:
    """CityStatusProgressBar.UpdateFields — Left/Middle/Right segments + dots."""
    n = max(0, int(total_fields))
    if n < 1:
        return None

    width = _BAR_MIN_WIDTH + _BAR_CENTER_FIELD * max(0, n - 2)
    width = min(width, _BAR_MAX_WIDTH)
    field_w = width / n
    field_w_px = max(1, round(field_w * P.PPU))
    seg_h_px = max(1, round(_BAR_SEG_HEIGHT * P.PPU))
    total_w_px = field_w_px * n

    # Negative filledFields (engine) uses negativeColor for the "active" palette.
    active = _BAR_NEG if filled_fields < 0 else _BAR_FILL
    filled_abs = abs(int(filled_fields))

    canvas = Image.new(total_w_px, seg_h_px)
    for i in range(n):
        if i == 0:
            spr = _SEG_SPRITES[0]
        elif i == n - 1:
            spr = _SEG_SPRITES[2]
        else:
            spr = _SEG_SPRITES[1]
        color = active if i < filled_abs else _BAR_BASE
        seg = ctx.bake(spr)
        if seg is None:
            continue
        seg = _mul_rgba(seg.resized(field_w_px, seg_h_px), color)
        canvas.paste(seg, i * field_w_px, 0)

        if i < dots:
            # Prefab Dot localScale 0.75 — fixed size, independent of field count.
            dot = _bake_ui(ctx, _DOT_SPRITE, _DOT_SCALE)
            if dot is not None:
                # Dot colour: white on filled slots, black on empty (UpdateFields fcsel).
                dcol = (1.0, 1.0, 1.0, 1.0) if i < filled_abs else (0.0, 0.0, 0.0, 1.0)
                dot = _mul_rgba(dot, dcol)
                # Segment sprites have transparent padding — align opaque centres,
                # not the full canvas / sprite rect.
                seg_cx, seg_cy = _opaque_center(seg)
                dot_cx, dot_cy = _opaque_center(dot)
                canvas.paste(dot,
                             i * field_w_px + round(seg_cx - dot_cx),
                             round(seg_cy - dot_cy))
    return canvas


def render_city_status(ctx, x: int, y: int) -> List[Placement]:
    """Render CityStatusDisplay overlays for a city tile (name plate + pop bar).

    Faithful to CityStatusDisplay.SetCity:
      totalFields  = level + 1
      filledFields = population leftover after paying 2+3+…+level
                     (ImprovementState.population is cumulative total)
      dots         = GetCityUnitCount(map, cityCoords)
      work         = ImprovementState.production  (engine: CalculateWork → SetWork)
      own cities   = full plate (crown/underline/stars) + pop bar
      enemy cities = name only (no crown, underline, stars, or pop bar)
    """
    tile = ctx.tile_at(x, y)
    if tile is None or ctx.is_hidden(tile):
        return []
    imp = tile.improvement
    if imp is None or imp.type != int(E.Improvement.CITY):
        return []

    # Neutral villages: hut sprite only — no name plate or population bar.
    if not tile.owner and not tile.capital_of:
        return []

    level = max(0, int(imp.level))
    filled_fields = _city_pop_fill(level, imp.population)
    total_fields = level + 1
    dots = _city_unit_count(ctx, x, y)

    # Own / omniscient: full status. Enemy: name plate only (no crown, stars, bar).
    own = ctx.viewer_id == 0xFF or tile.owner == ctx.viewer_id
    work = int(imp.production) if own else 0
    is_capital = bool(tile.capital_of) if own else False
    team = ctx.player_color(tile.owner)
    name = (imp.name or "").strip()

    out: List[Placement] = []

    plate = _build_name_plate(ctx, name, is_capital, team, work=work)
    if plate is not None:
        cy = -_NAME_WORLD_Y * P.PPU  # world y=-0.08 → below centre
        out.append(Placement(
            E.SORT_CITY_STATUS, plate,
            round(-plate.w / 2),
            round(cy - plate.h / 2),
        ))

    if own:
        bar = _build_progress_bar(ctx, total_fields, filled_fields, dots)
        if bar is not None:
            cy = -_BAR_WORLD_Y * P.PPU
            out.append(Placement(
                E.SORT_CITY_STATUS, bar,
                round(-bar.w / 2),
                round(cy - bar.h / 2),
            ))

    return out


# ── emission ──────────────────────────────────────────────────────────────────
def items(ctx, x: int, y: int) -> List[Placement]:
    tile = ctx.tile_at(x, y)
    if tile is None:
        return []

    result: List[Placement] = []
    result.extend(render_city_status(ctx, x, y))

    unit = tile.unit
    if unit is None or unit.type == int(E.Unit.NONE) or ctx.is_hidden(tile):
        return result

    # ── health badge ──────────────────────────────────────────────────────────
    # Wire/format health is tenths; client does ceil(health * 0.1) for the label.
    health = max(0, int(math.ceil(int(unit.health) / 10.0)))
    tier = _defence_tier(ctx, tile, unit)
    color = (255, 60, 60, 255) if health <= 4 else (255, 255, 255, 255)
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
        E.SORT_UNIT_STATUS, badge,
        round(_BADGE_CX - badge.w / 2),
        round(_BADGE_CY - badge.h / 2),
    ))

    # ── type-icon badge ───────────────────────────────────────────────────────
    passenger = unit.passenger_unit
    icon_type = passenger.type if passenger is not None else unit.type
    team = ctx.player_color(unit.owner)
    icon_badge = _build_icon_badge(ctx, icon_type, team)
    if icon_badge is not None:
        result.append(Placement(
            E.SORT_UNIT_STATUS, icon_badge,
            round(_ICON_CX - icon_badge.w / 2),
            round(_ICON_CY - icon_badge.h / 2),
        ))

    return result


