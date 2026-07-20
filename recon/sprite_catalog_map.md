# Slice: sprite_catalog_map — Asset mapping (enum → sprite-base-name)

## 1. Summary
This slice is the **lookup layer**: it does not draw anything itself, it maps simulation
enum values (`TerrainData.Type`, `ResourceData.Type`, `ImprovementData.Type`, `UnitData.Type`,
`TribeType`, `SkinType`) plus the per-tile `climate`/`_skin` context to concrete sprite *base
names*, then to actual files in `polytopia_extracted/sprites/`. All 2051 catalog sprites are
categorized into terrain / shoreline / resource / improvement / city (house/roof/wall/monument)
/ unit (body/head/weapon/tint/ship/special) / tentacle / shadow / border / road-route / fog /
overlay-fx / ui (see `recon/asset_map.json` → `categories`). The central naming function is
`SpriteAtlasManager.DoSpriteLookup(baseName, tribe, skin, checkForOutline, level)` (RVA
**0x2B2F5B0**): it concatenates `baseName` with a **theme suffix** derived from
`EnumExtensions.GetName(tribe/skin)` lowercased (e.g. `ground` + `imperius` → `ground_imperius`),
trying skin-suffix, then tribe-suffix, then bare base. The base-name constants are the
`SpriteData` string consts (dump.cs 374190–374235), confirmed against the three `*ToString`
helpers by disassembly.

## 2. Constants
All base-name string constants from `SpriteData` (static class, dump.cs **374187–374235**):

| Const | Value | Enum it serves |
|-------|-------|----------------|
| TILE_FIELD | `ground` | TerrainData.Type.Field(3) + None(0)/default |
| TILE_MOUNTAIN | `mountain` | Mountain(4) |
| TILE_FOREST | `Forest` | Forest(5) |
| TILE_WATER | `water` | Water(1) |
| TILE_OCEAN | `ocean` | Ocean(2) |
| TILE_ICE | `ice` | Ice(6) |
| TILE_WETLAND | `wetland` | Wetland(7) |
| TILE_UNKNOWN | `hidden` | fog-of-war / unexplored |
| RESOURCE_GAME | `animal` | Resource.Game(1) |
| RESOURCE_CROP | `ResourceGFX_crop` | Crop(2) |
| RESOURCE_FISH | `ResourceGFX_fish` | Fish(3) |
| RESOURCE_WHALE | `ResourceGFX_whale` | Whale(4) |
| RESOURCE_METAL | `ResourceGFX_metal` | Metal(5) |
| RESOURCE_FRUIT | `ResourceGFX_fruit` | Fruit(6) |
| RESOURCE_SPORES | `ResourceGFX_spores` | Spores(7) |
| RESOURCE_STARFISH | `ResourceGFX_starfish` | Starfish(8) |
| RESOURCE_AQUACROP | `ResourceGFX_aquacrop` | AquaCrop(9) |
| IMPROVEMENT_FARM | `Farm` | Farm(5) |
| IMPROVEMENT_MINE | `Mine` | Mine(21) |
| IMPROVEMENT_FORGE | `Forge_1` | Forge(22) |
| IMPROVEMENT_SAWMILL | `Sawmill_1` | Sawmill(13) |
| IMPROVEMENT_WINDMILL | `Windmill_1` | Windmill(6) |
| IMPROVEMENT_MARKET | `MarketIcon` | Market(50) — board art is `Market_base/roof/section/...` |
| IMPROVEMENT_PORT | `Port` | Port(8) |
| IMPROVEMENT_LUMBER_HUT | `Lumber Hut` (file `Lumber_Hut`) | LumberHut(12) |
| IMPROVEMENT_RUIN | `ruin` | Ruin(2) |
| IMPROVEMENT_CUSTOMS_HOUSE | `Customs House_1` (file `Customs_House_1`) | CustomsHouse(4) |
| IMPROVEMENT_SANCTUARY | `sanctuary_1` | Sanctuary(32) |
| IMPROVEMENT_TEMPLE | `Temple_1` | Temple(17) |
| IMPROVEMENT_WATER_TEMPLE | `Water Temple_1` (file `Water_Temple_1`) | WaterTemple(19) |
| IMPROVEMENT_MOUNTAIN_TEMPLE | `Mountain Temple_1` (file `Mountain_Temple_1`) | MountainTemple(20) |
| IMPROVEMENT_FOREST_TEMPLE | `Forest Temple_1` (file `Forest_Temple_1`) | ForestTemple(18) |
| IMPROVEMENT_ICE_TEMPLE | `Ice Temple_1` (file `Ice_Temple_1`) | IceTemple(35) |
| IMPROVEMENT_ROAD | `Road` | Road(3) — board art is `roads0000..0007` |
| IMPROVEMENT_ATOLL | `atoll` | Atoll(51) |
| IMPROVEMENT_ICE_PORT | `iceport` | (ice port) |
| IMPROVEMENT_ICE_BANK | `icebank_icon` | IceBank(34) — built art `ice_bank_base/segment/top` |
| IMPROVEMENT_AQUA_FARM | `Aqua Farm` (file `Aqua_Farm`) | Aquafarm(49) |
| UNIT_HEADS | `head` | unit head layer |
| HEAD_DEAD/ROBOT/NEUTRAL | `head_dead`/`head_robot`/`head_neutral` | SpecialFaceIcon |

