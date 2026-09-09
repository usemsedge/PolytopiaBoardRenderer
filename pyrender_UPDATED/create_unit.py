"""Unit component — composites a unit's paper-doll exactly as the engine's prefab does.

Ported from ``pyrender/layer_units.py`` to the tile-local create_* contract. A unit is a
``SpriteContainer`` placed at the tile world point; each visual part is a child sprite at a
fixed local (x, y) and local scale baked in the prefab (recovered into ``unit_parts.json``).
Each part is anchored by its own pivot, world units convert to pixels via the projection PPU,
and each PNG is drawn at its measured render scale (REF_PPU / sprite_ppu) times the prefab's
local scale. Parts are pre-sorted by m_SortingOrder (back-to-front). Tinted parts (``*_tint``)
get the player team colour multiplied in. Part sprite names are re-themed per tribe/skin via
DoSpriteLookup. ``flipped`` mirrors the whole composited unit.

We build the whole unit into ONE composite Image (so flip mirrors it as a unit) and emit a
single Placement at E.SORT_UNIT. In tile-local space the SpriteContainer origin (world 0,0)
sits at the diamond centre, so the placement top-left is ``(-origin_x, -origin_y)`` plus the
seat-convention nudge ``UNIT_OFFSET_PX``.

Centipede segments: prefab Connection parts are dropped; ``connector_items`` draws a
dynamic ``cymanti_centipede_connector`` stretched toward ``unit.leader`` (SegmentConnector).

Visual modifiers (engine: Unit.UpdateObject):
  Tint — Unit.GetOverlayColorAndStrength → SkinVisualsRenderer.ColorizeUnit (lerp).
  Particles — Unit.UpdateUnitEffectParticles (animated in-game; we paste one static
    frame of the Unit*/bubble sprite, centered on the unit).
  Invisible enemy → skip (IsInvisibleForLocalPlayer); owner → SetAlpha.
  Outline (has action left) → cyan _Outline sprites at SORT_UNIT-1 for the
    perspective player's units that can still move, or that moved but still
    have a dash target next to them.
  Exhausted local units → no outline + ColorizeUnit wash at strength 0.4.
  Type-icon white ring is handled in create_labels (untouched only).
"""
from __future__ import annotations

import json
import math
import os
from typing import List, Optional, Tuple

import context
import enums as E
import projection as P
import spritemeta as SM
from context import Placement
from image import Image
from PIL import Image as PILImage

_HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(_HERE, "unit_parts.json")) as _f:
    UNIT_PARTS = json.load(_f)
# Per-sprite pivot registered against the TRIMMED PNG (the extracted sprites are alpha-trimmed,
# but m_Pivot is relative to the original rect; sprite_reg.json corrects for the trim offset).
with open(os.path.join(_HERE, "sprite_reg.json")) as _f:
    SPRITE_REG = json.load(_f)


def _pivot(name):
    """Trimmed-PNG pivot (bottom-left origin, normalized), falling back to centre."""
    r = SPRITE_REG.get(name)
    if r:
        return tuple(r["pivot"])
    return SM.pivot(name) or (0.5, 0.5)


# Manual pixel nudge of the whole unit on the tile: (dx, dy), +x = right, +y = down.
# NOT a source offset: RenderUnit (@0x2CDD620) sets the unit's world position to bare
# ToPosition(coords) with z=0 — relative tile offset (0,0,0), no TILE_VERTICAL_OFFSET.
# This knob only compensates pyrender's seat convention (the SpriteContainer origin lands
# at the diamond CENTRE; +y seats the unit slightly forward/down on the top face).
UNIT_OFFSET_PX = (0, 25)

# Uniform scale applied to the entire unit composite after rendering.
# 1.0 = native size; 0.9 = shrink 10%; does NOT affect the outline (resampled separately).
UNIT_SCALE = 1

# Outline colour recovered from data.unity3d (4-float RGBA at 0x111A8F8):
# R=0.000, G=0.961, B=0.961, A=0.959  →  #00F5F5, nearly opaque cyan.
OUTLINE_COLOR = (0, 245, 245)


# Extra vertical seat for head parts, as a fraction of the head's drawn height, applied on
# top of the prefab transform. + = lower (sink into the shoulders), - = raise. 0 = prefab-exact.
# This is the global baseline; per-tribe/skin fine corrections are added on top (below).
HEAD_OFFSET_FRAC = 0

