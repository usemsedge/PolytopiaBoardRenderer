# Slice: draworder_color — Global composite & color

## 1. Summary

Every drawable in the board is a `PolytopiaSpriteRenderer` whose **`sortingOrder`
integer is the single global painter's-algorithm key**. The order is built from two
numbers added together: a per-tile **row depth** `rowDepth = mapHeight - (x + y) * 100`
(from `MapRenderer.GetDepthForTile`, RVA 0x2D507A4) and a small **sub-layer offset**
0..99 selecting which of a tile's layers (terrain, features, resources, houses, walls,
buildings, borders) it is. The whole board is composited by ascending `sortingOrder`:
the lowest value is drawn first (furthest back), the highest last (on top / front).
Because `rowDepth` *decreases* by 100 per diagonal row toward the back, back rows get
**lower** `sortingOrder` and draw first; front rows (bottom of screen) get **higher**
values and draw on top — correct isometric back-to-front order. Each tile bakes its own
layer renderers into one combined mesh in `Tile.BatchSprites` (RVA 0x2CDE3CC), preserving
the per-renderer `sortingOrder`. Player/tribe color is a single packed ARGB int per player
(`PlayerState.color`, offset 0xC0) unpacked to a float RGBA `(R>>16, G>>8, B)/255, A=1`
by `GetPlayerColor` (RVA 0x2CA78FC); tints are applied per sprite either as a multiply
(`PolytopiaSpriteRenderer.color`) or as a lerp overlay (`overlayColor`+`overlayStrength`).

## 2. Constants

| Constant | Value | Source |
|----------|-------|--------|
| `DEPTH_INCREASE_PER_ROW` | 100 | dump.cs:371970; binary `mov w9,#-0x64` (−100) in GetDepthForTile @0x2D5080 4 |
| `BORDERS_BACK_SORT_OFFSET` | 0 | dump.cs:371971; BorderContainer.set_Depth @0x2CD6CA8 stores value+0 |
| `TERRAIN_SORT_OFFSET` | 1 | dump.cs:371972; Tile.set_Depth @0x2CE1CD8 `add w21,w20,#1` |
| `TRANSPORT_SORT_OFFSET` | 2 | dump.cs:371973 |
| `WORLD_OBJECT_SORT_OFFSET` | 2 | dump.cs:371974; WorldObject.set_Depth @0x2CE7264 `add w1,w1,#2` |
| `TERRAIN_FEATURE_SORT_OFFSET` | 3 | dump.cs:371975; Tile.set_Depth @0x2CE1CEC `add w22,w20,#3` (mountain/forest/algae) |
| `RESOURCES_OUTLINE_SORT_OFFSET` | 4 | dump.cs:371976 |
| `RESOURCES_SORT_OFFSET` | 5 | dump.cs:371977 |
| `HOUSES_SORT_OFFSET` | 6 | dump.cs:371978 |
| `WALLS_SORT_OFFSET` | 97 | dump.cs:371979 |
| `BUILDINGS_SORT_OFFSET` | 98 | dump.cs:371980 |
| `BORDERS_FRONT_SORT_OFFSET` | 99 | dump.cs:371981; BorderContainer.set_Depth @0x2CD6CD4 `add w1,w8,#0x63` (=99) |
| `TILE_WIDTH_HALF` | 0.4811 | dump.cs:371966; IEEE `0x3EF652BD` |
| `TILE_HEIGHT_HALF` | 0.288 | dump.cs:371967; IEEE `0x3E9374BC` |
| `TILE_VERTICAL_OFFSET` | −0.223 | dump.cs:371969 |
| color-channel divisor | 255.0 | IEEE `0x437F0000` in GetPlayerColor @0x2CA791C; also terrain "full white" in RenderTerrain @0x2CDC9F0 |

Note: `WORLD_OBJECT_SORT_OFFSET = 2` is baked into `WorldObject` itself — its renderer's
`sortingOrder = Depth + 2` (get_Depth returns `sortingOrder − 2`). The resource/improvement
sub-layer offsets (4/5/6/97/98) are added **on top of** the tile rowDepth when the tile sets
each world object's `Depth`, so a resource's renderer ends at `rowDepth + 5` etc.

## 3. Sprite selection

This slice does not pick art per layer (the terrain/resource/improvement/unit/border slices
own that). It governs the **ordering and tinting** of whatever sprites those slices produce.
The relevant catalog facts it relies on (all confirmed present in `pyrender/sprite_catalog.json`):