Note: dump.cs uses display-name strings with spaces ("Customs House_1"); the **extracted PNG
files** use underscores ("Customs_House_1"). The catalog uses the underscore form. Implementers
must map space→underscore (the atlas slugifies names).

Category counts (all 2051 covered, `recon/asset_map.json` → `category_counts`):
terrain 71, shoreline 10, resource 121, improvement 135, city_house 181, city_roof 36,
city_wall 1, monument 148, unit_body 193, unit_head 70, unit_weapon 68, unit_tint 261,
unit_special 152, unit_ship 144, unit_misc 3, tentacle 29, shadow 4, border 2,
road_route 25, fog 0, overlay_fx 51, ui 346.

## 3. Sprite selection

### 3.1 Theme suffix (the core rule)
`DoSpriteLookup(base, tribe, skin)` (0x2B2F5B0) builds candidate names and picks the first that
exists in an atlas. From disassembly it uses `EnumExtensions.GetName<Int32Enum>(tribe)` /
`GetName(skin)` then `String.Concat`, lowercased, with `_` separators. Effective order:

1. `base + "_" + skinName` if `skin != None/Default` (e.g. `ground_magma`)
2. `base + "_" + tribeThemeName` (e.g. `ground_imperius`)
3. bare `base` (e.g. `ground`) — only exists for some bases.

**Tile terrain context**: `SkinVisualsTransientData.SetupForTile` (0x2D9F0DC) reads
`TileData.climate` (int @0x1C, a `TribeType` value) and `TileData._skin` (`SkinType` @0x20)
into `tileClimateSettings` (TribeAndSkin @0x28). `UIUtils.GetTerrainSprite` (0x2C8DB7C) loads
`ldp w21,w22,[x22,#0x28]` = (tribe=climate, skin) and passes them to `DoSpriteLookup`.

**TribeType → theme suffix** (lowercase enum name; confirmed `ground_<theme>` exists for all
except Nature):

| Value | Tribe | suffix | ground_ exists |
|------:|-------|--------|----------------|
| 1 | Nature | nature | **NO** (placeholder climate, resolves to a real tribe) |
| 2 | Aimo | aimo | yes |
| 3 | Aquarion | aquarion | yes |
| 4 | Bardur | bardur | yes |
| 5 | Elyrion | elyrion | yes |
| 6 | Hoodrick | hoodrick | yes |
| 7 | Imperius | imperius | yes |
| 8 | Kickoo | kickoo | yes |
| 9 | Luxidoor | luxidoor | yes |
| 10 | Oumaji | oumaji | yes |
| 11 | Quetzali | quetzali | yes |
| 12 | Vengir | vengir | yes |
| 13 | Xinxi | xinxi | yes |
| 14 | Yadakk | yadakk | yes |
| 15 | Zebasi | zebasi | yes |
| 16 | Polaris | polaris | yes |
| 17 | Cymanti | cymanti | yes |