# Per-(tribe, skin) head-position correction. Each value is (x_frac, y_frac): the head is
# nudged by x_frac * head_width horizontally and y_frac * head_height vertically (so the
# move scales with the head's drawn size). +x = right, +y = lower (deeper into the body);
# -x = left, -y = higher. y is added on top of HEAD_OFFSET_FRAC. Default for any pair not
# listed is (0.0, 0.0) = prefab-exact. There is a row per tribe for the normal skin
# (Skin.DEFAULT) and for that tribe's special skin, since the skinned head art can sit
# differently on the body. Tune these to seat each tribe/skin's head cleanly.
HEAD_CORRECTION_RAW = {
    (E.Tribe.AIMO,     E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.AIMO,     E.Skin.AIBO):    (0.0, 0.0),
    (E.Tribe.AQUARION, E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.AQUARION, E.Skin.SWAMP):   (0.0, 0.0),
    (E.Tribe.BARDUR,   E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.BARDUR,   E.Skin.BAERION): (0.0, 0.0),
    (E.Tribe.ELYRION,  E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.ELYRION,  E.Skin.DARKELF): (0.0, 0.0),
    (E.Tribe.HOODRICK, E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.HOODRICK, E.Skin.RANGER):  (0.0, 0.0),
    (E.Tribe.IMPERIUS, E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.IMPERIUS, E.Skin.SCHOLAR): (0.0, 0.0),
    (E.Tribe.KICKOO,   E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.KICKOO,   E.Skin.PIRATE):  (0.0, 0.0),
    (E.Tribe.LUXIDOOR, E.Skin.DEFAULT):   (0.0, 0.0),
    (E.Tribe.LUXIDOOR, E.Skin.MERCENARY): (0.0, 0.0),
    (E.Tribe.OUMAJI,   E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.OUMAJI,   E.Skin.SFINX):   (0.0, 0.0),
    (E.Tribe.QUETZALI, E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.QUETZALI, E.Skin.IKARUS):  (0.0, 0.0),
    (E.Tribe.VENGIR,   E.Skin.DEFAULT):  (0.0, 0.0),
    (E.Tribe.VENGIR,   E.Skin.SKELETON): (0.0, 0.0),
    (E.Tribe.XINXI,    E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.XINXI,    E.Skin.NINJA):   (0.0, 0.0),
    (E.Tribe.YADAKK,   E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.YADAKK,   E.Skin.URKAZ):   (0.0, 0.0),
    (E.Tribe.ZEBASI,   E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.ZEBASI,   E.Skin.ARTY):    (0.0, 0.0),
    (E.Tribe.POLARIS,  E.Skin.DEFAULT): (0.0, 0.0),
    (E.Tribe.POLARIS,  E.Skin.MAGMA):   (0.0, 0.0),
    (E.Tribe.CYMANTI,  E.Skin.DEFAULT): (0.0, 0.0),
}
# Normalize keys to plain (int, int) so lookups by raw tribe/skin ints hit reliably.
HEAD_CORRECTION = {(int(t), int(s)): v for (t, s), v in HEAD_CORRECTION_RAW.items()}


def _head_correction(tribe, skin):
    """(x_frac, y_frac) head nudge for a tribe/skin, defaulting to (0.0, 0.0)."""
    return HEAD_CORRECTION.get((int(tribe), int(skin)), (0.0, 0.0))


# Unit enum value -> prefab name in unit_parts.json (prefab GameObject names, some are
# internal code names: Priest=Mindbender, Swordman=Swordsman, Wendy=Gaami, Seamonster=Navalon).
ENUM_TO_PREFAB = {
    E.Unit.SCOUT: "Scout", E.Unit.WARRIOR: "Warrior", E.Unit.RIDER: "Rider",
    E.Unit.KNIGHT: "Knight", E.Unit.DEFENDER: "Defender", E.Unit.SHIP: "Ship",
    E.Unit.BATTLESHIP: "Battleship", E.Unit.CATAPULT: "Catapult", E.Unit.ARCHER: "Archer",
    E.Unit.MINDBENDER: "Priest", E.Unit.SWORDSMAN: "Swordman", E.Unit.GIANT: "Giant",
    E.Unit.BUNNY: "Bunny", E.Unit.BOAT: "Boat", E.Unit.POLYTAUR: "Polytaur",
    E.Unit.NAVALON: "Seamonster", E.Unit.DRAGON_EGG: "Egg", E.Unit.BABY_DRAGON: "BabyDragon",
    E.Unit.FIRE_DRAGON: "FireDragon", E.Unit.AMPHIBIAN: "Amphibian",
    E.Unit.TRIDENTION: "Tridention", E.Unit.MOONI: "Mooni", E.Unit.BATTLE_SLED: "Battlesled",
    E.Unit.ICE_FORTRESS: "Fortress", E.Unit.ICE_ARCHER: "IceArcher", E.Unit.CRAB: "Crab",
    E.Unit.GAAMI: "Wendy", E.Unit.HEXAPOD: "Hexapod", E.Unit.DOOMUX: "Doomux",
    E.Unit.PHYCHI: "Phychi", E.Unit.KITON: "Kiton", E.Unit.EXIDA: "Exida",
    E.Unit.CENTIPEDE: "Centipede", E.Unit.SEGMENT: "Centipede_segment", E.Unit.RAYCHI: "Raychi",
    E.Unit.SHAMAN: "Shaman", E.Unit.DAGGER: "dagger", E.Unit.CLOAK: "Cloak",
    E.Unit.CLOAK_BOAT: "Cloak Boat", E.Unit.PIRATE: "Pirate", E.Unit.BOMBERSHIP: "Bombership",
    E.Unit.SCOUTSHIP: "ScoutShip", E.Unit.TRANSPORTSHIP: "Transportship",
    E.Unit.RAMMERSHIP: "Rammership", E.Unit.JUGGERNAUT: "Juggernaut",
    E.Unit.MERMAID_WARRIOR: "Mermaid Warrior", E.Unit.MERMAID_ARCHER: "Mermaid Archer",
    E.Unit.MERMAID_SWORDSMAN: "Mermaid Swordman", E.Unit.MERMAID_DEFENDER: "Mermaid Defender",
    E.Unit.MERMAID_CLOAK: "Mermaid Cloak", E.Unit.MERMAID_DAGGER: "mermaidDagger",
    E.Unit.JELLY: "jelly", E.Unit.SHARK: "shark", E.Unit.SIREN: "Siren",
    E.Unit.AQUAPULT: "Aquapult", E.Unit.BOOMCHI: "Boomchi", E.Unit.ISLAND: "island",
    E.Unit.CIRU: "Ciru", E.Unit.MANTIS: "Mantis", E.Unit.BUG_EGG: "BugEgg",
    E.Unit.MOTH: "Moth", E.Unit.LARVA: "Larva",
}

