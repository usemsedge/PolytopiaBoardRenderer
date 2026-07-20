# Slice: resources — Resource layer (Tile.RenderResource / UIUtils.GetResourceSprite)

## 1. Summary
A tile draws at most one resource sprite, taken from `TileData.resource` (a `ResourceState`
whose only relevant field is `type : ResourceData.Type`, 1..9). The resource name is the base
string from `SpriteData.ResourceToString(type)` — `animal` for Game, `ResourceGFX_crop`,
`ResourceGFX_fish`, `ResourceGFX_whale`, `ResourceGFX_metal`, `ResourceGFX_fruit`,
`ResourceGFX_spores`, `ResourceGFX_starfish`, `ResourceGFX_aquacrop` for the rest. The base
string is then resolved through `SpriteAtlasManager.DoSpriteLookup(base, tribe, skin, checkForOutline=true)`,
which appends a **theme suffix** built from the *tile's climate* (climate→theme-tribe via
`GameLogicData.GetTribeTypeFromStyle`) and the tile's visual skin (e.g. `_imperius`, `_bardur`,
`_magma`, `_swamp`), falling back to the bare base name. Two of the nine families (`animal`,
`ResourceGFX_fruit`) exist in the atlas **only** as theme-suffixed sprites; the other seven exist
as bare sprites (plus optional `_magma` skin variants). The chosen sprite is drawn at the tile's
`visualCenter` (no extra local offset) with a paired `_Outline` sprite. Sub-depth: outline at
`y*100+4`, the resource at `y*100+5`. A per-resource desaturation flag (greying when the player
cannot yet harvest it) is applied via `TerrainMaterialHelper.SetSpriteSaturated`.

## 2. Constants
- **Resource sub-depth offsets** (RVA 0x2CD1484 `Resource$$set_Depth`):
  - resource sprite renderer order = `value + 5`  (`add w1,w19,#5` @0x2CD1598)
  - outline sprite renderer order = `value + 4`  (`add w1,w19,#4` @0x2CD1600)
  - where `value` passed in by `Tile.RenderResource` = tile row depth `y*100` (derived as
    `terrainRenderer.SortingOrder - 1` = `(y*100+1) - 1`; RVA 0x2CDCE70 `sub w1,w8,#1`).
  - => **resources = y*100 + 5, resource outline = y*100 + 4** (matches BRIEF sort table 4/5).
- **`ResourceData.Type` enum** (dump.cs ~783747): None=0, Game=1, Crop=2, Fish=3, Whale=4,
  Metal=5, Fruit=6, Spores=7, Starfish=8, AquaCrop=9.
- **ResourceToString jump table** at file-offset/VA `0x45011C8`, indexed by `type-1`
  (RVA 0x2D84B44; `sub w8,w1,#1; cmp w8,#8; b.hi default`). Out-of-range / None → `placeholder`
  (literal @0x49263B8).
- **DoSpriteLookup format-string literals** (RVA 0x2B2F5B0): `'_{0}'` @0x491C850, `'_{0}_'`
  @0x491C858, `'_'` @0x491AC60, `'_Outline'` @0x491BAB0.
- **Saturation predicate `ShouldChangeSaturation(type)`** (RVA 0x2CD0CB0):
  returns true for type ∈ {Game(1), Crop(2), Metal(5), Fruit(6), Spores(7), AquaCrop(9)};
  false for Fish(3), Whale(4), Starfish(8). (Decoded: `sub w8,r,#5; cmp r,#8; ccmn w8,#2,#2,ne;
  cset w0,lo`.)
- **Aquatic-resource bitmask `0x118`** (RVA 0x2CD0C30, bits 3,4,8 = Fish/Whale/Starfish): used by
  `Resource.UpdateObject` to skip the final saturation call for the three water resources.
- **TribeType enum** (dump.cs 878951): Nature=1, Aimo=2, Aquarion=3, Bardur=4, Elyrion=5,
  Hoodrick=6, Imperius=7, Kickoo=8, Luxidoor=9, Oumaji=10, Quetzali=11, Vengir=12, Xinxi=13,
  Yadakk=14, Zebasi=15, Polaris=16, Cymanti=17.
- **SkinType enum** (relevant terrain skins): Swamp=17, Magma=18, Default=0, None=-1.

## 3. Sprite selection
Inputs: `TileData.resource.type` (1..9), `TileData.climate` (int), the tile's visual skin.

Step A — base name `SpriteData.ResourceToString(type)` (exact, from jump table @0x45011C8):

