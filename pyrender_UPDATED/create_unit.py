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

Visual modifiers (engine: Unit.UpdateObject / GetOverlayColorAndStrength):
  Invisible enemy   → unit skipped entirely  (IsInvisibleForLocalPlayer)
  Invisible owner   → unit at INVISIBLE_ALPHA  (Unit.SetAlpha)
  Outline (untouched) → _Outline sprites at SORT_UNIT-1, tinted team colour
  Frozen   (0) → lerp (204,230,255) @ 0.4   blue-white ice
  Poisoned (1) → lerp (102,230, 26) @ 0.5   green
  Boosted  (2) → lerp ( 77, 26,179) @ 0.5   purple (Mindbender boost)
  Petrified(5) → lerp ( 26, 26, 26) @ 0.8   near-black stone
  Exhausted    → lerp (128,128,128) @ 0.5   grey (TBD: pending pixel verification)
  Priority: Petrified > Frozen > Poisoned > Boosted > Exhausted
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
UNIT_SCALE = 0.95

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
def _apply_overrides(prefab: str, parts):
    """Return parts adjusted for engine special-cases (head scale / removed head /
    fixed un-themed sprites). Parts are copied before mutation."""
    out = []
    for part in parts:
        node = part["node"]
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


# ---------------------------------------------------------------- visual modifiers
# ColorizeUnit overlay: (RGB 0-255, strength 0-1) per UnitEffect.
# Values confirmed from recon/units.md §6 IEEE-754 constant pool decode.
# Priority list is ordered most-to-least dominant; first match wins.
_EFFECT_OVERLAYS = [
    (E.UnitEffect.PETRIFIED, (26,  26,  26), 0.8),   # ~(0.1,0.1,0.1)
    (E.UnitEffect.FROZEN,    (204, 230, 255), 0.4),   # ~(0.8,0.9,1.0)
    (E.UnitEffect.POISONED,  (102, 230,  26), 0.5),   # ~(0.4,0.9,0.1)
    (E.UnitEffect.BOOSTED,   (77,   26, 179), 0.5),   # ~(0.3,0.1,0.7)
]
# Grey overlay applied when the unit has moved (canPerformAction=false, no status effect).
# High-value grey so the additive lerp lightens (washes out) the unit rather than darkening it.
# Exact values TBD — pending pixel verification against live screenshot.
_EXHAUSTED_OVERLAY = ((200, 200, 200), 0.5)

# Alpha for an invisible unit visible to its own owner (engine: Unit.SetAlpha).
# Exact value TBD — pending pixel verification.
_INVISIBLE_ALPHA = 0.5


def _apply_alpha(img: Image, alpha: float) -> Image:
    """Return a copy of img with all pixel alphas multiplied by alpha."""
    return img.multiply_alpha(alpha)


# ---------------------------------------------------------------- skinning logic
# SkinningLogic (SkinVisualsReference.SkinningLogic): governs how each part is re-skinned.
SKIN_USE_TRIBE = 0       # owner tribe (+ skin) — the normal paper-doll parts
SKIN_USE_CLIMATE = 1     # the tile's climate tribe (+ skin) — e.g. the rider's mount
SKIN_USE_BIRTH_CLIMATE = 2  # the unit's birth climate (we approximate with tile climate)
SKIN_DONT_CHANGE = 3     # keep the prefab's literal sprite (no re-skin at all)

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


def _resolve_part(ctx, part, tribe, skin, climate):
    """Resolve a part's themed sprite name per its SkinningLogic (engine: SkinWorldObject,
    which looks up the TribeAndSkin pair selected by the part's skinLogic and passes BOTH
    its tribe and skin to DoSpriteLookup).

    UseTribe -> owner tribe + skin; UseClimate/UseBirthClimate -> the tile-climate tribe,
    but STILL with the player's skin -> so a skin that ships its own mount (``animal_<skin>``,
    e.g. Zebasi/Arty) swaps the animal, while a skin without one falls back to the climate's
    ``animal_<tribe>``; DontChangeSkin (or a ``fixed`` part) -> the literal prefab sprite."""
    sl = part.get("skinLogic", SKIN_USE_TRIBE)
    if part.get("fixed"):
        # Locked to its own tribe's art (Aquarion mount: never re-themed to the owner),
        # but the skin still applies: animal_aquarion -> animal_aquarion_swamp under Swamp.
        return ctx.resolve(part["sprite"], 0, skin)[0]
    if sl == SKIN_DONT_CHANGE:
        return ctx.resolve(part["sprite"], 0, 0)[0]
    base = _debase(part["sprite"])
    eff_tribe = climate if sl in (SKIN_USE_CLIMATE, SKIN_USE_BIRTH_CLIMATE) else tribe
    # Skip the skin for placeholder mounts so the tribe's real animal is kept (DarkElf).
    eff_skin = 0 if (base == "animal" and (int(eff_tribe), int(skin)) in _ANIMAL_KEEP_TRIBE) else skin
    return ctx.resolve(base, eff_tribe, eff_skin)[0]