# Theme suffix tokens (tribe + skin) used to strip a prefab's default-variant sprite down
# to its base name, so it can be re-themed for the actual owner via DoSpriteLookup.
_THEME_TOKENS = set(E.TRIBE_THEME.values()) | set(E.SKIN_THEME.values())


def _skinned_prefab(prefab: Optional[str], skin: int) -> Optional[str]:
    """Some skins ship a prefab with distinct geometry (different part hierarchy), not just
    re-themed sprites — e.g. the Cute skin's ``Raychi_cute`` / ``Centipede_segment_cute``.
    When such a ``<prefab>_<skin_token>`` was extracted, the engine uses it for that skin, so
    prefer it; otherwise keep the base prefab and let DoSpriteLookup re-theme its sprites."""
    if not prefab or not skin:
        return prefab
    tok = E.SKIN_THEME.get(skin)
    if tok:
        variant = f"{prefab}_{tok}"
        if variant in UNIT_PARTS:
            return variant
    return prefab


def _debase(sprite: str) -> str:
    """Strip a trailing tribe/skin token from a prefab sprite so DoSpriteLookup can re-theme it
    (e.g. the Knight prefab's default mount ``animal_xinxi`` -> base ``animal`` -> ``animal_<tribe>``)."""
    parts = sprite.split("_")
    if len(parts) > 1 and parts[-1] in _THEME_TOKENS:
        return "_".join(parts[:-1])
    return sprite


# ---------------------------------------------------------------- prefab overrides
# A few units don't render straight from their baked prefab transforms; the engine
# special-cases them. We reproduce those here so the JSON stays a faithful raw dump.
def _apply_overrides(prefab: str, parts, *, drop_connection: bool = False):
    """Return parts adjusted for engine special-cases (head scale / removed head /
    fixed un-themed sprites). Parts are copied before mutation."""
    out = []
    for part in parts:
        node = part["node"]
        # SegmentConnector owns the connector at runtime (LateUpdate stretch/rotate
        # toward leader). Drop the prefab's rest-pose Connection VisualPart whenever
        # we draw the dynamic connector (or always on segment prefabs — see caller).
        if drop_connection and str(node).lower().startswith("connection"):
            continue
        # Rammership has no head — the engine leaves its head marker empty (the
        # crew is part of the baked ship art), so drop the inherited Head part.
        if prefab == "Rammership" and node.startswith("Head"):
            continue
        # Rider_Wolf: the wolf IS the mount — the Animals node is the base Rider's
        # horse slot and must not render (wolf/wolftint cover the mount role).
        if prefab == "Rider_Wolf" and node == "Animals":
            continue
        p = part
        # Giant's head is baked oversized in the prefab (HeadScaler 1.2 -> 1.44).
        # Render it at the normal unit head scale instead.
        if prefab == "Giant" and node.startswith("Head"):
            p = dict(part)
            p["scale"] = [1.0, 1.0]
        # Tridention / Amphibian always ride the Aquarion animal regardless of the
        # owner's tribe — mark the mount "fixed" so it is not re-themed.
        if prefab in ("Tridention", "Amphibian") and node == "Animals":
            p = dict(p)
            p["fixed"] = True
        out.append(p)
    return out


# ---------------------------------------------------------------- centipede connector
# SegmentConnector (dump TypeDef 1642) + Unit.UpdateConnector:
#   leader = MapRenderer.GetUnitInstance(unitState.leader)
#   LateUpdate: rotate connector toward leader, localScale.x = distance * 1.7
# Connector VisualPart lives on the segment prefab; head has none. Any centipede
# part with leader>0 gets a dynamic connector (same rule as polytopia.net).
_CONNECTOR_BASE = "cymanti_centipede_connector"


def _is_centipede_part(unit_type: int) -> bool:
    return int(unit_type) in (int(E.Unit.CENTIPEDE), int(E.Unit.SEGMENT))


def _find_unit_tile(ctx, unit_id: int):
    """TileData that holds the unit with the given UnitState.id, or None."""
    uid = int(unit_id)
    if uid <= 0:
        return None
    for t in ctx.map.tiles:
        u = getattr(t, "unit", None)
        if u is not None and int(getattr(u, "id", 0) or 0) == uid:
            return t
    return None


def _tile_center_delta_px(from_xy, to_xy) -> Tuple[float, float]:
    """Pixel vector (Y-down) from from_xy's diamond centre to to_xy's."""
    fx, fy = from_xy
    tx, ty = to_xy
    return (
        ((tx - ty) - (fx - fy)) * P.HALF_W,
        -((tx + ty) - (fx + fy)) * P.HALF_H,
    )


