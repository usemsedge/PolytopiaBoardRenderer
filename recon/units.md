# Slice: Units — Unit compositing (body/head/weapon/bodytint + overlays)

## 1. Summary
A unit is drawn as a **multi-layer paper-doll**, not a single sprite. `Tile$$RenderUnit`
(0x2CDD620) creates/positions a `Unit` WorldObject from the tile's `UnitState`, places it at
`MapExtensions.ToPosition(coords)` (0x2CC11AC), then `Unit.UpdateObject(SkinVisualsTransientData)`
(0x2DA0000) composites it. The visual is assembled by `SkinVisualsRenderer.SkinUnit`
(0x2D9E010) iterating a `SkinVisualsReference.VisualPart[]` (body, head, weapon, bodytint,
plus shield/quiver accessories). For each part the engine takes a base name (e.g. `body_default`,
`head`, `weapon_sword`, `bodytint_default`) and resolves the best variant via
`SpriteAtlasManager.DoSpriteLookup(baseName, tribe, skin, checkForOutline, level)` (0x2B2F5B0),
which appends a `_<skin>` and/or `_<tribe>` suffix and returns the first variant present in the
atlas (else the bare base). **Head carries tribe identity** (`head_imperius`, `head_bardur`),
**body/weapon are skin-driven** (suffixes only for special unit *skins*, not for base tribes),
and **bodytint layers receive the player team color**. Status effects (Frozen/Poisoned/Boosted/
Petrified) drive an HSV-style overlay color applied through `SkinVisualsRenderer.ColorizeUnit`
(0x2D9E864). Horizontal facing is a simple X-flip from `UnitState.flipped` via `Unit.set_Flipped`
(0x2DA0BEC). Many large/naval/tribe-special units instead use a single whole-body `unit_*` (+`_tint`)
or `<tribe>_<name>` sprite rather than the body/head/weapon stack.

## 2. Constants
| Value | Decoded | Source |
|-------|---------|--------|
| Player color decode divisor `0x437F0000` | 255.0 | `ColorUtils.ColorFromInt` 0x2CB175C |
| Color packing | int = `0x00RRGGBB`; R=bits16-23, G=bits8-15, B=bits0-7; alpha=1.0 | ColorFromInt 0x2CB175C (`ubfx #0x10/#8`, `and #0xff`) |
| MAX_LEVEL | 30 (level clamp for level-suffixed sprites) | SkinVisualsRenderer dump.cs 375708; clamp `csel ... #0x1e` in SkinWorldObject 0x2D9DC30 |
| `UnitState.flipped` offset | 0x54 (byte) | dump.cs 776877; `ldrb w1,[x8,#0x54]` 0x2DA04C0 |
| `UnitState.type` offset | 0x24 (UnitData.Type) | dump.cs 776863 |
| `UnitState.skinType` offset | 0x20 | dump.cs 776862 |
| `UnitState.style` offset | 0x1E (short) | dump.cs 776861 |
| `UnitState.health` offset | 0x48 (ushort) | dump.cs 776869 |
| `UnitState.owner` offset | 0x1C (byte) | dump.cs 776860 |
| `PlayerState.color` offset | 0xC0 (int, packed RGB) | dump.cs 776725 |
| Status-overlay color/strength constants | see §6 | UpdateObject 0x2DA0234–0x2DA0348 (IEEE-754 decoded) |

Overlay float immediates decoded (IEEE-754): `0x3E99999A`=0.3, `0x3F333333`=0.7,
`0x3DCCCCCD`=0.1, `0x3F666666`=0.9, `0x3ECCCCCD`=0.4, `0x3F4CCCCD`=0.8, plus literals 0.5 and 1.0.

## 3. Sprite selection

### 3a. Two unit families
- **Modular paper-doll units** (humanoids: Scout, Warrior, Rider, Knight, Defender, Archer,
  MindBender, Swordsman, Catapult, Giant, Shaman, Cloak, Dagger, Mermaid variants, Polytaur…):
  built from `body_* + head_* + weapon_* + bodytint_*` (+ accessory layers).
- **Whole-sprite units** (naval + tribe-special monsters): one `unit_<name>` (often with
  `_tint`/`_sail`/`_front` companion layers) or `<tribe>_<name>` sprite.