| type | enum | base string returned |
|------|------|----------------------|
| 1 | Game     | `animal` |
| 2 | Crop     | `ResourceGFX_crop` |
| 3 | Fish     | `ResourceGFX_fish` |
| 4 | Whale    | `ResourceGFX_whale` |
| 5 | Metal    | `ResourceGFX_metal` |
| 6 | Fruit    | `ResourceGFX_fruit` |
| 7 | Spores   | `ResourceGFX_spores` |
| 8 | Starfish | `ResourceGFX_starfish` |
| 9 | AquaCrop | `ResourceGFX_aquacrop` |
| else/None | — | `placeholder` |

Step B — theme suffix via `DoSpriteLookup(base, tribe, skin)` where `tribe` = climate's theme
tribe (`GetTribeTypeFromStyle(climate)`), `skin` = tile visual skin. The lookup tries suffixed
candidate names — `base + "_" + lower(tribeName)` and, when a non-Default skin applies,
`base + "_" + lower(tribeName) + "_" + lower(skinName)` or `base + "_" + lower(skinName)` — and
**falls back to the bare `base`** if no suffixed sprite exists in the atlas. The selected sprite's
`_Outline` sibling is fetched the same way (`checkForOutline=true`).

Determinative rule confirmed against the catalog:
- `animal` and `ResourceGFX_fruit` have **NO bare sprite** → a theme tribe suffix is mandatory.
  All 16 playable tribes (enum 2..17, i.e. excluding Nature) have both `_<tribe>` and
  `_<tribe>_Outline`. Climate→tribe is the standard 1:1 Polytopia mapping (climate index = base
  tribe). Skin variants also exist (`ResourceGFX_fruit_magma`, `ResourceGFX_fruit_swamp`,
  `animal_magma`, `animal_aquarion_swamp`, plus per-skin like `animal_scholar`, `animal_skeleton`).
- `crop`, `fish`, `whale`, `metal`, `spores`, `starfish`, `aquacrop` exist as **bare** sprites and
  are normally drawn unsuffixed; `_magma` skin variants exist for some (`ResourceGFX_fish_magma`,
  `ResourceGFX_metal_magma`, `ResourceGFX_starfish_magma`) and win when the Magma skin is active.

Concrete example filenames (all verified present in `pyrender/sprite_catalog.json`):
- Game on Imperius-climate tile → `animal_imperius.png` (+ `animal_imperius_Outline.png`).
- Game on Bardur-climate tile → `animal_bardur.png` (+ `animal_bardur_Outline.png`).
- Fruit on Imperius-climate → `ResourceGFX_fruit_imperius.png` (+ `..._Outline.png`).
- Fruit on Bardur-climate → `ResourceGFX_fruit_bardur.png`.
- Fruit on a Magma-skin tile → `ResourceGFX_fruit_magma.png`.
- Crop → `ResourceGFX_crop.png` (+ `ResourceGFX_crop_Outline.png`).
- Fish → `ResourceGFX_fish.png`; Magma skin → `ResourceGFX_fish_magma.png`.
- Whale → `ResourceGFX_whale.png`. Metal → `ResourceGFX_metal.png`. Spores → `ResourceGFX_spores.png`.
- Starfish → `ResourceGFX_starfish.png`. AquaCrop → `ResourceGFX_aquacrop.png`.

(Confirmed missing, as expected: bare `ResourceGFX_fruit`, bare `animal` — do not exist.)

## 4. Geometry
- **Anchor / placement:** `Tile.RenderResource` (RVA 0x2CDCBB0) instantiates the `Resource` prefab
  (from `PrefabManager.GetPrefab(type)`), then sets the resource's `localPosition` equal to the
  tile's `visualCenter` transform localPosition (`get_localPosition`@0x2CDCEC8 →
  `set_localPosition`@0x2CDCED8). **No additional per-resource pixel offset is applied** in this
  code path — the resource sprite is centered on the tile's visual center. (Per-sprite art is
  pre-baked with its own pivot in the atlas; place sprite so its pivot lands at the tile's world
  position. Most resource sprites use a bottom-anchored pivot — treat the sprite's authored pivot
  as ground truth; see Open questions.)
- **Pivot:** the `PolytopiaSpriteRenderer` uses each sprite's own atlas pivot; resources are not
  re-pivoted by this layer.
- **Flip:** none — `RenderResource` performs no horizontal/vertical flip.
- **Depth / sort order within the tile stack:** outline renderer = `y*100 + 4`, main resource
  renderer = `y*100 + 5` (Section 2). This sits above terrain features (3) and below houses (6),
  exactly per the BRIEF sort table.