**SkinType → theme suffix** (SkinType enum dump.cs 878915; only those with art are used as
terrain/building suffix): Default(0)=none, DarkElf(15)=`darkelf`, Swamp(17)=`swamp`,
Magma(18)=`magma`, Aibo(12)=`aibo`, Arty(10)=`arty`, Mercenary(7)=`mercenary`. Unit-only skins:
Ranger(1)=`ranger`, Ninja(2)=`ninja`, Baerion(3)=`baerion`, Scholar(5)=`scholar`, Sfinx(8)=`sfinx`,
Skeleton(9)=`skeleton`, Pirate(11)=`pirate`, Urkaz(13)=`urkaz`, Ikarus(14)=`ikarus`. The non-tribe
themes `aimo` and `mercenary` appear in both lists — `aimo` is a real climate theme too.

### 3.2 Terrain (`TerrainData.Type`, dump.cs 784062)
Base from §2; final name = `base_<theme>`. Confirmed examples (exist in catalog):
`ground_imperius`, `mountain_bardur`, `Forest_kickoo`, `ice_magma`, `wetland_swamp`,
`water`, `ocean`, `hidden`. **`mountain` and `Forest` have NO bare sprite** — a theme suffix is
mandatory. Mangrove(8) returns `ground` from `TerrainToString` (default branch) but is rendered
as a wetland/forest feature in practice (open question, see §8).

### 3.3 Resources (`ResourceData.Type`, dump.cs 783747)
`UIUtils.GetResourceSprite` (0x2C8DC68) → `DoSpriteLookup(ResourceToString(r), tribe, skin)`.
`ResourceGFX_fruit` and `animal` (Game) are **themed per tribe** (e.g. `ResourceGFX_fruit_imperius`,
`animal_bardur`); crop/fish/whale/metal/spores/starfish/aquacrop are mostly single-theme with a
`_Outline` companion and occasional `_magma`. Confirmed: `ResourceGFX_crop`, `ResourceGFX_fish`,
`ResourceGFX_whale`, `ResourceGFX_metal`, `ResourceGFX_spores`, `ResourceGFX_starfish`,
`ResourceGFX_aquacrop`, `ResourceGFX_fruit_imperius`, `animal_imperius`. Every resource sprite has
a matching `<name>_Outline` used for the outline sub-layer (sort offset 4).

### 3.4 Improvements (`ImprovementData.Type`, dump.cs 783585)
`UIUtils.GetImprovementSprite` (0x2C8DCC8 / 0x2C8DDA0) → `DoSpriteLookup(ImprovementToString(i),
tribe, skin, level)`. Many improvements have a `level` argument selecting `_1.._8` variants
(Forge_1..8, Sawmill_1..8, Windmill_0..6, Temple_1..5, Customs_House_1..5, Forest_Temple_1..5).
City(1) is **NOT** a single sprite — handled by `CityRenderer.RefreshCity` (0x2CCC13C) building
`House_<level>_<theme>` + `roof_<theme>` + `CityWallGFX` + `Monument<N>_<theme>` stacks.
Confirmed: `Farm`, `Mine`, `Forge_1`, `Sawmill_1`, `Windmill_1`, `Port`, `Lumber_Hut`, `ruin`,
`Customs_House_1`, `sanctuary_1`, `Temple_1`, `Water_Temple_1`, `Mountain_Temple_1`,
`Forest_Temple_1`, `Ice_Temple_1`, `atoll`, `icebank_icon`, `ice_bank_base`, `Aqua_Farm`,
`bridge`, `Market_base`.

### 3.5 Cities (`ImprovementState` with type City)
- Houses: `House_<level>_<theme>`, levels {1,2,3,4,5,6,7,9}, all 30 themes (tribes + skins). e.g. `House_1_imperius`.
- Roofs: `roof_<theme>` (+`_Outline`), 18 themes. e.g. `roof_imperius`.
- Wall: single `CityWallGFX` (tinted by player color).
- Monuments: `Monument<1..7>_<theme>` (the 7 reward monuments = ImprovementData Monument1..7 = 23..29). e.g. `Monument4_imperius`.

### 3.6 Units (`UnitData.Type`, dump.cs 784325)
Modular layered model (`SkinVisualsRenderer.SkinUnit`): per unit, composited bottom-up:
- `bodytint_<class>[_<skin>][_Outline]` — player-color-tinted base layer.
- `body_<class>[_<skin>][_Outline]` — body silhouette. Body classes: default, bunny, cloak,
  dagger, giant, knight, knighthorse, legs_priest, priest, rider, santa.
- `head[_<tribe|special>][_Outline]` — **head is tribe-colored** (head_imperius, head_bardur, …,
  + specials head_dead/head_neutral/head_robot).