# ---------------------------------------------------------------- compositor

def _build_outline(ctx, parts, tribe, skin, team, climate) -> Optional[Tuple[Image, float, float]]:
    """Composite _Outline companion sprites into one image at the same positions as
    the main unit parts.  Each outline sprite uses its OWN render_scale and pivot
    (distinct from the base sprite's — they are low-res PNGs that scale up to the
    same world size).  Tinted with the team colour (engine: SetOutlineColor)."""
    PPU = P.PPU
    placed = []
    minx = miny = 1e18
    maxx = maxy = -1e18
    for part in parts:
        name = _resolve_part(ctx, part, tribe, skin, climate)
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


def _build_unit(ctx, parts, tribe, skin, team, climate) -> Optional[Tuple[Image, float, float]]:
    """Composite the prefab parts into one image. Returns (image, origin_x, origin_y) where
    (origin_x, origin_y) is the SpriteContainer world origin within the image (the point that
    seats on the tile). Each part's sprite pivot lands at part.pos * PPU; size = ppu-scale *
    prefab local scale; tinted parts get the team colour. ``climate`` themes UseClimate parts."""
    PPU = P.PPU
    placed = []                                  # (img, tlx, tly) in origin-relative px
    minx = miny = 1e18
    maxx = maxy = -1e18
    for part in parts:
        name = _resolve_part(ctx, part, tribe, skin, climate)
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
    tribe, pskin = ctx.player_tribe_skin(owner)
    skin = (unit.birth_climate_skin_type
            if unit.birth_climate_skin_type and unit.birth_climate_skin_type > 0
            else pskin)

    prefab = _skinned_prefab(ENUM_TO_PREFAB.get(unit.type), skin)
    ts_overrides = _TRIBE_SKIN_PREFAB.get((int(tribe), int(skin)), {})
    if prefab in ts_overrides:
        prefab = ts_overrides[prefab]
    parts = UNIT_PARTS.get(prefab) if prefab else None
    if not parts:
        return []
    parts = _apply_overrides(prefab, parts)

    team = ctx.player_color(owner)
    flip = bool(unit.flipped)
    # UseClimate parts (the rider's mount, etc.) follow the tile's climate, not the skin.
    climate = tile.climate if tile.climate else tribe

    # Outline: baseline-only — viewer's own unit, not yet moved, no active effects.
    # Engine: ShowOutline / SetOutlineColor(team colour) in Unit.UpdateObject.
    show_outline = (
        ctx.viewer_id != 0xFF
        and unit.owner == ctx.viewer_id
        and not unit.moved
        and not effects
    )

    # Status-effect overlay — first match in priority order wins.
    overlay_rgb: Optional[Tuple[int, int, int]] = None
    overlay_strength = 0.0
    for effect, rgb, strength in _EFFECT_OVERLAYS:
        if effect in effects:
            overlay_rgb = rgb
            overlay_strength = strength
            break

    # Exhausted grey — applied only when no status overlay and unit has moved.
    if overlay_rgb is None and unit.moved:
        overlay_rgb, overlay_strength = _EXHAUSTED_OVERLAY

    # Build main unit composite.
    built = _build_unit(ctx, parts, tribe, skin, team, climate)
    if built is None:
        return []
    img, ox, oy = built

    # Apply ColorizeUnit overlay (status effect or exhausted grey).
    # Uses additive lerp (colorized), not multiply-lerp (tinted) — see image.py.
    if overlay_rgb is not None:
        img = img.colorized(overlay_rgb, overlay_strength)

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
        ob = _build_outline(ctx, parts, tribe, skin, OUTLINE_COLOR, climate)
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