## 5. Algorithm
```
RenderResource(tile):                         # RVA 0x2CDCBB0 (worker); 0x2CDEC7C builds transient + tail-calls this
    tile.isDirty = true
    res_state = tile.data.resource            # TileData.resource @0x58
    if res_state == null or not HavePrefab(res_state.type):
        if tile.resource != null: tile.resource.Destroy()   # remove stale view
        return
    rtype = res_state.type                    # ResourceData.Type 1..9  (ResourceState.type @0x10)
    if tile.resource == null or wrong type:
        prefab = PrefabManager.GetPrefab(rtype)
        tile.resource = Instantiate(prefab, visualCenter)
    tile.resource.Data = GameState.GameLogicData.resources[rtype]   # SetData
    tile.resource.localPosition = tile.visualCenter.localPosition   # no extra offset
    base_depth = tile.terrainRenderer.SortingOrder - 1              # == y*100
    tile.resource.Depth = base_depth          # set_Depth -> outline=+4, sprite=+5
    tile.resource.UpdateObject(transientSkinData)   # picks + applies sprite/outline/saturation

UpdateObject(resource, transient):            # RVA 0x2CD08E0
    skinVis = resource.GetSkinVisualsReference()
    SkinVisualsRenderer.SkinTile(skinVis, transient, checkOutlines=resource.outlineEnabled, level=-1)
        # -> resolves base = ResourceToString(rtype)
        # -> DoSpriteLookup(base, tribe=GetTribeTypeFromStyle(tile.climate), skin=tile.visualSkin,
        #                   checkForOutline=true)  -> sprite + outline sprite, assigned to renderers
    # tech/visibility gating for saturation:
    isVisibleForPlayer = GameLogicData.IsResourceVisibleToPlayer(rtype, localPlayer, gameState)
    isTechUnlocked     = (GetActionableImprovementForResource(rtype, localPlayer) != null
                          && improvement.HasAbility(0x11))           # 0x11 = harvest-type ability
    if (1<<rtype) & 0x118 == 0:               # not Fish/Whale/Starfish
        SetSpriteSaturated(saturated = isTechUnlocked or not ShouldChangeSaturation(rtype))

ResourceToString(type):                       # RVA 0x2D84B44 — exact table in Section 3
SetupForTile(transient, gameState, tile):     # RVA 0x2D9F0DC
    tileClimateSettings.tribe = GetTribeTypeFromStyle(tile.data.climate)   # @0x84A184
    tileClimateSettings.skin  = Tile.GetVisualSkinTypeForTile(tile)        # @0x2CE0A28
GetResourceSprite(transient, rtype, atlas):   # UIUtils, RVA 0x2C8DC68 (UI-side equivalent)
    name = ResourceToString(rtype)
    s    = transient.tileClimateSettings       # field @0x28: tribe@0x28(low32), skin@0x2C(high32)
    return atlas.DoSpriteLookup(name, s.tribe, s.skin, checkForOutline=true, level=-1).Sprite
```

## 6. Tint / color
- **No per-player color tint** is applied to the resource sprite itself in this layer
  (resources are neutral terrain art; player color belongs to borders/units/cities).
- **Outline:** the resource view always carries an `_Outline` companion sprite (drawn at sub-depth
  `+4`, behind the resource at `+5`). Its color is set by `Tile.GetOutlineColor`
  (RVA 0x2CDED40) → `Resource.SetOutlineColor` (RVA 0x2CD0F00). For an idle (non-highlighted)
  resource this is effectively the default/clear outline; interaction highlight colors come from
  the input/overlay layer, out of scope here. Implementers can render the `_Outline` sprite
  untinted (white) for the static board.
- **Saturation (desaturation):** governed by `SetSpriteSaturated`
  (`TerrainMaterialHelper.SetSpriteSaturated`, RVA 0x2CE6B70). When the local player has NOT
  unlocked the tech to harvest a resource and `ShouldChangeSaturation(type)` is true
  (Game/Crop/Metal/Fruit/Spores/AquaCrop), the resource is drawn **desaturated/greyed**; otherwise
  full color. Fish/Whale/Starfish are never desaturated by this path (bitmask 0x118). The exact
  saturation factor/shader math is in the material shader and was not decoded (see risks). For a
  full-visibility ("all tech / spectator") render, draw all resources at full saturation.