- Tintable layers ship a paired mask sprite suffixed `_tint`, multiplied by the player color.
  Confirmed examples: `warrior_0_tint_ranger`, `Larva_tint`, `aquarion_crab_tint`,
  `boomchi_tint`, `4_8_tint` (city-house tint). The opaque base (e.g. `head_imperius`) is
  drawn unmultiplied; the `_tint` layer above it carries the player color.
- Outlines ship suffixed `_Outline`. Confirmed: `ResourceGFX_crop_Outline`,
  `head_imperius_Outline`, `warrior_0_tint_ranger_Outline`.
- Borders: confirmed `Border_A`, `Border_B`, `Border_Down`, `Border_Left`, `BorderXGFX`,
  `BorderYGFX`. Houses: confirmed `House_1_aibo` etc. Roads: confirmed `Road`, `roads0000`.

(Verified via `pyrender/sprite_catalog.json`, 2051 entries.)

## 4. Geometry

This slice is depth/sort + color only; placement/anchor/flip are owned by the per-layer slices.
The sort-relevant geometry:

- A tile's world origin = `MapExtensions.ToPosition(x,y)` = `((x−y)*0.4811, (x+y)*0.288)`
  (verified fact in BRIEF). Screen-down = smaller `posY`.
- Each tile's `Tile.Depth` is set once to `rowDepth = mapHeight − (x+y)*100`
  (`MapRenderer.GetDepthForTile`). `Tile.set_Depth(value)` (RVA 0x2CE1C84) then writes the
  per-child renderer `sortingOrder`:
  - `terrainRenderer` (field 0x20) → `value + 1`
  - `mountainRenderer` (0x28), `forestRenderer` (0x30), `algaeRenderer` (0x38) → `value + 3`
  - `fogOfWarRenderer` (0x40) → `value + 1`
  - `border` (0x50) → `BorderContainer.set_Depth(value)`: back lists `value+0`, front lists `value+99`
  - `transport` (0x58) → `TransportContainer.set_Depth(value)` (roads ≈ `value+2`)
  - resource / improvement world objects → their `Depth` is set to `value`, and their renderer
    lands at `value + offset` (resource +5, resource outline +4, houses +6, walls +97, buildings +98).
- Sub-depth therefore packs into the same int as row depth; consecutive diagonal rows are
  100 apart so the 0..99 sub-layer band of one tile never collides with another tile's band.
- In `BatchSprites` each renderer's mesh is transformed into the combined object's local space
  (`combinedMeshFilter`/`combinedMeshRenderer`, fields 0x88/0x90) and concatenated; submesh
  order follows the renderer list order produced by `Tile.UpdateSortedSpriteRenderers`
  (RVA 0x2CDA0D4), which appends fog→border→shoreline→transport→forest→mountain→algae→
  resource→improvement→border(front)→tentacle. Renderers sharing the same atlas/material are
  merged into one batched renderer (loop @0x2CDE4F4–0x2CDE668).

## 5. Algorithm

Painter's-algorithm composite for the whole board:

```
def render_board(state, sprites):
    H = state.map.height
    draw_list = []                      # (sortingOrder, layer_seq, sprite, pos, color, overlay)

    for tile in all_tiles(state):       # any order
        x, y = tile.x, tile.y
        rowDepth = H - (x + y) * 100     # GetDepthForTile, RVA 0x2D507A4

        # emit each layer this tile produces, with its sub-offset:
        emit(rowDepth + 0,  back_border_sprites(tile))      # BORDERS_BACK
        emit(rowDepth + 1,  terrain_sprite(tile))           # TERRAIN
        emit(rowDepth + 1,  fog_sprite(tile))               # fog uses TERRAIN offset
        emit(rowDepth + 2,  road_transport_sprites(tile))   # TRANSPORT / WORLD_OBJECT
        emit(rowDepth + 3,  feature_sprites(tile))          # mountain / forest / algae
        emit(rowDepth + 4,  resource_outline_sprite(tile))  # RESOURCES_OUTLINE
        emit(rowDepth + 5,  resource_sprite(tile))          # RESOURCES
        emit(rowDepth + 6,  city_house_sprites(tile))       # HOUSES
        emit(rowDepth + 97, wall_sprites(tile))             # WALLS
        emit(rowDepth + 98, building_sprites(tile))         # BUILDINGS (incl. units? see Q)
        emit(rowDepth + 99, front_border_sprites(tile))     # BORDERS_FRONT

    # GLOBAL SORT — ascending sortingOrder; lowest drawn first (back), highest last (front/top).
    # Tie-break: preserve emission order within a tile (stable sort) so the per-tile sequence
    # in UpdateSortedSpriteRenderers is respected when two layers share an offset.
    draw_list.sort(key=lambda e: (e.sortingOrder, e.layer_seq))

    canvas = blank()
    for e in draw_list:
        layer = sprites[e.sprite]
        if e.color   is not None: layer = multiply_rgba(layer, e.color)        # PolytopiaSpriteRenderer.color
        if e.overlay is not None: layer = lerp_rgb(layer, e.overlay.color, e.overlay.strength)
        canvas.paste(layer, e.pos)       # over (src-over alpha)
    return canvas
```