def _rotate_about_pivot(
    img: Image, angle_deg: float, pvx: float, pvy: float
) -> Tuple[Image, float, float]:
    """Rotate ``img`` CCW by ``angle_deg`` about Unity-style pivot (pvx, pvy).

    Returns (rotated_image, pivot_x, pivot_y) in the result's top-left pixel space.
    """
    pil = img.to_pil()
    w, h = pil.size
    # Pivot in top-left pixel coords (Unity pvy: 0=bottom, 1=top).
    px = float(pvx) * w
    py = (1.0 - float(pvy)) * h
    # Pad so the pivot sits at the canvas centre, then rotate about centre.
    pad_l = int(math.ceil(max(0.0, w - px)))
    pad_r = int(math.ceil(max(0.0, px)))
    pad_t = int(math.ceil(max(0.0, h - py)))
    pad_b = int(math.ceil(max(0.0, py)))
    # Extra margin so corners survive rotation.
    diag = int(math.ceil(math.hypot(w, h)))
    m = diag
    canvas = PILImage.new("RGBA", (w + pad_l + pad_r + 2 * m, h + pad_t + pad_b + 2 * m), (0, 0, 0, 0))
    ox, oy = m + pad_l, m + pad_t
    canvas.paste(pil, (ox, oy), pil)
    cx = ox + px
    cy = oy + py
    # Shift so (cx,cy) → image centre, rotate, track pivot (= centre).
    recentered = PILImage.new("RGBA", canvas.size, (0, 0, 0, 0))
    dx = canvas.size[0] / 2.0 - cx
    dy = canvas.size[1] / 2.0 - cy
    recentered.paste(canvas, (round(dx), round(dy)), canvas)
    rotated = recentered.rotate(angle_deg, resample=PILImage.Resampling.BICUBIC, expand=True)
    # Pivot is at the centre of ``recentered``; after expand, find that point.
    # Pillow rotate(expand=True) keeps the old centre at the new centre.
    piv_x = rotated.size[0] / 2.0
    piv_y = rotated.size[1] / 2.0
    # Trim transparent margins but keep pivot coordinates correct.
    bbox = rotated.getbbox()
    if bbox is None:
        return Image.new(1, 1, (0, 0, 0, 0)), 0.0, 0.0
    l, t, r, b = bbox
    cropped = rotated.crop(bbox)
    return Image.from_pil(cropped), piv_x - l, piv_y - t


# Prefab Connection local pos on Centipede_segment (unit_parts.json).
_CONNECTOR_PREFAB_POS = (0.021, 0.104)


def connector_items(ctx, x: int, y: int) -> List[Placement]:
    """Dynamic SegmentConnector for a centipede part with leader > 0.

    Matches polytopia.net / SegmentConnector.LateUpdate:
      translate to this unit, rotate toward leader, scale X by dist/nativeWidth
      so the shaft spans tile-centre to tile-centre (Unity: localScale.x = worldDist×1.7
      with native world width ≈ 1/1.7).
    Pivot sits on the segment's Connection attachment (unit seat + prefab pos).
    Drawn at SORT_UNIT_CONNECTOR (under the unit sprites).
    """
    tile = ctx.tile_at(x, y)
    if tile is None or ctx.is_hidden(tile):
        return []
    unit = tile.unit
    if unit is None or unit.type == E.Unit.NONE:
        return []
    if not _is_centipede_part(unit.type):
        return []
    leader_id = int(getattr(unit, "leader", 0) or 0)
    if leader_id <= 0:
        return []
    # Invisible enemy: whole unit (and its connector) hidden.
    if ctx.viewer_id != 0xFF and unit.owner != ctx.viewer_id:
        if E.UnitEffect.INVISIBLE in (unit.effects or []):
            return []

    leader_tile = _find_unit_tile(ctx, leader_id)
    if leader_tile is None:
        return []

    to_leader_x, to_leader_y = _tile_center_delta_px((x, y), (leader_tile.x, leader_tile.y))
    dist = math.hypot(to_leader_x, to_leader_y)
    if dist < 1.0:
        return []

    tribe, skin = ctx.player_tribe_skin(unit.owner)
    name = ctx.resolve(_CONNECTOR_BASE, tribe, skin)[0]
    if not name or not ctx.store.exists(name):
        name = _CONNECTOR_BASE
        if not ctx.store.exists(name):
            return []
    try:
        spr = ctx.store.get(name)
    except KeyError:
        return []

    # Website: ctx.scale(dist/naturalWidth, 1) then drawImage at native (w,h).
    # Tile pixels match (~256), so keep the PNG's native height — applying
    # render_scale here made the shaft ~20% thicker than the in-game look.
    nw = max(1, spr.w)
    nh = max(1, spr.h)
    target_w = max(1, round(dist))
    stretched = spr.resized(target_w, nh) if (target_w != nw or nh != spr.h) else spr

    pvx, pvy = _pivot(name)
    # Angle of vector from leader → this unit (website canvas rotate / Unity).
    angle = math.degrees(math.atan2(-to_leader_y, -to_leader_x))
    rot, piv_x, piv_y = _rotate_about_pivot(stretched, angle, pvx, pvy)
    # Seat with the unit (UNIT_OFFSET) plus the prefab Connection local pos.
    px, py = _CONNECTOR_PREFAB_POS
    dx = round(-piv_x + UNIT_OFFSET_PX[0] + px * P.PPU)
    dy = round(-piv_y + UNIT_OFFSET_PX[1] - py * P.PPU)
    return [Placement(E.SORT_UNIT_CONNECTOR, rot, dx, dy)]


# ---------------------------------------------------------------- action affordances
# Player-perspective unit chrome (Unit.UpdateObject + UnitStatusDisplay.SetState):
#   untouched  (!moved && !attacked) → cyan body outline + white typeOutline ring
#   has action (can still move, or dash with an adjacent enemy) → cyan outline, no ring
#   exhausted  (moved with no dash target, attacked && !can_move, or frozen)
#              → no outline, no ring, grey wash
#
# Flag half of UnitState.CanMove / CanAttack (Frozen blocks both). After moving,
# a remaining attack is only a dash into an orthogonally adjacent enemy.
def unit_can_move(unit) -> bool:
    if bool(getattr(unit, "moved", False)):
        return False
    effects = getattr(unit, "effects", None) or []
    return E.UnitEffect.FROZEN not in {int(e) for e in effects}


