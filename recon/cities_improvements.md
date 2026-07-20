# Slice: cities_improvements — Improvements + procedural Cities

## 1. Summary

`Tile.RenderImprovement` (0x2CDCF60) does **not** pick sprites itself — it only
instantiates/positions a `Building` or `City` prefab (PrefabManager) on the tile and
forwards to `WorldObject.UpdateObject`. Two distinct paths exist:

* **Simple improvements** (Farm, Mine, Forge, Temple, Port, Ruin, …): a single sprite,
  chosen by `UIUtils.GetImprovementSprite` → `SpriteData.ImprovementToString(type)` (a jump
  table mapping `ImprovementData.Type` → a base name string) → `SpriteAtlasManager.DoSpriteLookup(baseName, tribe, skin, level)`.
  `DoSpriteLookup` appends a tribe/skin **theme** suffix and an optional level number, then
  resolves the final atlas sprite (e.g. `Farm`, `Mine_magma`, `Forge_1`).
* **Cities** (`ImprovementData.Type.City`): built procedurally by `CityRenderer.RefreshCity`
  (0x2CCC13C). The city level decides a plot count {4, 9, 16}; plots are laid out on an
  isometric **diamond grid** of side `round(sqrt(count))`; `level` houses are dropped onto
  pseudo-randomly walked plots (`House_{n}_{theme}` + `roof_{theme}`), plus an optional
  workshop (`House_Workshop`), parks (`House_Park`), a capital marker house, an enemy wall
  (`CityWallGFX` / `ocean_wall_*`), embassies (`embassy`/`embassy_cymanti`), and city resources.
  Monument_* are **separate non-city improvements** (types 23–29), rendered through the simple
  path, not by RefreshCity.

All sprite names below are confirmed present in `pyrender/sprite_catalog.json`.

---

## 2. Constants

### Improvement → base-name jump table (`SpriteData.ImprovementToString`, RVA 0x2D84C20)
ARM64 confirms: `idx = type - 2`; if `idx <= 0x34` (i.e. type in 2..54) index a 53-entry
pointer table at VA 0x4501210; else return default `"placeholder"`. Strings are the
`SpriteData` IMPROVEMENT_* constants (dump.cs 374207–374231). Mapping (enum dump.cs 783585):

| `ImprovementData.Type` | base name (string literal) |
|---|---|
| Ruin=2 | `ruin` |
| Road=3 | `Road` |
| CustomsHouse=4 | `Customs House_1` |
| Farm=5 | `Farm` |
| Windmill=6 | `Windmill_1` |
| Fishing=7 | (fish/port-class; see open Q) |
| Port=8 | `Port` |
| Hunting=9 | `animal`/none (resource-only) |
| LumberHut=12 | `Lumber Hut` |
| Sawmill=13 | `Sawmill_1` |
| Temple=17 | `Temple_1` |
| ForestTemple=18 | `Forest Temple_1` |
| WaterTemple=19 | `Water Temple_1` |
| MountainTemple=20 | `Mountain Temple_1` |
| Mine=21 | `Mine` |
| Forge=22 | `Forge_1` |
| Monument1..7=23..29 | `Monument` (→ `Monument{1..7}`; see §3) |
| Sanctuary=32 | `sanctuary_1` |
| IceBank=34 | `icebank_icon` |
| IceTemple=35 | `Ice Temple_1` |
| Market=50 | `MarketIcon` |
| Atoll=51 | `atoll` |
| Aquafarm=49 | `Aqua Farm` |

Spaces in literals become `_` in atlas filenames (`Customs House_1`→`Customs_House_1`,
`Lumber Hut`→`Lumber_Hut`, `Water Temple_1`→`Water_Temple_1`).

### CityRenderer fields / statics (dump.cs 417058)
* `m_level` @0x5C, `m_isCapitalOf` (byte) @0x60, `m_haveWall` (byte) @0x61,
  `m_haveWorkshop` (byte) @0x62, `m_parkCount` (int) @0x64, `playerEmbassies` @0x68,
  `m_tribe` @0x58, `SkinType` @0x2C, `sortOrder` @0x40.