- `weapon_<class>[_<skin>][_Outline]` — weapon classes: bow, club, dagger, icebow, priest,
  priest_druid, sword, tridention.
Confirmed: `body_default`, `bodytint_default`, `head_imperius`, `weapon_sword`, `head_dead`.
**Ships / compound units**: `unit_<class>` (unit_ship, unit_boat, unit_battleship, unit_bombership,
unit_scoutship, unit_transportship, unit_rammer, unit_pirate_ship, unit_cloak_boat, unit_juggernaut,
unit_catapult_default, unit_aquapult_body, unit_quiver, unit_shield_defender), with `_tint` and
`_<skin>` and `_Outline` variants; some have extra parts (`_sail`, `_front`, `_back`).
**Special single-art units** (tribe/creature): `polytaur_<tribe>`, `elyrion_dragon[_large][_darkelf]`,
`elyrion_egg`, `elyrion_seamonster`, `cymanti_centipede_*`, `cymanti_doomux`, `polaris_battlesled`,
`polaris_fortress`, `polaris_icemaker`, `polaris_body_gaami`, `aquarion_crab`, `jelly`, `shark`,
`exida`, `kiton`, `mantis`, `moth`, `phychi`, `raychi`, `shaman`, `hexapod`, `boomchi`, `ciru`,
`island`, `demon`, `wolf`, `bugEgg`. (Full per-class body mapping is the RenderUnit slice's job;
this slice supplies the catalog grouping in `recon/asset_map.json` → `units` + `categories`.)

### 3.7 Borders / roads / fog
- Territory borders: only `BorderXGFX` and `BorderYGFX` are board art (the two isometric edge
  sprites, mirrored/flipped for N/E/S/W by `BorderContainer`, tinted by player color). **All
  `Border_*`/`NoBorder_*` are controller-button glyphs → UI, not territory borders.**
- Roads: `roads0000..roads0007` (8 connectivity-bitmask variants). Routes (water roads):
  `routes0000..routes0007` (+`_magma`). `Road` const maps to this family.
- Fog: no dedicated fog sprite; unexplored tiles draw the `hidden` terrain sprite (TILE_UNKNOWN).

## 4. Geometry
Not applicable as a draw layer — this slice produces *names only*. Sub-depth assignment is owned
by the per-layer slices (terrain=1, transport/road=2, terrain-features=3, resource-outline=4,
resource=5, houses=6, walls=97, buildings=98, borders back/front=0/99; see Part E.3). The one
geometric fact this slice fixes: **outline sprites** (`*_Outline`) are a separate paste drawn one
sub-layer *behind* their main sprite (resource outline at offset 4, resource at 5), at the same
pixel position. Bridges have a `-flipped` variant for orientation; ships have `_sail`/`_front`/
`_back` parts that paste at sprite-defined pivots (geometry per RenderUnit slice).

## 5. Algorithm
```
def sprite_name(base, tribe, skin, level=-1):
    cands = []
    if skin not in (None, Default) and skin_theme[skin]:
        s = skin_theme[skin]
        cands += [f"{base}_{s}_{level}" if level>=0 else None, f"{base}_{s}"]
    t = tribe_theme[tribe]              # lowercase enum name
    cands += [f"{base}_{t}_{level}" if level>=0 else None, f"{base}_{t}"]
    cands += [f"{base}_{level}" if level>=0 else None, base]
    for c in cands:
        if c and c in CATALOG: return c
    return base                          # final fallback (may not exist for mountain/Forest)

def terrain_sprite(tile):       # tile.terrain, tile.climate(int TribeType), tile._skin
    base = TERRAIN_BASE[tile.terrain]            # §2 table
    return sprite_name(base, tile.climate, tile._skin)

def resource_sprite(tile, owner_tribe, owner_skin):
    base = RESOURCE_BASE[tile.resource.type]
    return sprite_name(base, owner_tribe, owner_skin)   # fruit/animal themed; others usually bare

def improvement_sprite(imp, tribe, skin):
    if imp.type == City: return None        # CityRenderer handles it
    base = IMPROVEMENT_BASE[imp.type]
    return sprite_name(base, tribe, skin, level=imp.level)
```
Lookups are case-sensitive on the base token (`Forest`, `ResourceGFX_fruit`, `MarketIcon`) and
lowercase on the theme suffix. Confirm against catalog before use; prefer the most-specific
existing candidate.