def unit_can_attack(unit) -> bool:
    if bool(getattr(unit, "attacked", False)):
        return False
    effects = getattr(unit, "effects", None) or []
    return E.UnitEffect.FROZEN not in {int(e) for e in effects}


# UnitData.unitAbilities contains "dash" (GameLogicData28).
_DASH_UNITS = {
    int(E.Unit.SCOUT), int(E.Unit.WARRIOR), int(E.Unit.RIDER), int(E.Unit.KNIGHT),
    int(E.Unit.ARCHER), int(E.Unit.SWORDSMAN), int(E.Unit.POLYTAUR),
    int(E.Unit.BABY_DRAGON), int(E.Unit.FIRE_DRAGON), int(E.Unit.AMPHIBIAN),
    int(E.Unit.TRIDENTION), int(E.Unit.BATTLE_SLED), int(E.Unit.ICE_ARCHER),
    int(E.Unit.HEXAPOD), int(E.Unit.DOOMUX), int(E.Unit.PHYCHI),
    int(E.Unit.CENTIPEDE), int(E.Unit.SEGMENT), int(E.Unit.RAYCHI),
    int(E.Unit.DAGGER), int(E.Unit.CLOAK), int(E.Unit.CLOAK_BOAT),
    int(E.Unit.PIRATE), int(E.Unit.SCOUTSHIP), int(E.Unit.RAMMERSHIP),
    int(E.Unit.MERMAID_WARRIOR), int(E.Unit.MERMAID_ARCHER),
    int(E.Unit.MERMAID_SWORDSMAN), int(E.Unit.MERMAID_CLOAK),
    int(E.Unit.MERMAID_DAGGER), int(E.Unit.SHARK), int(E.Unit.BOOMCHI),
    int(E.Unit.CIRU), int(E.Unit.MANTIS), int(E.Unit.MOTH), int(E.Unit.LARVA),
}

_ORTHO = ((0, 1), (0, -1), (1, 0), (-1, 0))


def unit_has_dash(unit) -> bool:
    return int(unit.type) in _DASH_UNITS


def _enemy_adjacent(ctx, unit, x: int, y: int) -> bool:
    """True when an enemy unit sits on an orthogonal neighbour tile."""
    owner = int(unit.owner)
    for dx, dy in _ORTHO:
        t = ctx.tile_at(x + dx, y + dy)
        if t is None:
            continue
        u = getattr(t, "unit", None)
        if u is None or u.type == E.Unit.NONE:
            continue
        if int(u.owner) == owner:
            continue
        if E.UnitEffect.INVISIBLE in (u.effects or []):
            continue
        return True
    return False


def unit_can_perform_action(ctx, unit, x: int, y: int) -> bool:
    """Any action left this turn (move, or dash into an adjacent enemy)."""
    if unit_can_move(unit):
        return True
    if not unit_can_attack(unit):
        return False
    # moved && !attacked: grey unless dash and an enemy is next to the unit.
    return unit_has_dash(unit) and _enemy_adjacent(ctx, unit, x, y)


def unit_is_untouched(unit) -> bool:
    """Neither moved nor attacked this turn (and not frozen)."""
    return unit_can_move(unit) and unit_can_attack(unit)


# ---------------------------------------------------------------- visual modifiers
# Unit.GetOverlayColorAndStrength (RVA 0x2B7E5C4) — IEEE-754 constants from the
# fcsel chain. Later checks overwrite earlier ones; Petrified wins. When
# canPerformAction is false, strength is forced to 0.4 (keeps effect RGB).
def _get_overlay_color_and_strength(
    can_perform_action: bool, effects
) -> Tuple[Tuple[int, int, int], float]:
    """Mirror Unit.GetOverlayColorAndStrength → (rgb 0-255, strength)."""
    eff = {int(e) for e in (effects or [])}
    # Boosted(2)
    if E.UnitEffect.BOOSTED in eff:
        s9, s11, s13 = 0.3, 0.0, 0.5
    else:
        s9, s11, s13 = 1.0, 1.0, 0.0
    s8, s10, s12 = 1.0, 0.0, 0.5
    # Swift(6)
    if E.UnitEffect.SWIFT in eff:
        s9, s11, s13 = 0.7, 0.1, 0.4
    # Poisoned(1)
    if E.UnitEffect.POISONED in eff:
        s14, s9, s10, s11 = 0.4, 0.9, 0.0, 0.3
    else:
        s14, s10, s11 = s8, s11, s13
    # Frozen(0)
    if E.UnitEffect.FROZEN in eff:
        s13, s9, s8, s10 = 0.4, 0.9, 1.0, 0.5
    else:
        s13, s8, s10 = s14, s10, s11
    # Petrified(5)
    if E.UnitEffect.PETRIFIED in eff:
        rf, gf, bf, strength = 0.1, 0.1, 0.1, 0.6
    else:
        rf, gf, bf, strength = s13, s9, s8, s10
    if not can_perform_action:
        strength = 0.4
    return (
        (min(255, int(rf * 255 + 0.5)),
         min(255, int(gf * 255 + 0.5)),
         min(255, int(bf * 255 + 0.5))),
        float(strength),
    )


# UpdateUnitEffectParticles — pool id is Enum.ToString(UnitEffect); particle
# textures are Unit<Name> (plus bubble for Bubble). Frozen is suppressed while
# Petrified is active (UpdateObject). Static renderer pastes one frame.
_EFFECT_PARTICLES: List[Tuple[int, str]] = [
    (E.UnitEffect.SWIFT, "UnitSwift"),
    (E.UnitEffect.POISONED, "UnitPoisoned"),
    (E.UnitEffect.BOOSTED, "UnitBoosted"),
    (E.UnitEffect.PETRIFIED, "UnitPetrified"),
    (E.UnitEffect.FROZEN, "UnitFrozen"),  # skipped if Petrified present
]
_BUBBLE_SPRITE = "bubble"