### 3b. Modular layer base names → confirmed catalog families
Bodies (`body_<base>`, base present, no `_Outline`): `body_default`, `body_rider`, `body_knight`,
`body_knighthorse`, `body_giant`, `body_priest`, `body_legs_priest`, `body_cloak`, `body_dagger`,
`body_mermaid`, `body_bunny`, `body_santa`. (All confirmed in catalog.)
Weapons (`weapon_<base>`): `weapon_sword`, `weapon_bow`, `weapon_club`, `weapon_dagger`,
`weapon_icebow`, `weapon_priest`, `weapon_tridention`. (All confirmed.)
Heads: `head` (generic base) and per-tribe `head_<tribe>` for all 16 playable tribes:
`head_imperius head_bardur head_xinxi head_oumaji head_kickoo head_hoodrick head_luxidoor
head_vengir head_zebasi head_aimo head_quetzali head_elyrion head_aquarion head_polaris
head_cymanti head_yadakk` (all confirmed). Neutral/villager uses `head_neutral`; special faces
`head_dead`, `head_robot` (SpriteData.SpecialFaceIcon, dump.cs 374233-374235).
Body tints (`bodytint_<base>`): `bodytint_default`, `bodytint_giant`, `bodytint_knight`,
`bodytint_rider`, `bodytint_cloak`, `bodytint_dagger`, `bodytint_mermaid` (confirmed —
mirror the body families). The bodytint is the layer that gets recolored with the player color.

### 3c. Skin/tribe suffix rule (DoSpriteLookup, 0x2B2F5B0)
Given a part base name `B`, tribe `T`, skin `S`, the lookup builds an ordered candidate list
(stored in `SpriteLookupResult` slots 0x20..0x40) and returns the **first that exists** in the atlas:
1. `B_<skinName>` (skin-specific, e.g. `body_default_ninja`)
2. `B_<tribeName>` (tribe-specific, e.g. `head_imperius`)
3. `B` (bare base, e.g. `body_default`)
(with `_Outline` companion looked up in parallel; level-suffixed variants resolved by
`TrySolveSpriteNameForLevelSprites` 0x2B2FCE0 when `levels` is set on the part.)
- `skinName`/`tribeName` are the **lowercased enum names** via `EnumExtensions.GetName` +
  `String.Concat`/`String.Format` (confirmed in `GetHeadSpriteAddress(TribeType)` 0x2D852BC →
  `0xC25100` tribe→string then concat; same `0xC25100` used inside DoSpriteLookup at 0x2B2F6C4).
- **Key empirical fact:** base tribes do NOT have body/weapon suffix sprites (e.g.
  `body_default_imperius` and `weapon_sword_bardur` do NOT exist), so for a normal tribe a unit's
  body/weapon falls through to the bare base (`body_default`,`weapon_sword`) and only the **head**
  carries the tribe (`head_imperius`). Skin suffixes (ninja/arty/mercenary/skeleton/baerion/ikarus/
  scholar/sfinx/urkaz/ranger/darkelf/magma/pirate/swamp + mermaid) DO exist on body/weapon/head.

### 3d. SkinType → suffix (enum name lowercased), dump.cs SkinType enum
`Default`(0)→none, `Ranger`(1)→`ranger`, `Ninja`(2)→`ninja`, `Baerion`(3)→`baerion`,
`Scholar`(5)→`scholar`, `Mercenary`(7)→`mercenary`, `Sfinx`(8)→`sfinx`, `Skeleton`(9)→`skeleton`,
`Arty`(10)→`arty`, `Pirate`(11)→`pirate`, `Aibo`(12)→`aibo`, `Urkaz`(13)→`urkaz`,
`Ikarus`(14)→`ikarus`, `DarkElf`(15)→`darkelf`, `Swamp`(17)→`swamp`, `Magma`(18)→`magma`.
(`None`=-1, `Default`=0 → no suffix.)