## 7. RVAs verified
- `0x2C8DC68` `UIUtils$$GetResourceSprite` — loads `transient.tileClimateSettings` (@0x28), calls
  `ResourceToString` then `SpriteAtlasManager.DoSpriteLookup(name, tribe=low32, skin=high32,
  checkForOutline=1, level=-1)`; returns `result.Sprite` (`ldr x0,[x0,#0x10]`).
- `0x2D84B44` `SpriteData$$ResourceToString` — `type-1` jump table @0x45011C8 (9 entries),
  default `placeholder`. Pointer order decoded → exact name table in Section 3.
- `0x2CDCBB0` `Tile$$RenderResource` (worker) — null/HavePrefab guards, GetPrefab/Instantiate,
  SetData, set_Depth(base = terrainRenderer order − 1), localPosition = visualCenter, UpdateObject.
- `0x2CDEC7C` `Tile$$RenderResource()` — allocates+`SetupForTile`s a `SkinVisualsTransientData`,
  tail-calls the worker.
- `0x2CD08E0` `Resource$$UpdateObject(transient)` — calls `SkinTile` (0x2D9DF94),
  `IsResourceVisibleToPlayer`, `GetActionableImprovementForResource`+`HasAbility(0x11)`,
  `SetSpriteSaturated`; aquatic-skip mask 0x118.
- `0x2CD1484` `Resource$$set_Depth` — sprite order `value+5`, outline order `value+4`.
- `0x2CD0CB0` `Resource$$ShouldChangeSaturation` — true for {1,2,5,6,7,9}.
- `0x2B2F5B0` `SpriteAtlasManager$$DoSpriteLookup` — builds suffixed candidates with `_{0}`,
  `_{0}_`, `_`, `_Outline`; uses `EnumExtensions.GetName` for tribe/skin tokens; dictionary
  lookup with fallback to bare base.
- `0x2D9F0DC` `SkinVisualsTransientData$$SetupForTile` — sets `tileClimateSettings` =
  (`GetTribeTypeFromStyle(climate)`, `GetVisualSkinTypeForTile(tile)`).
- `0x84A184` `GameLogicData$$GetTribeTypeFromStyle` — reads JSON `climateTribeMap` (data-driven).
- Struct offsets confirmed in dump.cs: `TileData.resource`@0x58, `ResourceState.type`@0x10,
  `Tile.data`@0xB8 / `resource`@0xC8 / `visualCenter`@0x60 / `terrainRenderer`@0x20,
  `SkinVisualsTransientData.tileClimateSettings`@0x28, `TribeAndSkin{tribe@0x0,skin@0x4}`.

## 8. Open questions / risks
- **Exact DoSpriteLookup candidate priority.** Confirmed it tries tribe/skin-suffixed names then
  falls back to bare base, and confirmed which families need a suffix vs. which have a bare sprite
  (Section 3). The precise ordering when BOTH a tribe and a non-Default skin apply (e.g. prefer
  `base_<tribe>_<skin>` vs `base_<skin>` vs `base_<tribe>`) was not fully traced. For a default-skin
  board this is moot: use `base_<climateTribe>` for fruit/animal, bare `base` for the other seven.
- **Climate→tribe map is data-driven** (`climateTribeMap` JSON), not a binary switch. Assumed the
  standard Polytopia 1:1 climate→base-tribe mapping (climate N ↔ Nth base tribe). Verify against the
  loaded `GameLogicData` JSON if the map is available; risk is wrong theme art on a tile.
- **Token casing.** Atlas suffixes are lowercase (`_imperius`, `_magma`); `EnumExtensions.GetName`
  yields PascalCase enum names, so a `ToLower` happens in name assembly. Treat tribe/skin tokens as
  lowercased enum names (e.g. `DarkElf`→`darkelf`). DarkElf token = `darkelf` (sprite confirmed).
- **Sprite pivot / vertical seating.** This layer does not add an offset; it relies on each atlas
  sprite's authored pivot to seat the resource on the tile. The pivot per sprite is not in
  `sprite_catalog.json` (only w/h). Implementer must obtain pivots (UVs/pivot from the atlas/prefab)
  or empirically bottom-center the sprite over the tile world position. Flagged as the main
  pixel-accuracy risk for this layer.
- **Saturation shader factor** (`SetSpriteSaturated`) not decoded numerically; only the boolean
  gate is known. For a full-visibility render, treat all resources as full saturation.
- The `_magma` base-resource variants (fish/metal/starfish) imply the Magma terrain skin overrides
  even the "bare" families; ensure the skin check runs for all nine types, not just fruit/animal.