* `HOUSE_WORKSHOP` @0x20, `HOUSE_CAPITAL` @0x24, `HOUSE_PARK` @0x28 (house "type" ints,
  set from the improvement data; workshop/park branch to the literal sprites below).
* Statics `PIXELS_PER_UNIT`, `SCALE`, `BASE_SIZE` (Vector2) — used for scale/positioning.

### Plot-count / grid (RefreshCity 0x2CCC13C, decoded)
* `count = (level <= 1) ? 4 : (level < 5) ? 9 : 16`  (CSEL at 0x2CCC408–0x2CCC428).
  - `level <= 0` is clamped to `level = 1`, `dataChanged = true`.
* `side = round(sqrt(count))` → 2, 3, or 4 (fsqrt + banker's-round at 0x2CCC42C–0x2CCC514).
* `cell = pixelsPerUnit * 50.0` (0x42480000 = **50.0**); diamond spans `2*side` rows.
* House jitter base step `r * 1.5` (0x3FC00000 = **1.5**) in `GetNextRandomPlot`.

### Decoded float immediates in the layout
| hex | value | role |
|---|---|---|
| 0x42480000 | 50.0 | base cell size multiplier (`cell = ppu*50`) |
| 0x3FC00000 | 1.5 | plot-walk step (`ceil(rng*1.5)` = +1 or +2) |
| 0x3E99999A | 0.30 | house x/feather factor |
| 0xBE75C28F | -0.24 | house y offset |
| 0x3D99999A | 0.075 | capital-marker x slope |
| 0x3E19999A | 0.15 | capital-marker x base |
| 0x3CA3D70A | 0.02 | capital-marker x trim |
| 0xBD99999A | -0.075 | capital-marker slope (neg) |

### Sub-depth (matches Part E.3)
* Houses/plots → row-depth offset **6**.
* Wall sorting order = `sortOrder + 0x61` = **+97** (0x2CCD268 `add w1,w8,#0x61`) → "Walls" layer.
* Buildings (simple improvements) → offset **98**.

---

## 3. Sprite selection

Final filename is produced by `SpriteAtlasManager.DoSpriteLookup(baseName, tribe, skin, checkForOutline=true, level=-1)`
(dump.cs 387659, RVA 0x2B2F5B0). Empirically (confirmed against catalog) it resolves:
1. `"{baseName}_{theme}"` if that sprite exists, else
2. `"{baseName}"` (no theme), and
3. appends `"_{level}"` when a level/count is supplied and a leveled variant exists.

**theme** = lowercase enum name of the **skin** if a non-Default skin is set, otherwise the
lowercase **tribe** name. From the enums (dump.cs 878915 SkinType, 878951 TribeType):
tribes → `imperius, bardur, kickoo, luxidoor, oumaji, quetzali, vengir, xinxi, yadakk, zebasi,
polaris, cymanti, hoodrick, elyrion, aquarion, aimo`; skins → `magma, swamp, darkelf(darkelf),
arty, pirate, ninja, sfinx, skeleton, scholar, ranger, baerion, aibo, urkaz, ikarus, mercenary`.

### Simple improvements (one sprite)
Use `ImprovementToString(type)` base, then theme/level. Confirmed catalog names:
* `Farm` (and skin `Farm_arty`), `Mine` (skin `Mine_magma`), `Port`, `ruin`, `atoll`,
  `iceport`, `icebank_icon`, `MarketIcon`, `Lumber_Hut`, `Sanctuary`→`sanctuary_1`.
* **Leveled** improvements take a level number: `Forge_1..Forge_8`, `Sawmill_1..Sawmill_8`,
  `Windmill_0..Windmill_6`, `Customs_House_1..Customs_House_5`, `Temple_1..Temple_5`,
  `Forest_Temple_1..5`, `Water_Temple_1..5`, `Mountain_Temple_1..5`, `Ice_Temple_1..6`
  (Ice has `_magma` skin variants). The `_1` in the SpriteData constant is the base/level-1.
* **Monuments** (types 23–29): base `Monument{1..7}`, themed → `Monument{N}_{theme}`, e.g.
  `Monument1_imperius`, `Monument7_bardur`. (Confirmed N=1..7, themes = tribe+skin set.)

### City houses (`CityRenderer.GetHouse`, RVA 0x2CCE218)
* If `type == HOUSE_WORKSHOP (0x20)` → base `House_Workshop` (literal, no theme).
* If `type == HOUSE_PARK (0x28)` → base `House_Park` (literal).
* Otherwise → `string.Format("House_{0}", type)` → `House_{n}` → `DoSpriteLookup` →
  **`House_{n}_{theme}`**. Confirmed: n ∈ {1,2,3,4,5,6,7,9} (no 8), themes per tribe/skin,
  e.g. `House_1_imperius`, `House_2_bardur`, `House_3_kickoo`, `House_5_luxidoor`,
  `House_9_bardur` (rare). Format literal `House_{0}_{1}` exists in stringliterals.
* Each house also gets a **roof** overlay (the `_Outline`/roof art): `roof_{theme}` and
  `roof_{theme}_Outline`, e.g. `roof_imperius`, `roof_bardur`, `roof_imperius_Outline`.
  (Roofs only exist for a subset of themes; fall back to no roof if absent.)

### City wall (`CityRenderer.GetResource`, RVA 0x2CCE8B8, called from RefreshCity 0x2CCD16C)
* base name literal at VA 0x4903CF0 → land wall **`CityWallGFX`** (themed via DoSpriteLookup).
* Water cities use the `water_wall_left`/`water_wall_right`(+`_wall_right` combo) or
  `ocean_wall_left`/`ocean_wall_right` set (selected by tile water/ocean — see RenderImprovement
  `TileData.get_IsWater`). Wall is shown only when `m_haveWall` (enemy/captured cities).

### Embassies (`CityRenderer.GetEmbassy`, RVA 0x2CCE56C)
* `embassy` (or `embassy_cymanti` for Cymanti tribe). One per entry in `playerEmbassies`.

### Capital marker
No dedicated "capital" sprite tile in the board atlas; the capital is rendered as a special
**house** via `HOUSE_CAPITAL` (field @0x24) placed when `m_isCapitalOf != 0`
(RefreshCity 0x2CCD0C8 branch). `UI_capitalvision` is a UI-only icon, **not** the board marker.

---

## 4. Geometry

* `RenderImprovement` positions the building/city prefab at the tile's world position
  (`MapExtensions.ToPosition`, already in Part E.4) using `Transform.localPosition`; pivot is
  the tile center. Simple improvement sprites are bottom-center-anchored over the tile.
* **City diamond plot grid** (RefreshCity): plots are generated by iterating a diamond of
  `2*side` rows (loop 0x2CCC798–0x2CCCAD0). Within the loop the running x is
  `x_world = cell * i` (`cell = ppu*50`) and successive plots step by `cell/side` halved
  (`s12 = (cell/side)*0.5`), recentering each row so the diamond is symmetric about the tile.
  Each `CityPlot` stores `floors`, `sortingOrder`, and a list of house renderers.
* House placement inside a plot stacks vertically by `floors`; each added house bumps
  `sortingOrder` (so taller buildings draw in front). House local offset uses factors
  0.30 (x feather) and -0.24 (y) decoded above.
* Capital marker x-offset uses the affine `((side-2) * -0.075 + 0.15) + 0.02` (0x2CCCC5C).
* **Sub-depth**: plots/houses → +6 on the tile row depth; walls → +97; simple buildings → +98.
  This places houses behind walls behind front borders, consistent with Part E.3.
* No horizontal flip is applied to city houses (no `flipped_x` in the path). Simple
  improvements are not flipped either.

---

## 5. Algorithm (implementer pseudocode)

```
render_improvement(tile, improvement_state, tribe, skin):
    t = improvement_state.type
    if t == City:
        refresh_city(tile, improvement_state, tribe, skin)
        return
    # simple improvement
    base = IMPROVEMENT_TO_STRING[t]              # §2 table; spaces -> '_'
    level = improvement_state.level              # leveled families only
    name = do_sprite_lookup(base, tribe, skin, level)
    place_sprite(name, tile.world_pos, sub_depth=98, anchor=bottom_center)

do_sprite_lookup(base, tribe, skin, level=-1):
    theme = lower(skin.name) if skin not in (None,Default) else lower(tribe.name)
    for cand in ([f"{base}_{theme}_{level}"] if level>=0 else []) \
              + ([f"{base}_{level}"]        if level>=0 else []) \
              + [f"{base}_{theme}", base]:
        if cand in catalog: return cand
    return base   # last-resort

refresh_city(tile, st, tribe, skin):
    level = max(1, st.level)
    count = 4 if level<=1 else (9 if level<5 else 16)
    side  = round(sqrt(count))                   # 2,3,4 (banker's rounding)
    cell  = PIXELS_PER_UNIT * 50.0
    plots = build_diamond_plots(tile.world_pos, side, cell)  # 2*side rows, symmetric

    # 1) houses: one per city level, on pseudo-random walked plots
    idx = 0
    for _ in range(level):
        plot = get_next_random_plot(plots, idx, count, rng)   # see below
        htype = pick_house_type(rng)                          # -> 1..7,9
        house = do_sprite_lookup(f"House_{htype}", tribe, skin)
        roof  = f"roof_{theme}" (+ _Outline) if present
        plot.add_house(house, roof, sub_depth=6)

    # 2) capital marker
    if st.is_capital_of != 0:
        plot = get_next_random_plot(...); plot.add_house(do_sprite_lookup("House_{HOUSE_CAPITAL}",...))

    # 3) workshop
    if st.has_reward(Workshop):     # ImprovementDataExtensions.HasReward
        plots[?].add_house("House_Workshop")          # literal, sub_depth 6
    # 4) parks
    for _ in range(st.reward_count(Park)):            # RewardCount
        plots[?].add_house("House_Park")
    # 5) embassies
    for owner in st.player_embassies:
        place("embassy_cymanti" if tribe==Cymanti else "embassy")
    # 6) wall (enemy/captured)
    if st.has_reward(CityWall):
        wall = "ocean_wall_*"/"water_wall_*" if tile.is_water else do_sprite_lookup("CityWallGFX",...)
        place(wall, sorting = sortOrder + 97)

get_next_random_plot(plots, idx_ref, size, rng):   # RVA 0x2CCE0DC
    step = ceil(rng.value() * 1.5)        # 1 or 2
    idx  = idx_ref + step
    if idx > size: idx = 1
    idx_ref = idx
    return plots[idx - 1]
```

`pick_house_type` uses `RandomGeneratorUtils.Range` over the city's seeded `rng` (field @0x90).
The exact type distribution per call is data-driven (house art set per tribe); for faithful
output you must replay the same seeded RNG sequence (see Open Questions).

---

## 6. Tint / color

* Improvement/house sprites are placed via `PolytopiaSpriteRenderer.set_Color` (seen in
  Tile.Render callees) — **no per-player tint** is applied to buildings/houses themselves;
  city houses/roofs are pre-colored per tribe theme (the theme suffix carries the palette).
* `roof_*_Outline` sprites are the white selection/outline overlays; drawn only when the
  city/building is highlighted (`checkForOutline=true` path in DoSpriteLookup populates the
  `_Outline` slot of the `SpriteLookupResult`). Default board render uses the non-outline sprite.
* Walls and embassies likewise use their atlas RGBA directly. `embassy-tint` exists as a
  separate tintable variant but the board path uses plain `embassy`.
* Opacity: buildings use full alpha; fog-of-war dimming is applied upstream in `Tile.Render`
  (not in this slice).

---

## 7. RVAs verified (by disassembly)

* **0x2CDCF60 `Tile.RenderImprovement`** — confirmed it does PrefabManager.HavePrefab/GetPrefab +
  Instantiate + get/set localPosition; calls `GameLogicData.GetTribeData`/`HasAbility`,
  `TileData.get_IsWater`, `IsBeingCaptured`; forwards to the Building/City vtable UpdateObject.
  No sprite-name logic here.
* **0x2C8DCC8 `UIUtils.GetImprovementSprite` (tribe,skin overload)** — builds a
  `SkinVisualsTransientData`, `SetupStatic`, then `SpriteData.ImprovementToString` →
  `SpriteAtlasManager.DoSpriteLookup`.
* **0x2C8DDA0 `UIUtils.GetImprovementSprite` (transientData overload)** — same, reuses passed
  transient data; `ImprovementToString` then `DoSpriteLookup`.
* **0x2D84C20 `SpriteData.ImprovementToString`** — jump table `type-2`, range ≤0x34, table @
  VA 0x4501210, default `placeholder`. Confirms the §2 enum→string mapping.
* **0x2CCC13C `CityRenderer.RefreshCity`** — confirmed: clamps level; `count = 4/9/16`;
  `side = round(sqrt(count))`; `cell = ppu*50`; diamond double-loop builds CityPlots;
  house/capital/workshop/park/embassy/wall sections; wall sortingOrder = sortOrder+97;
  ends with `UpdateSpriteRenderers`.
* **0x2CCE0DC `CityRenderer.GetNextRandomPlot`** — `step = ceil(rng*1.5)`, wrap to 1 when > size,
  returns `plots[idx-1]`.
* **0x2CCE218 `CityRenderer.GetHouse`** — WORKSHOP(0x20)→`House_Workshop`, PARK(0x28)→`House_Park`,
  else `string.Format("House_{0}",type)` → DoSpriteLookup (theme suffix).
* **0x2CCE8B8 `CityRenderer.GetResource`** — DoSpriteLookup(baseName,tribe,skin,count); used for the
  wall (`CityWallGFX`) and city resources.
* **0x2CCE56C `CityRenderer.GetEmbassy`** — embassy sprite per embassy owner.
* **0x2B2F5B0 `SpriteAtlasManager.DoSpriteLookup`** — concatenates baseName + theme + level and
  resolves atlas; fills 5-slot SpriteLookupResult incl. outline.
* **0x2CCB8A0 `City.UpdateCity`** — wires renderer fields: HaveWall/HaveWorkshop via
  `ImprovementDataExtensions.HasReward` (0x7EB660), ParkCount via `RewardCount` (0x7EB6EC),
  Level @0x5C, IsCapitalOf @0x60, Tribe via `GetVisualTribeType` (0x822F60), skin via
  `GetVisualSkin` (0x7ECB3C), embassies via `GetEmbassiesInCapitalOf` (0x8220EC).

---

## 8. Open questions / risks

1. **Exact RNG replay.** Houses, plot walk, and house-type picks all draw from the city's
   seeded `Random rng` (field @0x90, `RandomGeneratorUtils.Value`/`Range`). To match the real
   game's house arrangement pixel-for-pixel the implementer must reproduce that PRNG and its
   seeding (seed derived from city coordinates — `set_Coordinates` feeds it). I did not fully
   trace the seed derivation; if exact placement isn't required, any deterministic walk that
   honors `count`, `side`, and `level` count is visually plausible. **Risk: high for exactness.**
2. **`House_{n}` type set.** Catalog has n ∈ {1,2,3,4,5,6,7,9}; the per-tribe valid set and the
   `Range` bounds used by `pick_house_type` were not extracted from disassembly — confirm which
   indices a given tribe uses (some tribes lack `roof_*`, `House_6`, `House_9`).
3. **`cell`/`side` exact world-units.** `PIXELS_PER_UNIT`, `SCALE`, `BASE_SIZE` static values
   were not read from the cctor; the `*50` and `*0.5` factors are confirmed but absolute pixel
   sizes depend on those statics + `pixelsPerUnit` of the atlas sprite (read at runtime from
   `Texture` size at 0x2CCC52C). Treat the diamond spacing as proportional and calibrate against
   a reference screenshot.
4. **Fishing/Hunting/water improvements** map to resource-style art; `ImprovementToString` for
   types 7/9/etc. returns names that overlap the resource group — verify against the
   resources slice before drawing (they may be drawn by RenderResource, not RenderImprovement).
5. **Wall water variants.** Which of `water_wall_*` vs `ocean_wall_*` and the `_wall_right`
   combined sprite is chosen depends on shoreline/water-vs-ocean of the tile; exact selector
   not disassembled here (likely mirrors the shorelines slice). **Risk: medium.**
6. **Leveled-sprite level→index.** For Forge/Sawmill/Windmill/Temple the displayed numbered
   variant tracks city/building level, but the precise clamp (e.g. level→`min(level,maxLevel)`)
   should be read from `ImprovementData.maxLevel` rather than assumed.