### 3e. UnitData.Type → part set (mapping; modular vs whole-sprite)
Confirmed by which catalog families exist. Modular humanoids and their parts (representative):
| UnitData.Type | body base | weapon base | extra layer |
|---|---|---|---|
| Warrior(2), Scout(1) | `body_default` | `weapon_sword` | — |
| Archer(9) | `body_default` | `weapon_bow` | `unit_quiver` |
| Defender(5) | `body_default` | (shield) | `unit_shield_defender`,`unit_shieldtint_defender` |
| Swordsman(11) | `body_default` | `weapon_sword` | — |
| Rider(3) | `body_rider` | `weapon_sword` | — |
| Knight(4) | `body_knight` + `body_knighthorse` | `weapon_sword` | — |
| Catapult(8) | — | — | whole: `unit_catapult_default` |
| MindBender(10)/Shaman(36) | `body_priest`/`body_legs_priest` | `weapon_priest` | — |
| Giant(12) | `body_giant` | `weapon_club` | `bodytint_giant` |
| Dagger(37) | `body_dagger` | `weapon_dagger` | `bodytint_dagger`, `unit_dagger_head` |
| Cloak(38) | `body_cloak` | (none) | `bodytint_cloak` |
| Cloak_Boat(39) | — | — | whole: `unit_cloak_boat`(+`_tint`) |
| Bunny(13) | `body_bunny` | — | — |
| Mermaid* (46–51) | `body_mermaid`/`body_priest_mermaid` | per-class weapon | `unit_shield_mermaiddefender` |
Whole-sprite (single `unit_<name>` + `_tint`/`_sail`): Ship(6)=`unit_ship`(+`_sail`),
Boat(14)=`unit_boat`, Battleship(7)=`unit_battleship`(+`_sail`), Scoutship(42)=`unit_scoutship`,
Bombership(41)=`unit_bombership`, Transportship(43)=`unit_transportship`, Rammership(44)=`unit_rammer`,
Juggernaut(45)=`unit_juggernaut`(+`_front`,`_tint_back`), Pirate(40)=`unit_pirate_ship`,
Aquapult(55)=`unit_aquapult_body`(+`_tint`).
Tribe-special / monster whole-sprites (often `<tribe>_<name>` or standalone, each with `_tint`):
Polytaur(15)=`polytaur_<tribe>`, FireDragon(19)=`elyrion_dragon`(+`_large`), Gaami(27)=`polaris_body_gaami`(+`polaris_bodytint_gaami`),
BattleSled(23)=`polaris_battlesled`(+`_weapon`,`_tint`), Crab(26)=`aquarion_crab`(+`_tint`),
Doomux(29)=`cymanti_doomux`(+`_tint`), Centipede(33)=`cymanti_centipede_head`/`_bottom`/`_connector`(+`_tint`),
Hexapod(28)=`hexapod`(+`_tint`), Raychi(35)=`raychi`, Phychi(30)=`phychi`, Kiton(31)=`kiton`,
Exida(32)=`exida`, Mantis(59)=`mantis`, Jelly(52)=`jelly`, Shark(53)=`shark`(+`sharktint`),
Shaman(36)=`shaman`. (All names above confirmed present in `sprite_catalog.json`.)
Note: `*_icon` variants are UI icons (unit menu), NOT the battlefield sprite — do not use for board render.

## 4. Geometry
- **World position:** unit anchored at the tile center `pos = ToPosition(coords)` =
  `(x',y')` with `posX=(x-y)*0.4811`, `posY=(x+y)*0.288` (RenderUnit calls 0x2CC11AC at 0x2CDD9B8
  with `coords` from `[unitState+0x10]`). Standard tile vertical offset `-0.223` applies to the row.
- **Layer stacking (within a unit):** all VisualParts share the unit's transform; they are stacked
  in prefab order (back→front): bodytint/body shadow → body → legs (riders) → head → weapon →
  accessories (quiver/shield). `head` is positioned by `Unit.headPositionMarker` (field 0x30) /
  `HeadPosition` (Unit get_HeadPosition 0x2DA54B4); `spriteContainer` (field 0x38) holds the body stack.
- **Pivot/anchor:** sprites use their own atlas pivots (bottom-center for feet placement). Exact
  per-part offsets live in the Unity prefab (not in dump.cs) — see Open Questions.
- **Facing / flip:** `Unit.set_Flipped(UnitState.flipped)` (0x2DA0BEC, called at 0x2DA04C8 with the
  byte at `unitState+0x54`). Flip negates the sprite-container X scale → equivalent to
  `Image.flipped_x()` of the whole composited unit. No separate left/right sprites.
- **Sub-depth in the tile sort order:** units are not one of the fixed 0–99 terrain sub-layers.
  They are `WorldObject`s with their own `Depth` (Unit get_Depth/set_Depth 0x2DA54A8/0x2DA54B0)
  set from the tile depth; effectively they render **above** all terrain/resource/improvement
  sub-layers of the same tile (after sub-layer 6 houses, around/above buildings), and are
  depth-sorted by row (`y*100`) like everything else so a unit on a lower row occludes units/tiles
  on higher rows. Use: draw units after improvements, depth = tile row depth + a unit bias.