## 6. Tint / color
- **bodytint_* / *tint*** layers are the only sprites multiplied by the **player color** (the
  body/head/weapon over them are drawn untinted). `PolytopiaSpriteRenderer.set_Color` (called from
  Tile.Render) applies the tint.
- **Borders** (`BorderXGFX/YGFX`) are tinted by the owning player's color via
  `BorderContainer.SetColor` (0x2CD68BC).
- **`CityWallGFX`** is tinted by player color.
- **`*_Outline`** sprites are pre-rendered white/dark outline silhouettes; they are not tinted,
  they are pasted behind the main sprite for the selection/contrast outline.
- Terrain/resource/building base art is **not** player-tinted — variation comes entirely from the
  theme suffix (tribe/skin/climate), not a runtime color multiply.
(Exact tint formula / palette is owned by the unit and border slices.)

## 7. RVAs verified (by disassembly with tools/re_tools.py)
- `SpriteData.TerrainToString` **0x2D84A80** — jump table `terrain-1`, range 0..6 (Water..Wetland);
  None(0)/Mangrove(8)/OOR → default `ground`. Confirms terrain base table.
- `SpriteData.ResourceToString` **0x2D84B44** — jump table `resource-1`, range 0..8 (Game..AquaCrop);
  else default. Confirms resource base table.
- `SpriteData.ImprovementToString` **0x2D84C20** — jump table `improvement-2`, range 0..0x34
  (Ruin(2)..LandFill(54)); None/City/OOR → default `placeholder`. Confirms improvement base table
  and that City is excluded.
- `UIUtils.GetTerrainSprite` **0x2C8DB7C** — `ldp w21,w22,[x22,#0x28]` reads tileClimateSettings
  (tribe,skin); calls TerrainToString then DoSpriteLookup. Confirms climate(int)+skin drive theme.
- `SpriteAtlasManager.DoSpriteLookup` **0x2B2F5B0** — callees `EnumExtensions.GetName<Int32Enum>`
  (x2) + `String.Concat` (x9): suffix = lowercased tribe/skin enum name. Confirms naming scheme.
- `SkinVisualsTransientData.SetupForTile` **0x2D9F0DC** — reads `[x8,#0x1c]` (TileData.climate) into
  the tile settings. Confirms climate field offset/role.
- `BorderContainer` **0x2CD653C/0x2CD68BC** — 4 directional renderers + SetColor (player tint).
- Enum tables read directly from dump.cs: TerrainData.Type 784062, ResourceData.Type 783747,
  ImprovementData.Type 783585, UnitData.Type 784325, TribeType 878951, SkinType 878915.

## 8. Open questions / risks
- **Mangrove(8)**: `TerrainToString` returns `ground`, but mangrove tiles visibly use wetland/forest
  art. The real renderer likely composites a mangrove *feature* (forestRenderer/algaeRenderer) over
  a water/wetland base rather than a single `mountain`-style themed sprite. Verify in RenderTerrain.
- **Nature climate (TribeType 1)**: no `ground_nature`/`mountain_nature`/`Forest_nature` art exists.
  Tiles' `climate` int is presumably always a concrete tribe (2–17) at map-gen; confirm no tile ever
  carries climate=1 at render time, or determine the default-tribe fallback DoSpriteLookup uses.
- **Per-class unit body mapping** (UnitData.Type → body/weapon class strings, e.g. Warrior→default,
  Knight→knight+knighthorse, Catapult→unit_catapult_default): inferred from naming, not yet read
  from `PrefabManager`/`SkinVisualsRenderer.SkinUnit`. Owned by the RenderUnit slice; this slice
  only groups the catalog.
- **level argument**: which improvements pass a non-default `level` and how it indexes `_1.._8`
  (Forge/Sawmill levels vs purely decorative variants) is from `TrySolveSpriteNameForLevelSprites`
  (0x2B2FCE0) — not fully reversed.
- **Numbered sprites** `0_1, 1_1 … 4_17_tint` (large 250–316 px) are tribe/monument illustration or
  end-screen art, not board tiles; classified `ui`. Confirm none are referenced by board rendering.
- The dump uses **spaced** display strings ("Customs House_1") while files use **underscores**
  ("Customs_House_1"); the atlas slugifier mapping is assumed space→underscore. Verify if any base
  has a different slug.