Key correctness points (binary-verified):
- `rowDepth = mapHeight − (x+y)*100` — `madd w0, (x+y), −100, mapHeight` @0x2D50808.
  `mapHeight` is `MapData.height` (ushort at offset 0x12, dump.cs:774337).
- Lower `sortingOrder` = drawn first. Back rows (small `x+y`) → high `rowDepth` would imply
  drawing last; but small `x+y` is the **bottom/front** of the iso board (low `posY`), so
  high value = front = on top is correct. Front rows (large `x+y`) → very negative value =
  drawn first = behind. (Self-consistent with `BorderContainer` front=+99 sitting on top.)
- Within one tile, sub-offsets give the fixed stack: borders-back < terrain < transport <
  features < resource-outline < resource < houses < walls < buildings < borders-front.

## 6. Tint/color

**Player/tribe color is one packed signed 32-bit int per player: `PlayerState.color`
(offset 0xC0, dump.cs:776725).** Layout is **ARGB** `0xAARRGGBB`.

`GetPlayerColor(PlayerState, GameState)` (RVA 0x2CA78FC) unpacks it to a Unity `Color`:
```
i = playerState.color                # int at 0xC0
R = ((i >> 16) & 0xFF) / 255.0
G = ((i >>  8) & 0xFF) / 255.0
B = ( i        & 0xFF) / 255.0
A = 1.0                              # alpha forced to 1 (fmov s3,#1.0 @0x2CA7938)
```
Verified from the test gamestate: player 0 (Imperius) `color = −16776961 = 0xFF0000FF →
RGB (0,0,255)` blue; player 1 (Bardur) `color = −65536 = 0xFFFF0000 → RGB (255,0,0)` red.

**Where the color comes from (defaults):** `PlayerState.color` is seeded by
`PlayerState.SetPlayerColors(GameState)` (RVA 0x7F5248) from per-tribe/skin data:
`TribeData.color` (int, dump.cs:784177, offset 0x14) and, when a skin is active,
`SkinData.color` (int, dump.cs:783791, offset 0x10). The numeric default-per-tribe table is
**runtime JSON game data, not present in the static dump** — the implementer should read
`PlayerState.color` directly from the GameState (it is always populated), not hard-code tribe
colors. TribeType index order (dump.cs:878951): None0 Nature1 Aimo2 Aquarion3 Bardur4
Elyrion5 Hoodrick6 Imperius7 Kickoo8 Luxidoor9 Oumaji10 Quetzali11 Vengir12 Xinxi13 Yadakk14
Zebasi15 Polaris16 Cymanti17. Canonical default colors (from observed game data / gamestate,
**confirm against live state**): Imperius=blue(0,0,255), Bardur=red(255,0,0). Other tribes
have their own brand colors but no numeric source is in the static dump.

**Two tint channels on every `PolytopiaSpriteRenderer`:**
- `color` (RGBA float, field 0x30; set via `set_Color` RVA 0x2CD6978) — straight multiply
  over the sprite's pixels. Terrain renderers are set to white `(255,255,255,255)/255 = 1,1,1,1`
  (no tint; `mov w9,#0x437F0000` then `set_Color` @0x2CDCA24/0x2CDCABC).
- `overlayColor` (RGBA, field 0x40) + `overlayStrength` (float, field 0x50; set via
  `SetOverlayColor` RVA 0x2CDBB64) — a **lerp toward** overlayColor by strength:
  `out = lerp(base*color, overlayColor, overlayStrength)`. Used for highlight/fog/tentacle
  effects. SetOverlayColor early-outs if the new value is within ~1e-3 of the current.

**Player tinting of units/houses/borders:** the opaque base art is drawn untinted; the paired
`_tint` mask sprite (suffix `_tint`, e.g. `warrior_0_tint_ranger`, `4_8_tint`) is drawn with
`color = GetPlayerColor(owner)` as a multiply, producing the player-colored regions. Borders
use the owner's `GetPlayerColor` directly on the border sprites.

**Outline color:** `Tile.GetOutlineColor` (RVA 0x2CDED40) selects one of **two static RGBA
colors** from a render-config object (field 0xB8: color A at offsets 0xA0–0xAC, color B at
0xB0–0xBC). The choice depends on tile ownership and a special-case `skinType == 17` (Cymanti)
/ resource check. The two RGBA float quadruplets are runtime config, not in the static dump —
treat outline color as a fixed pair to be sampled from the live config (default appears as a
dark/near-black outline for resources; confirm empirically).