## 5. Algorithm (implementer pseudocode)
```
render_unit(tile, unitState, gameState):
    if unitState is None: return
    if IsHidden(tile) or IsInvisibleForLocalPlayer(unitState): return   # 0x2CDA6D4 / 0x2DA54D4
    owner   = gameState.players[unitState.owner]
    tribe   = owner.tribe ; skin = unitState.skinType ; type = unitState.type
    level   = clamp(unitState.promotionLevel? , 0, 30)   # level used only for leveled parts
    teamColor = ColorFromInt(owner.color)                # (R,G,B)=bytes>>16,>>8,&0xff /255 ; A=1

    # --- choose sprite set ---
    if type in WHOLE_SPRITE_UNITS:
        layers = whole_sprite_layers(type, tribe, skin)  # unit_<name> (+ _tint/_sail/_front)
    else:
        parts = paperdoll_parts(type)                    # [bodytint, body, (legs), head, weapon, accessory]
        layers = []
        for p in parts:
            base = p.default_name                        # e.g. body_default / head / weapon_sword / bodytint_default
            skinLogic = p.skinLogic                      # UseTribe|UseClimate|UseBirthClimate|DontChangeSkin
            t,s = settings_for_logic(skinLogic, tribe, climate, birthClimate, skin)
            name = DoSpriteLookup(base, t, s, level)      # see §3c: try base_<skin>, base_<tribe>, base
            layers.append((p, name, p.tintable))

    # --- composite back-to-front ---
    img = blank
    for (p, name, tintable) in layers:
        spr = load(name + ".png")
        if tintable:                                     # bodytint / *_tint
            spr = multiply_tint(spr, teamColor)          # player team color
        # status overlay (see §6)
        if overlay_strength > 0:
            spr = lerp_rgb(spr, overlayColor, overlay_strength)
        img.paste(spr at part_offset)

    if unitState.flipped: img = img.flipped_x()
    place img at ToPosition(unitState.coordinates) with bottom-center anchor
    # outline color (selection/ownership) via SetOutlineColor (0x2DA16D4) — optional overlay
```
Key real calls in `Unit.UpdateObject(transient)` 0x2DA0000 (in order):
SkinUnit(0x2D9E010) → ColorizeUnit(0x2D9E864) → ShowOutline(0x2D9E23C) →
set_Flipped(0x2DA0BEC, arg=`flipped`@0x54) → UpdateHeadScale(0x2DA0D40).

## 6. Tint / color
- **Player team color (tintable parts only):** `ColorFromInt(PlayerState.color)`; packed
  `0x00RRGGBB`, each channel /255, A=1.0 (0x2CB175C). Applied to parts where `VisualPart.tintable==true`
  (offset 0x24) — i.e. `bodytint_*` / `*_tint` layers. ColorizeUnit (0x2D9E864) iterates parts and
  `fcsel`s between the team-color params and the overlay params based on `tintable`.
- **`ColorizeUnit(skin, overlayColor, overlayStrength, teamColorOverride, teamColorOverrideStrength)`**
  (dump.cs 375742). In UpdateObject the call passes: overlayColor RGB = (s8,s9,s10), alpha=1.0,
  overlayStrength = s11; teamColorOverride = (1,1,1) literals on stack; teamColorOverrideStrength = s12.
- **Status-effect overlay** (computed before the call, default = no overlay; `UnitState.HasEffect`
  0x7EEEB0, `UnitEffect` enum dump.cs 776841): the engine selects an overlay (color,strength) tuple
  per active effect. Decoded constant pools (IEEE-754) used:
  - `Boosted`(2): overlay≈(0.3,0.1,0.7?) strength 0.5 family (s-regs set at 0x2DA024C–0x2DA0280).
  - `Poisoned`(1): overlay greenish ≈(0.4,0.9,0.1) strength 0.5 (0x2DA0294–0x2DA02B0).
  - `Frozen`(0): overlay blue-white ≈(0.8,0.9,1.0) strength 0.4 (0x2DA02CC–0x2DA02F0).
  - `Petrified`(5): overlay grey ≈(0.1,0.1,0.1)/0.8 family (0x2DA030C–0x2DA0328).
  - default (no effect): strength 0 (movi d0/d1 = 0) → no tint.
  (Exact channel assignment per effect is the s8=R/s9=G/s10=B convention; the four constants
  0.3/0.4/0.7/0.8/0.9/0.1 are distributed via the fcsel chain — treat the per-effect RGB as
  approximate pending a live-pixel check; the *strengths* 0.4/0.5 and the "no effect ⇒ 0" rule are firm.)
- **Veteran / promotion:** there is no separate tint; veterans get a star/level overlay drawn by
  `UnitStatusDisplay` (Unit.UpdateStatusDisplay 0x2DA051C) and leveled body/head variants resolved
  via the `level` arg to DoSpriteLookup (parts with `VisualPart.levels==true`).
- **Health / status dots:** `Unit.UpdateStatusDisplay` (0x2DA051C) and `ShowStatusDisplayDot`
  draw the health bar / status indicator above the unit; this is a separate UI overlay, not part of
  the body composite.