# Alpha for an invisible unit visible to its own owner (engine: Unit.SetAlpha).
# Toolbox static renderer uses 0.45; game value not a literal in UpdateObject.
_INVISIBLE_ALPHA = 0.45


def _apply_alpha(img: Image, alpha: float) -> Image:
    """Return a copy of img with all pixel alphas multiplied by alpha."""
    return img.multiply_alpha(alpha)


def _paste_particle_frame(
    unit_img: Image, origin_x: float, origin_y: float, ctx, sprite_name: str
) -> Tuple[Image, float, float]:
    """Center one static particle frame on the unit composite (game particles
    attach to the unit transform; we freeze a single sprite frame)."""
    if not ctx.store.exists(sprite_name):
        return unit_img, origin_x, origin_y
    try:
        pimg = ctx.store.get(sprite_name)
    except KeyError:
        return unit_img, origin_x, origin_y
    rs = SM.render_scale(sprite_name)
    dw = max(1, round(pimg.w * rs))
    dh = max(1, round(pimg.h * rs))
    if dw != pimg.w or dh != pimg.h:
        pimg = pimg.resized(dw, dh)
    # Unit image centre ≈ particle attach point.
    cx = unit_img.w * 0.5
    cy = unit_img.h * 0.5
    tlx = cx - dw * 0.5
    tly = cy - dh * 0.5
    minx = min(0.0, tlx)
    miny = min(0.0, tly)
    maxx = max(float(unit_img.w), tlx + dw)
    maxy = max(float(unit_img.h), tly + dh)
    W = int(math.ceil(maxx - minx))
    H = int(math.ceil(maxy - miny))
    canvas = Image.new(W, H, (0, 0, 0, 0))
    canvas.paste(unit_img, round(-minx), round(-miny))
    canvas.paste(pimg, round(tlx - minx), round(tly - miny))
    return canvas, origin_x - minx, origin_y - miny


def _apply_effect_particles(
    unit_img: Image, origin_x: float, origin_y: float, ctx, effects
) -> Tuple[Image, float, float]:
    """Static stand-in for UpdateUnitEffectParticles + ShowBubble."""
    eff = {int(e) for e in (effects or [])}
    img, ox, oy = unit_img, origin_x, origin_y
    for effect, sprite in _EFFECT_PARTICLES:
        if effect not in eff:
            continue
        if effect == E.UnitEffect.FROZEN and E.UnitEffect.PETRIFIED in eff:
            continue
        img, ox, oy = _paste_particle_frame(img, ox, oy, ctx, sprite)
    if E.UnitEffect.BUBBLE in eff:
        img, ox, oy = _paste_particle_frame(img, ox, oy, ctx, _BUBBLE_SPRITE)
    return img, ox, oy


# ---------------------------------------------------------------- skinning logic
# SkinningLogic (SkinVisualsReference.SkinningLogic): governs how each part is re-skinned.
SKIN_USE_TRIBE = 0       # owner tribe (+ skin) — the normal paper-doll parts
SKIN_USE_CLIMATE = 1     # owner tribe (+ skin) — engine uses tile climate; we follow owner
SKIN_USE_BIRTH_CLIMATE = 2  # unit.birth_climate when set, else owner tribe
SKIN_DONT_CHANGE = 3     # keep the prefab's literal sprite (no re-skin at all)


def _as_tribe(value, fallback: int) -> int:
    """TribeType from a serialized climate/tribe field. 0 and Skin.NONE (65535) are unset."""
    try:
        v = int(value or 0)
    except (TypeError, ValueError):
        return int(fallback)
    if v < 0:
        v &= 0xFFFF
    if v == 0 or v == 0xFFFF or v not in E.TRIBE_THEME:
        return int(fallback)
    return v

# (tribe, skin) pairs whose ``animal_<skin>`` sprite is a placeholder, not a real mount.
# Kept for any other (tribe, skin) pairs added in future; the ELYRION/DARKELF rider now
# routes to Rider_Wolf (see _TRIBE_SKIN_PREFAB) so this set no longer affects it.
_ANIMAL_KEEP_TRIBE: set = set()

# (tribe, skin) -> {base_prefab: override_prefab} for skins whose variant prefab name does
# not follow the ``{prefab}_{skin_token}`` convention (e.g. Elyrion DarkElf Rider → Rider_Wolf
# rather than Rider_darkelf, which doesn't exist).
_TRIBE_SKIN_PREFAB = {
    (int(E.Tribe.ELYRION), int(E.Skin.DARKELF)): {"Rider": "Rider_Wolf"},
}


