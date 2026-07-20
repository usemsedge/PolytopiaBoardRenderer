# Slice: terrain — How a tile (base + toppers) is rendered

> **Verification status (2026-06-24):** the geometry, the constant values, the
> base/topper sort ordering, the desaturation tint, and the call structure below were
> **re-verified by direct disassembly** of the v116 arm64 slice
> (`GameAssembly_arm64.dylib`, build 2.15.1.15081) with `objdump` + ARM64 `BL`/immediate
> decoding — not just read from the IL2CPP dump. `dump.cs` only carries empty method
> bodies (`{ }`), so it proves *signatures, field offsets, and `const` values* but says
> nothing about ordering or usage; everything about *ordering* here comes from the binary.
> Items still resting on runtime data (not code) are called out in §8. All RVAs are
> v116-specific and drift on any game update.

## 1. Summary

One tile = one `Tile` MonoBehaviour with several child sprite renderers. The **base**
ground/water/ice surface is drawn by `TerrainRenderer.spriteRenderer`; the **"toppers"**
(the game's *terrain features* — mountain, forest, algae) are separate
`PolytopiaSpriteRenderer`s stacked on the same tile.

`MapRenderer.RenderMap` (0x2D4F6C0) instantiates one `Tile` per cell, positions it via
`MapExtensions.ToPosition`, sets `Tile.Depth = GetDepthForTile` (row-major, +100 per row),
then calls `Tile.Render` (0x2CDC5DC). `Tile.Render` calls `RenderTerrain` (0x2CDC828),
which: skins the tile, toggles the three feature renderers by terrain/effect, applies the
tint, then calls `TerrainRenderer.UpdateGraphics` (0x2CDBD9C) to set the base sprite, and
finally `RenderShorelines`.

Sprite names are built from `SpriteData.TerrainToString(terrain)` →
`"ground"/"water"/"ocean"/"ice"/"wetland"/"mountain"/"Forest"`, themed by
`SpriteAtlasManager.DoSpriteLookup(baseName, tribe, skin)` into `baseName_<theme>` (e.g.
`ground_imperius`, `mountain_bardur`, `Forest_kickoo`). A Forest/Mountain tile composites a
`ground_<theme>` **base** under a `Forest_<theme>` / `mountain_<theme>` **topper**.

**Crucial distinction: call order ≠ draw order.**
- *Call order* (the sequence `Tile.Render` invokes layers): terrain → resource →
  improvement → unit → border → transport → tentacle. This does **not** determine what
  paints on top.
- *Draw order* is set entirely by each renderer's `sortingOrder = Tile.Depth + layer_offset`,
  assigned in **`Tile.set_Depth`** (0x2CE1C84). The base gets `+1`, the toppers get `+3`,
  so toppers always paint over their own tile's base. Verified instruction-level in §4.

## 2. Constants (all `const` in `dump.cs` ~371964; values confirmed)

| Name | Value |
|------|-------|
| `TILE_WIDTH` / `TILE_HEIGHT` | 0.9622 / 0.576 |
| `TILE_WIDTH_HALF` / `TILE_HEIGHT_HALF` | 0.4811 / 0.288 |
| `TILE_VERTICAL_OFFSET` | -0.223 |
| `DEPTH_INCREASE_PER_ROW` | 100 |
| `BORDERS_BACK_SORT_OFFSET` | 0 |
| **`TERRAIN_SORT_OFFSET`** | **1** |
| `TRANSPORT_SORT_OFFSET` / `WORLD_OBJECT_SORT_OFFSET` | 2 / 2 |
| **`TERRAIN_FEATURE_SORT_OFFSET`** | **3** |
| `RESOURCES_OUTLINE_SORT_OFFSET` / `RESOURCES_SORT_OFFSET` | 4 / 5 |
| `HOUSES_SORT_OFFSET` | 6 |
| `WALLS_SORT_OFFSET` / `BUILDINGS_SORT_OFFSET` / `BORDERS_FRONT_SORT_OFFSET` | 97 / 98 / 99 |
| Desaturate tint (packed ARGB) | `0x7FF3F3F3` → RGBA(0.953, 0.953, 0.953, 0.498) |
| "No tint" (white) | `0xFFFFFFFF` → RGBA(1,1,1,1) |
| byte→float divisor | 255.0 (`0x437F0000`) |

### Field offsets (relevant; from `dump.cs`, used as load offsets in the disasm)

| Struct | Field | Offset |
|--------|-------|--------|
| `TileData` | terrain (`TerrainData.Type`) | 0x18 |
| `TileData` | climate (int tribe "style") | 0x1C |
| `TileData` | _skin (`SkinType`) | 0x20 |
| `TileData` | effects (List) | 0x28 |
| `TileData` | owner (byte) | 0x34 |
| `Tile` | terrainRenderer (`TerrainRenderer`) | 0x20 |
| `Tile` | mountainRenderer | 0x28 |
| `Tile` | forestRenderer | 0x30 |
| `Tile` | algaeRenderer | 0x38 |
| `Tile` | fogOfWarRenderer | 0x40 |
| `Tile` | transportContainer | 0x70 |
| `Tile` | data (`TileData`) | 0xB8 |
| `TerrainRenderer` | spriteRenderer | 0x20 |
| `TerrainRenderer` | waterSprites / oceanSprites / iceSprites | 0x28 / 0x30 / 0x38 |
| `TerrainRenderer` | isDesaturated (bool) | 0x40 |

### Enums (from `dump.cs`)

- `TerrainData.Type`: None=0, Water=1, Ocean=2, Field=3, Mountain=4, Forest=5, Ice=6, Wetland=7, Mangrove=8
- `TileData.EffectType`: None=0, Flooded=1, Swamped=2, Tentacle=3, Algae=4
- `SkinType`: Default=0, DarkElf=15, Swamp=17, Magma=18
- `TribeType`: None=0, Nature=1, Aimo=2, Aquarion=3, Bardur=4, Elyrion=5, Hoodrick=6, Imperius=7, Kickoo=8, Luxidoor=9, Oumaji=10, Quetzali=11, Vengir=12, Xinxi=13, Yadakk=14, Zebasi=15, Polaris=16, Cymanti=17

## 3. Geometry

- **World position** (`MapExtensions.ToPosition`, 0x2CC11AC):
  `posX = (x - y) * 0.4811`, `posY = (x + y) * 0.288`. Grid coords packed low32=x, high32=y.
- **No altitude / Z term:** `RenderMap` sets the tile transform straight from `ToPosition`
  (verified @0x2D4FBE8). The visual recession of water below land is **baked into the sprite
  art** (water block is shorter), not a position offset.
- Base sprite and all toppers are parented to the same `Tile` GameObject at that world point;
  pivots live in the atlas metadata (base ~256px diamond-centered; mountain/forest taller and
  bottom-aligned onto the diamond).
- **No flips** in the terrain path. Water corner/left/right variants are *distinct sprites*
  chosen by neighbor state (`WaterSpriteData.GetSpriteName`), not mirrored.

## 4. Draw order — verified instruction-level in `Tile.set_Depth` (0x2CE1C84)

`Tile.Depth` (set by `MapRenderer` from `GetDepthForTile`, row-major) is propagated to every
child renderer with its layer offset. Disassembly (`x19` = `this`, `w20` = depth):

```
ldr  x8,[x19,#0x20]; ldr x0,[x8,#0x20]   ; terrainRenderer.spriteRenderer (base)
add  w21, w20, #0x1                       ; depth + 1   (TERRAIN_SORT_OFFSET)
bl   PolytopiaSpriteRenderer$$set_SortingOrder

ldr  x0,[x19,#0x28]                        ; mountainRenderer
add  w22, w20, #0x3                        ; depth + 3   (TERRAIN_FEATURE_SORT_OFFSET)
bl   set_SortingOrder
ldr  x0,[x19,#0x38]; mov x1,x22            ; algaeRenderer   -> depth + 3
ldr  x0,[x19,#0x30]; mov x1,x22            ; forestRenderer  -> depth + 3
ldr  x0,[x19,#0x40]; mov x1,x21            ; fogOfWarRenderer -> depth + 1

ldr  x0,[x19,#0x70]; add w1,w20,#0x2        ; TransportContainer.set_Depth -> depth + 2
... BorderContainer / ShoreLineContainer / TentacleContainer.set_Depth, combinedMesh sortingLayer
```

Resulting per-tile sort (within a tile, then `y*100` between rows):

| Renderer | sortingOrder | Paints |
|----------|--------------|--------|
| base terrain (`terrainRenderer.spriteRenderer`) | **depth + 1** | bottom |
| fog of war | depth + 1 | (replaces base on hidden tiles) |
| transport (roads/routes) | depth + 2 | over base |
| **mountain / forest / algae toppers** | **depth + 3** | over base+transport |
| resources | depth + 4/5, houses +6, walls/buildings +97/98, borders front +99 | higher layers |

So a topper at `depth+3` always paints above its base at `depth+1`. Because depth is
row-major (+100/row), an entire tile's stack still sorts behind the rows in front of it.

## 5. `RenderTerrain` (0x2CDC828) — verified call sequence

BL decode of the body, in execution order:

1. `SkinVisualsRenderer.SkinTile` — select art variant (memoized on tile hash)
2. `GameManager.get_LocalPlayer` — for ownership/desaturation
3. `TileData.get_IsWater` (×2) + `TileData.HasEffect` — terrain/effect tests
4. **`GameObject.SetActive` ×3** — toggles mountain / forest / algae renderers:
   - `mountainRenderer.SetActive(terrain == Mountain(4))`
   - `forestRenderer.SetActive(terrain == Forest(5))`
   - `algaeRenderer.SetActive(HasEffect(Algae=4))`  *(the `mov w1, #0x4` is visible in the body)*
5. `PolytopiaSpriteRenderer.set_Color` (×2) — apply white or desaturate tint to features
6. **`TerrainRenderer.UpdateGraphics`** — set the base sprite (see §6)
7. `get_IsHidden` + `SetActive` ×2 — fog handling
8. **`Tile.RenderShorelines`** — coast strips (separate slice)

The desaturation tint is literally in this body:
`mov w24,#0xf3f3` + `movk w24,#0x7ff3,lsl#16` = `0x7FF3F3F3`; `mov w9,#0x437f0000` = 255.0
divisor used to unpack it to floats.

## 6. Base sprite selection — `TerrainRenderer.UpdateGraphics` (0x2CDBD9C)

```
t = data.terrain
if   t == Ice(6):   name = iceSprites.GetSpriteName(tile)      # neighbor-variant
elif t == Ocean(2): name = oceanSprites.GetSpriteName(tile)
elif t == Water(1): name = waterSprites.GetSpriteName(tile)
else:  # Field/Mountain/Forest/Wetland -> land base
    if   not HasEffect(Flooded):              name = "ground"          # @0x4922220
    elif HasEffect(Flooded) and Swamped:      name = "wetland_swamp"   # @0x492BBD0
    else:                                     name = "wetland"         # @0x492BBC8
    # alien/Cymanti special (style 11 / mountain) may override to "wetland" — see §8
sprite = DoSpriteLookup(name, climateTribe, climateSkin, checkForOutline=True)
if sprite: terrainRenderer.spriteRenderer.Sprite = sprite             # e.g. ground_imperius
# base re-tint only when the isDesaturated@0x40 flag flips
```

**Topper sprite names** come from the same `DoSpriteLookup` path keyed `"mountain"` /
`"Forest"` (themed), set on `mountainRenderer` / `forestRenderer` (drawn at `depth+3`).

### Theme derivation (`SkinVisualsTransientData.SetupForTile`, 0x2D9F0DC)

- `climateTribe = GameLogicData.GetTribeTypeFromStyle(data.climate)` — **data-driven** search
  of `GameLogicData.tribes` for the tribe whose `style == climate` (0x84A184).
- `climateSkin = Tile.GetVisualSkinTypeForTile()` (0x2CE0A28): global `GameSkin` override →
  spreading-climate skin (Polaris→15) → else `TileData._skin` (default 0).
- `DoSpriteLookup` (0x2B2F5B0) builds `name + "_" + lower(GetName(skin|tribe))` candidates via
  `String.Concat` + `EnumExtensions.GetName`, resolves the first existing atlas sprite, falls
  back to bare `name`. Suffix = lowercased tribe (or skin) name; `DarkElf`→`darkelf`.

## 7. Tint

Only two colors are ever applied by this layer:

- white `(1,1,1,1)` — unmodified.
- desaturate `0x7FF3F3F3` = RGBA(0.953, 0.953, 0.953, 0.498) — a dimmed, half-alpha *multiply*
  tint for tiles outside local relevance. Applied identically to base and toppers.

`TerrainRenderer.ShouldChangeSaturation(TerrainData.Type)` (0x2CDC244) returns
`terrain ∉ {Water, Ocean}` — so water/ocean are **never** desaturated. Unpack rule
(`PolytopiaSpriteRenderer.set_Color` from packed int `c`): `r=(c&0xFF)/255, g=((c>>8)&0xFF)/255,
b=((c>>16)&0xFF)/255, a=((c>>24)&0xFF)/255`. No per-player team tint on terrain (that is
units/borders); `tileClimateSettings.color` = `ColorUtil.WhiteInt`.

## 8. Open / data-driven (NOT closeable from the binary)

- **`climate → tribe` mapping is data, not a formula.** `GetTribeTypeFromStyle` searches
  `GameLogicData.tribes` for `style == climate`. The implementer needs the `style` values from
  the GameLogicData JSON. Theme suffix = lowercased tribe name (proven by catalog).
- **Exact `shouldDesaturate` truth table** is only partially decoded: confirmed it combines
  `data.owner` vs local player, `IsWater`, and `terrain == Ice`, and is gated by
  `ShouldChangeSaturation`. The fog/explored interaction needs the fog slice. Working model:
  "desaturate tiles outside local-player relevance; never water/ocean."
- **Sprite pivots in pixels** live in atlas metadata, not these functions.
- **Water/ocean/ice base** uses `WaterSpriteData.GetSpriteName` (neighbor default/corner/left/
  right) — overlaps the shoreline slice; bare `water`/`ocean`/`ice` is the safe still-image default.
- **Alien/Cymanti special case** (climate style 11; Mountain→`"wetland"` override) exists in
  `UpdateGraphics` (~0x2CDBEEC–0x2CDBF30) but its exact trigger is only partially decoded.
- **`Mangrove(8)`** has no `TerrainToString` entry (falls to "hidden") — likely handled
  elsewhere or unused in v116.

## 9. RVAs (v116 — re-verify after any update)

| Symbol | RVA |
|--------|-----|
| `MapRenderer$$RenderMap` | 0x2D4F6C0 |
| `MapRenderer$$GetDepthForTile` | 0x2D507A4 |
| `Tile$$Render` | 0x2CDC5DC |
| **`Tile$$set_Depth`** (applies sort offsets) | **0x2CE1C84** |
| `Tile$$RenderTerrain` | 0x2CDC828 |
| `Tile$$RenderShorelines` | 0x2CDEB78 |
| `TerrainRenderer$$UpdateGraphics` | 0x2CDBD9C |
| `TerrainRenderer$$ShouldChangeSaturation(Type)` | 0x2CDC244 |
| `TerrainRenderer.WaterSpriteData$$GetSpriteName` | 0x2CDC02C |
| `SkinVisualsRenderer$$SkinTile` | 0x2D9DF94 |
| `SkinVisualsTransientData$$SetupForTile` | 0x2D9F0DC |
| `Tile$$GetVisualSkinTypeForTile` | 0x2CE0A28 |
| `SpriteData$$TerrainToString` | 0x2D84A80 |
| `SpriteAtlasManager$$DoSpriteLookup` | 0x2B2F5B0 |
| `GameLogicData$$GetTribeTypeFromStyle` | 0x84A184 |
| `MapExtensions$$ToPosition` | 0x2CC11AC |

## 10. Reproduce the verification

```bash
cd /Users/owfei/testing/biblical_greed
# call order inside any function (ARM64 BL decode against script.json):
python3 - <<'PY'
import json, struct; from pathlib import Path
BIN=Path("GameAssembly_arm64.dylib").read_bytes()
M=sorted(json.load(open("il2cpp_dump/script.json"))["ScriptMethod"],key=lambda m:m["Address"])
sym=lambda a:([m for m in M if m["Address"]<=a] or [{"Name":hex(a)}])[-1]["Name"]
def scan(s,e):
    for o in range(s,e,4):
        i=struct.unpack_from("<I",BIN,o)[0]
        if (i>>26)==0b100101:
            d=i&0x3FFFFFF; d-=0x4000000 if d&0x2000000 else 0
            print(f"  +{o-s:#05x} {sym(o+(d<<2))}")
scan(0x2CDC5DC,0x2CDC828)   # Tile.Render
PY
# instruction-level (sort offsets, tint constant):
objdump -d --start-address=0x2CE1C84 --stop-address=0x2CE1DEC GameAssembly_arm64.dylib   # set_Depth
objdump -d --start-address=0x2CDC828 --stop-address=0x2CDCBB0 GameAssembly_arm64.dylib   # RenderTerrain
```