- **Outline:** `Unit.SetOutlineColor` (0x2DA16D4) / `ShowOutline` (0x2D9E23C) draw the `_Outline`
  companion sprite of each part (selection highlight / faint ownership outline). Outline color comes
  from `Tile.GetOutlineColor` (0x2CDED40) in the RenderUnit path.

## 7. RVAs verified
- `Tile$$RenderUnit` 0x2CDD620 — thin orchestrator: GetGameState, UnitExtensions.GetInstance
  (0x2DA3468), Unit.CreateUnit (0x2D9FADC), SetupForUnit (0x2D9F2A4), ToPosition (0x2CC11AC),
  SetOutlineColor (0x2DA16D4), IsHidden (0x2CDA6D4), IsInvisibleForLocalPlayer (0x2DA54D4).
- `Unit$$CreateUnit` 0x2D9FADC — looks up unit prefab by `UnitData.Type` (PrefabManager, 0x2B1CA44),
  instantiates, attaches `SkinVisualsReference` (stored at unit+0xD8).
- `Unit$$UpdateObject(SkinVisualsTransientData)` 0x2DA0000 — calls SkinUnit→ColorizeUnit→ShowOutline
  →set_Flipped; computes status-effect overlay via HasEffect (0x7EEEB0) for effects 0,1,2,4,5,6.
- `SkinVisualsRenderer$$SkinUnit` 0x2D9E010 → `SkinWorldObject` 0x2D9DB84 — iterates `visualParts[]`,
  per part selects TribeAndSkin by `skinLogic`, level-clamps to 30, resolves sprite via DoSpriteLookup.
- `SpriteAtlasManager$$DoSpriteLookup` 0x2B2F5B0 — builds ordered candidate names (base_skin /
  base_tribe / base) into SpriteLookupResult, returns first present (HasSprite 0x2B30218 /
  HasOutline 0x2B30284); uses tribe/skin→lowercase-name via 0xC25100 + String.Format 0x2778390.
- `SpriteData$$GetHeadSpriteAddress(TribeType)` 0x2D852BC / `(SkinType)` 0x2D85388 — `head_` +
  lowercased enum name (EnumExtensions.GetName + Concat).
- `SkinVisualsRenderer$$ColorizeUnit` 0x2D9E864 — iterates parts, `tintable`(VisualPart+0x24) selects
  team-color vs overlay path.
- `ColorUtils$$ColorFromInt` 0x2CB175C — packed `0x00RRGGBB` → float RGBA, /255, A=1.
- `Unit$$set_Flipped` 0x2DA0BEC — X-flip from `UnitState.flipped` (offset 0x54).
- `UnitState$$HasEffect(UnitEffect)` 0x7EEEB0 — effect bit test against `effects` list (offset 0x60).

## 8. Open questions / risks
- **Per-part pixel offsets & pivots** (head marker position, weapon hand position, layer order
  within a unit) live in the Unity prefab assets, not in `dump.cs`/the dylib. The implementer must
  derive these from the extracted sprite alpha bounds + reference screenshots, or accept the
  bottom-center anchor approximation. The *layer set and names* here are firm; the *relative XY
  offsets* are not in the binary.
- **Exact status-overlay RGB per effect:** the strength values (0.4/0.5) and the "no effect ⇒
  strength 0" rule are confirmed; the precise R/G/B channel assignment per effect (Frozen/Poisoned/
  Boosted/Petrified) is reconstructed from the fcsel constant pool and should be validated against a
  live frozen/poisoned unit screenshot before trusting the exact hue.
- **skinLogic selection (UseTribe vs UseClimate vs UseBirthClimate)** per part is data on the prefab's
  VisualPart (`SkinningLogic` enum: UseTribe=0, UseClimate=1, UseBirthClimate=2, DontChangeSkin=3).
  Heads use UseTribe; terrain-blended parts may use climate. The chosen TribeAndSkin comes from
  `SetupForUnit` (0x2D9F2A4) which fills unitSettings/unitClimateSettings/birthClimateSettings — the
  exact climate→theme rule overlaps the terrain slice; cross-check there.
- **Whole-sprite layer companions** (`_tint`, `_sail`, `_front`, `_back`) stacking order for naval
  units (esp. Juggernaut's `_front`/`_tint_back`) needs visual confirmation; the `_tint` layer is the
  team-colored layer (analogous to bodytint).
- **Centipede / multi-segment units** (Centipede/Segment) use a connector + repeated body segments
  (`cymanti_centipede_head/_bottom/_connector`) driven by `SegmentConnector` (Unit field 0x40) —
  out of scope for a single-tile composite; flag as special-case.