def _resolve_part(ctx, part, tribe, skin, climate, birth_climate):
    """Resolve a part's themed sprite name per its SkinningLogic (engine: SkinWorldObject,
    which looks up the TribeAndSkin pair selected by the part's skinLogic and passes BOTH
    its tribe and skin to DoSpriteLookup).

    UseTribe / UseClimate -> owner tribe + skin; UseBirthClimate -> unit birth climate
    (falling back to owner tribe) + owner skin — so a skin that ships its own mount
    (``animal_<skin>``, e.g. Zebasi/Arty) swaps the animal, while a skin without one falls
    back to ``animal_<tribe>``; DontChangeSkin (or a ``fixed`` part) -> literal prefab sprite.
    Unit art never themes from the tile's climate/skin."""
    sl = part.get("skinLogic", SKIN_USE_TRIBE)
    if part.get("fixed"):
        # Locked to its own tribe's art (Aquarion mount: never re-themed to the owner),
        # but the skin still applies: animal_aquarion -> animal_aquarion_swamp under Swamp.
        return ctx.resolve(part["sprite"], 0, skin)[0]
    if sl == SKIN_DONT_CHANGE:
        return ctx.resolve(part["sprite"], 0, 0)[0]
    base = _debase(part["sprite"])
    if sl == SKIN_USE_BIRTH_CLIMATE:
        eff_tribe = birth_climate
    elif sl == SKIN_USE_CLIMATE:
        eff_tribe = climate
    else:
        eff_tribe = tribe
    # Skip the skin for placeholder mounts so the tribe's real animal is kept (DarkElf).
    eff_skin = 0 if (base == "animal" and (int(eff_tribe), int(skin)) in _ANIMAL_KEEP_TRIBE) else skin
    return ctx.resolve(base, eff_tribe, eff_skin)[0]


# ---------------------------------------------------------------- compositor

def _build_outline(ctx, parts, tribe, skin, team, climate, birth_climate
                   ) -> Optional[Tuple[Image, float, float]]:
    """Composite _Outline companion sprites into one image at the same positions as
    the main unit parts.  Each outline sprite uses its OWN render_scale and pivot
    (distinct from the base sprite's — they are low-res PNGs that scale up to the
    same world size).  Tinted with the team colour (engine: SetOutlineColor)."""
    PPU = P.PPU
    placed = []
    minx = miny = 1e18
    maxx = maxy = -1e18
    for part in parts:
        name = _resolve_part(ctx, part, tribe, skin, climate, birth_climate)
        if not name:
            continue
        oname = name + "_Outline"
        if not ctx.store.exists(oname):
            continue
        try:
            img = ctx.store.get(oname)
        except KeyError:
            continue
        # Use the outline sprite's own render_scale and pivot — NOT the base sprite's.
        # Outline PNGs have a different (much lower) PPU so their scale is ~4× the base.
        rscale = SM.render_scale(oname)
        sx = part["scale"][0] * rscale
        sy = part["scale"][1] * rscale
        dw = max(1, round(img.w * sx))
        dh = max(1, round(img.h * sy))
        if dw != img.w or dh != img.h:
            img = img.resized(dw, dh)
        if team:
            img = img.tinted(team)
        pvx, pvy = _pivot(oname)
        piv_x = part["pos"][0] * PPU
        piv_y = -part["pos"][1] * PPU
        tlx = piv_x - pvx * dw
        tly = piv_y - (1.0 - pvy) * dh
        if part["node"].startswith("Head"):
            hx, hy = _head_correction(tribe, skin)
            tlx += hx * dw
            tly += (HEAD_OFFSET_FRAC + hy) * dh
        placed.append((img, tlx, tly))
        minx = min(minx, tlx); miny = min(miny, tly)
        maxx = max(maxx, tlx + dw); maxy = max(maxy, tly + dh)

    if not placed:
        return None
    W = int(math.ceil(maxx - minx))
    H = int(math.ceil(maxy - miny))
    canvas = Image.new(W, H, (0, 0, 0, 0))
    for img, tlx, tly in placed:
        canvas.paste(img, round(tlx - minx), round(tly - miny))
    return canvas, -minx, -miny


def _build_unit(ctx, parts, tribe, skin, team, climate, birth_climate
                ) -> Optional[Tuple[Image, float, float]]:
    """Composite the prefab parts into one image. Returns (image, origin_x, origin_y) where
    (origin_x, origin_y) is the SpriteContainer world origin within the image (the point that
    seats on the tile). Each part's sprite pivot lands at part.pos * PPU; size = ppu-scale *
    prefab local scale; tinted parts get the team colour. ``climate`` / ``birth_climate``
    theme UseClimate / UseBirthClimate parts (both owner-derived, never the tile)."""
    PPU = P.PPU
    placed = []                                  # (img, tlx, tly) in origin-relative px
    minx = miny = 1e18
    maxx = maxy = -1e18
    for part in parts:
        name = _resolve_part(ctx, part, tribe, skin, climate, birth_climate)
        if not name or not ctx.store.exists(name):
            continue
        try:
            img = ctx.store.get(name)
        except KeyError:
            # Catalog lists the sprite but its PNG wasn't extracted (extraction gap, e.g.
            # cymanti_centipede_bottom_head after a re-extract); skip the part, don't crash.
            continue
        rscale = SM.render_scale(name)
        sx = part["scale"][0] * rscale
        sy = part["scale"][1] * rscale
        dw = max(1, round(img.w * sx))
        dh = max(1, round(img.h * sy))
        if dw != img.w or dh != img.h:
            img = img.resized(dw, dh)
        if part["tint"] and team:
            img = img.tinted(team)
        pvx, pvy = _pivot(name)
        # part transform position (world units, Y up) -> origin-relative pixels (Y down)
        piv_x = part["pos"][0] * PPU
        piv_y = -part["pos"][1] * PPU
        tlx = piv_x - pvx * dw                   # sprite pivot lands at (piv_x, piv_y)
        tly = piv_y - (1.0 - pvy) * dh
        if part["node"].startswith("Head"):
            hx, hy = _head_correction(tribe, skin)   # per-tribe/skin nudge, % of head size
            tlx += hx * dw                           # +x = right
            tly += (HEAD_OFFSET_FRAC + hy) * dh      # baseline seat + per-tribe y (+ = lower)
        placed.append((img, tlx, tly))
        minx = min(minx, tlx); miny = min(miny, tly)
        maxx = max(maxx, tlx + dw); maxy = max(maxy, tly + dh)

    if not placed:
        return None
    W = int(math.ceil(maxx - minx))
    H = int(math.ceil(maxy - miny))
    canvas = Image.new(W, H, (0, 0, 0, 0))
    for img, tlx, tly in placed:                 # parts are pre-sorted by m_SortingOrder
        canvas.paste(img, round(tlx - minx), round(tly - miny))
    return canvas, -minx, -miny                  # origin (world 0,0) within the canvas