## 7. RVAs verified

- `MapRenderer.GetDepthForTile` 0x2D507A4 — confirmed `depth = mapHeight − (x+y)*100`;
  `mapHeight` = `MapData.height` (ushort @0x12); coords packed low32=x, high32=y.
- `Tile.set_Depth` 0x2CE1C84 — confirmed per-child `sortingOrder` writes: terrain +1,
  fog +1, mountain/forest/algae +3, border via BorderContainer.set_Depth, transport via
  TransportContainer.set_Depth.
- `BorderContainer.set_Depth` 0x2CD6C98 — confirmed back renderers = value, front = value+99.
- `WorldObject.get_Depth`/`set_Depth` 0x2CE7230/0x2CE7254 — confirmed renderer
  `sortingOrder = Depth + 2` (WORLD_OBJECT offset baked in).
- `Tile.UpdateSortedSpriteRenderers` 0x2CDA0D4 — confirmed it clears and rebuilds
  `sortedSpriteRenderers` (field 0x128) appending fog/border/shoreline/transport/forest/
  mountain/algae/resource/improvement/border-front/tentacle, calling `set_SortingOrder`.
- `Tile.BatchSprites` 0x2CDE3CC — confirmed: clears dirty, unbatches, calls
  UpdateSortedSpriteRenderers, iterates `sortedSpriteRenderers`, merges same-atlas/material
  meshes into `batchedSpriteRenderers` (0x130) and bakes one combined mesh
  (`combinedMeshFilter`/`combinedMeshRenderer`), preserving list order as submesh order.
- `PolytopiaSpriteRenderer.set_Color` 0x2CD6978 and `SetOverlayColor` 0x2CDBB64 — confirmed
  two channels: multiply `color` (field 0x30) and lerp `overlayColor`/`overlayStrength`
  (fields 0x40/0x50) with epsilon early-out.
- `GetPlayerColor` (view) 0x2CA78FC — confirmed ARGB unpack of `PlayerState.color` (0xC0),
  R=(i>>16)&255, G=(i>>8)&255, B=i&255, /255, A=1.0.
- `Tile.GetOutlineColor` 0x2CDED40 — confirmed picks 1 of 2 static RGBA config colors based
  on ownership / skinType==17.
- Field offsets confirmed in dump.cs: `MapData.height` 0x12 (774337), `WorldCoordinates.x/y`
  0x0/0x4 (780058), `PlayerState.color` 0xC0 (776725), `TribeData.color` 0x14 (784177),
  `PolytopiaSpriteRenderer.color/overlayColor/overlayStrength/sortingOrder`
  0x30/0x40/0x50/0x74 (419032-419043).

## 8. Open questions / risks

1. **Numeric per-tribe default palette is not in the static dump.** It lives in runtime JSON
   (`TribeData.color` / `SkinData.color`). The implementer must take `PlayerState.color` from
   the GameState (always populated). Only Imperius=blue and Bardur=red are confirmed from the
   test gamestate; other tribes' exact RGB are unverified here.
2. **Outline RGBA values** (the two colors in GetOutlineColor's config object) are runtime
   floats; their exact values were not recoverable from the static dump. Sample from live
   config or measure from a rendered frame.
3. **Units' sub-layer:** `RenderUnit` (0x2CDD620) places units as world objects; their
   `sortingOrder` likely sits in the buildings band (≈ +98) or just above so they draw over
   terrain/resources. Exact unit offset is owned by the unit slice — confirm whether units use
   BUILDINGS (+98) or a dedicated value; this affects unit-vs-building overlap.
3. **Tie-break within equal offsets** (terrain+1 vs fog+1; multiple +3 features): the engine
   relies on stable list order from `UpdateSortedSpriteRenderers`. Implement the global sort as
   **stable** keyed on `(sortingOrder, emissionIndex)` with emissionIndex following that list
   order (fog after terrain; features in forest? no — order is forest→mountain→algae per the
   list-append sequence). Getting this order wrong only matters where layers share an offset.
4. **Cross-tile equal sortingOrder is impossible** by construction (rows are 100 apart, band is
   0..99), so no inter-tile tie-break is needed — verified by the constant layout.
5. **`color` vs `overlayColor` compositing order**: shader applies multiply then lerp. If the
   Python core only supports one, multiply (`color`) is the dominant/player-tint channel;
   overlay is for transient highlights and can be omitted for a static board render.