# ---------------------------------------------------------------- emission
def items(ctx, x, y) -> List[Placement]:
    tile = ctx.tile_at(x, y)
    if tile is None:
        return []
    unit = tile.unit
    if unit is None or unit.type == E.Unit.NONE or ctx.is_hidden(tile):
        return []

    effects = unit.effects or []

    # Invisible enemy: unit is hidden from the viewer entirely (IsInvisibleForLocalPlayer).
    if ctx.viewer_id != 0xFF and unit.owner != ctx.viewer_id:
        if E.UnitEffect.INVISIBLE in effects:
            return []

    owner = unit.owner
    # Unit art themes from the owning player only — never the tile's climate/skin.
    # birth_climate / birth_climate_skin_type of Skin.NONE serialize as 65535
    # and must not win over the owner's tribe/skin (that looks up no theme and
    # falls through to generic Nature sprites).
    tribe, skin = ctx.player_tribe_skin(owner)
    climate = tribe
    birth = _as_tribe(unit.birth_climate, tribe)

    prefab = _skinned_prefab(ENUM_TO_PREFAB.get(unit.type), skin)
    ts_overrides = _TRIBE_SKIN_PREFAB.get((int(tribe), int(skin)), {})
    if prefab in ts_overrides:
        prefab = ts_overrides[prefab]
    parts = UNIT_PARTS.get(prefab) if prefab else None
    if not parts:
        return []
    # SegmentConnector drives the connector at runtime — never bake the prefab's
    # rest-pose Connection part (dynamic connector_items draws it when leader>0).
    drop_conn = bool(prefab and str(prefab).startswith("Centipede_segment"))
    parts = _apply_overrides(prefab, parts, drop_connection=drop_conn)

    team = ctx.player_color(owner)
    flip = bool(unit.flipped)

    # Action chrome is player-perspective only (IsPlayerLocal / perspective_id).
    is_local = ctx.is_perspective_owner(owner)
    can_perform = unit_can_perform_action(ctx, unit, x, y)

    # Cyan body outline: own unit that still has any action left.
    # Engine: ShowOutline(canPerformAction && IsPlayerLocal && !hideOutlines).
    show_outline = is_local and can_perform

    # GetOverlayColorAndStrength(canPerformAction, effects) → ColorizeUnit.
    # Exhausted own units get the 0.4 wash; enemies keep effect tints only.
    overlay_can_perform = can_perform if is_local else True
    overlay_rgb, overlay_strength = _get_overlay_color_and_strength(
        overlay_can_perform, effects
    )

    # Build main unit composite.
    built = _build_unit(ctx, parts, tribe, skin, team, climate, birth)
    if built is None:
        return []
    img, ox, oy = built

    # Apply ColorizeUnit overlay (status effect and/or exhausted wash).
    if overlay_strength > 0.0:
        img = img.colorized(overlay_rgb, overlay_strength)

    # Static particle frames (UpdateUnitEffectParticles / ShowBubble).
    img, ox, oy = _apply_effect_particles(img, ox, oy, ctx, effects)

    if flip:
        img = img.flipped_x()
        ox = img.w - ox

    # Invisible owner: unit is translucent (engine: Unit.SetAlpha).
    if E.UnitEffect.INVISIBLE in effects:
        img = _apply_alpha(img, _INVISIBLE_ALPHA)

    if UNIT_SCALE != 1.0:
        nw = max(1, round(img.w * UNIT_SCALE))
        nh = max(1, round(img.h * UNIT_SCALE))
        img = img.resized(nw, nh)
        ox = ox * UNIT_SCALE
        oy = oy * UNIT_SCALE

    # Tile-local: SpriteContainer origin (world 0,0) seats on the diamond centre (0,0), so the
    # composite's top-left sits at -(origin) plus the seat-convention nudge UNIT_OFFSET_PX.
    dx = round(-ox + UNIT_OFFSET_PX[0])
    dy = round(-oy + UNIT_OFFSET_PX[1])

    result = []

    # Outline: composite _Outline sprites placed one sub-layer below the unit.
    if show_outline:
        ob = _build_outline(ctx, parts, tribe, skin, OUTLINE_COLOR, climate, birth)
        if ob is not None:
            oimg, oox, ooy = ob
            if flip:
                oimg = oimg.flipped_x()
                oox = oimg.w - oox
            if UNIT_SCALE != 1.0:
                onw = max(1, round(oimg.w * UNIT_SCALE))
                onh = max(1, round(oimg.h * UNIT_SCALE))
                oimg = oimg.resized(onw, onh)
                oox = oox * UNIT_SCALE
                ooy = ooy * UNIT_SCALE
            odx = round(-oox + UNIT_OFFSET_PX[0])
            ody = round(-ooy + UNIT_OFFSET_PX[1])
            result.append(Placement(E.SORT_UNIT - 1, oimg, odx, ody))

    result.append(Placement(E.SORT_UNIT, img, dx, dy))
    return result
