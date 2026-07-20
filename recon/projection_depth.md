# Slice: projection_depth — Projection, Depth & Canvas Framing

## 1. Summary
This is the geometric foundation every other render layer sits on. A grid cell
`(x,y)` is converted to a world `Vector2` by `MapExtensions.ToPosition` as
`posX = (x - y) * 0.4811`, `posY = (x + y) * 0.288` (this is an isometric/diamond
projection; the two constants are `TILE_WIDTH_HALF` and `TILE_HEIGHT_HALF`). World
units are converted to pixels by the sprite authoring scale **PPU = 266.057
pixels/world-unit** (derived exactly: the 256px-wide `ground_*` tile equals
`TILE_WIDTH = 0.9622` world units → `256 / 0.9622 = 266.057`). The base tile world
position carries **no** `TILE_VERTICAL_OFFSET`; that constant (`-0.223`) is applied
only by individual elevated sprites (terrain features / buildings) within their own
renderers, not by the tile origin. Draw order is a single integer Unity
`SortingOrder` per sprite: `base = (x + y) * (-100) + mapHeight` (from
`GetDepthForTile`), and each layer adds its sub-offset (terrain +1, features +3,
resources +5, buildings +98, borders-front +99, …). Higher SortingOrder draws in
front. Because the game's world Y is up and `posY` grows with `x+y`, tile (0,0) is
the visual front-bottom and (W-1,H-1) is the back-top; for a Y-down output image the
implementer negates `posY`. The canvas is sized to the bounding box of all tile
pixel positions plus sprite extents.

## 2. Constants
| Constant | Value | Hex (IEEE-754 f32) | Source |
|----------|-------|--------------------|--------|
| `TILE_WIDTH` | 0.9622 | 0x3F7652BD | dump.cs:371964 (MapRenderer) |
| `TILE_HEIGHT` | 0.576 | 0x3F1374BC | dump.cs:371965 |
| `TILE_WIDTH_HALF` | 0.4811 | 0x3EF652BD | dump.cs:371966; used in ToPosition @0x2CC1204 |
| `TILE_HEIGHT_HALF` | 0.288 | 0x3E9374BC | dump.cs:371967; used in ToPosition @0x2CC121C |
| `TILE_HORIZONTAL_OFFSET` | 0 | — | dump.cs:371968 |
| `TILE_VERTICAL_OFFSET` | -0.223 | 0xBE645A1D | dump.cs:371969 (NOT applied to tile origin; see §4) |
| `DEPTH_INCREASE_PER_ROW` | 100 | — | dump.cs:371970; appears as `-100` in GetDepthForTile @0x2D50804 |
| `PIXELS_PER_UNIT` (derived) | 266.0569528 | — | `256 / 0.9622` (sprite px width / TILE_WIDTH). Not a named const in dump; the sprite import scale. |
| Sub-layer sort offsets | see table §4 | — | dump.cs:371971-371981 |

Half-diamond in pixels (exact, with PPU above):
`TILE_WIDTH_HALF * PPU = 128.000 px`, `TILE_HEIGHT_HALF * PPU = 76.624 px`.

## 3. Sprite selection
This slice selects no sprites of its own; it positions whatever sprites the other
layers produce. It does need tile sprite **dimensions** to compute pivots and canvas
size. Confirmed present in `pyrender/sprite_catalog.json`:
- `ground_imperius` 256x245, `ground_bardur` 256x245, `ground_xinxi` 256x245,
  `ground_oumaji` 256x245, `ground_kickoo` 256x245 (all base ground tiles 256x245;
  `ground_cymanti` 256x242, `ground_magma` 256x249 are the only ground outliers).
- `mountain_bardur` 232x183, `mountain_imperius` 232x183 (features are narrower/shorter).
- `Forest_kickoo` 255x182, `Forest_imperius` 238x183.
- Generic fallbacks: `ground` 256x245, `water` 256x227, `ocean` 256x227, `ice` 256x243.
All verified to exist (catalog has 2051 entries). **Every base `ground_*` tile is
256px wide → all share PPU 266.06**, which is what makes the projection consistent.

## 4. Geometry
**World → pixel transform** (the reference projection; `(x,y)` grid → `(px,py)` pixel,
relative to tile (0,0) before canvas offset):
```
PPU = 266.0569528            # = 256 / 0.9622
world_x = (x - y) * 0.4811
world_y = (x + y) * 0.288
px =  world_x * PPU          #  (x-y)*128.000
py = -world_y * PPU          # -(x+y)*76.624   (negate: game Y-up → image Y-down)
```
This places (0,0) at pixel (0,0); +x goes right-down, +y goes left-down. Neighbor
deltas (verified numerically): +x → (+128.0, +76.624); +y → (-128.0, +76.624);
+(1,1) → (0, +153.25) = one full TILE_HEIGHT down. The point `(px,py)` is the tile's
**world-position anchor** = where the sprite **pivot** lands.

**Pivot / anchor.** `ToPosition` returns the tile's world position; `Tile.set_Position`
(0x2CE1C38, disassembled) forwards `(posX, posY, 0)` straight to the Unity transform
with no adjustment, so the sprite's own pivot decides where the diamond sits.
Polytopia tile art uses a **horizontally-centered pivot** (all `ground_*` are exactly
256 wide and symmetric, and the half-diamond is exactly 128px = w/2, confirming the
diamond is centered in the sprite). Vertically the pivot is at the **diamond center**
on the tile surface. Practical placement for a sprite of size `(sw, sh)` whose pivot
is normalized `(pivX, pivY)` (Unity: y measured from bottom):
```
paste_left = canvas_x + px - pivX * sw
paste_top  = canvas_y + py - (1 - pivY) * sh
```
For base ground tiles assume `pivX = 0.5`. `pivY` is the **open risk** (see §8): the
catalog stores no pivot. Recommended default `pivY = 0.5` (center). The vertical
"overshoot" of the 245px sprite over the 153px diamond is the raised tile lip and is
handled by the sprite art itself, not by an offset here.

**TILE_VERTICAL_OFFSET (-0.223).** Searched the binary: it is NOT applied in
`ToPosition`, `Tile.set_Position`, `Tile.set_Depth`, `Tile.Render`, or
`TerrainRenderer.UpdateGraphics` (the only float consts found in UpdateGraphics are a
color `0x7FF3F3F3 / 255`). It is consumed by the elevated-feature sub-renderers
(mountain/forest/building local Y). For the base projection: **do not apply it**.
The terrain-features / improvement slices apply `-0.223 * PPU = -59.33 px` (i.e. the
sprite is nudged 59px in +screen-y, downward) where they sit raised on the tile.
(Marked: exact per-layer application is owned by those slices.)

**Sub-depth fit (Unity SortingOrder, NOT a Z position).** `set_Depth` (0x2CE1C84,
disassembled) takes the base depth and calls `PolytopiaSpriteRenderer.set_SortingOrder`
(0x2CD6CFC) on each child container with the base plus a constant: terrain +1,
terrain-features +3, etc. The full offset table (dump.cs:371971-371981):
| Offset | Layer |
|--------|-------|
| 0 | Borders back |
| 1 | Terrain |
| 2 | Transport / World object |
| 3 | Terrain features |
| 4 | Resource outline |
| 5 | Resources |
| 6 | Houses |
| 97 | Walls |
| 98 | Buildings |
| 99 | Borders front |

## 5. Algorithm
```
# --- one-time setup for a map of width W, height H ---
PPU = 266.0569528
HW, HH = 0.4811, 0.288

def tile_pixel(x, y):            # before canvas offset
    return ((x - y) * HW * PPU, -(x + y) * HH * PPU)

# 1. bounding box of tile anchors over all cells
xs = [tile_pixel(x,y)[0] for x in range(W) for y in range(H)]
ys = [tile_pixel(x,y)[1] for x in range(W) for y in range(H)]
# anchor extents:
min_px = -(H-1)*HW*PPU            # leftmost: tile (0,H-1)
max_px =  (W-1)*HW*PPU            # rightmost: tile (W-1,0)
min_py = -(W-1+H-1)*HH*PPU        # topmost (most negative): tile (W-1,H-1)
max_py = 0.0                      # bottommost: tile (0,0)

# 2. pad by sprite extents so no sprite clips. Use the widest/tallest tile sprite
#    actually placed; ground is 256x245. With pivot (0.5, pivY):
PAD_L = PAD_R = 256/2                     # = 128
PAD_TOP    = (1 - pivY) * SPRITE_MAX_H    # default pivY=0.5 -> 122.5 for 245-tall
PAD_BOTTOM = pivY       * SPRITE_MAX_H    # plus extra for tall features/cities
# A safe simple choice: PAD = max sprite height placed on the map (e.g. tall city ~ a
# few hundred px). Compute from the actual sprites the other slices emit.

# 3. canvas size & origin
canvas_w = ceil(max_px - min_px) + PAD_L + PAD_R
canvas_h = ceil(max_py - min_py) + PAD_TOP + PAD_BOTTOM
origin_x = -min_px + PAD_L        # add to every px
origin_y = -min_py + PAD_TOP      # add to every py

# --- per sprite ---
def place(x, y, layer_offset, sw, sh, pivX=0.5, pivY=0.5, extra_world_y=0.0):
    px, py = tile_pixel(x, y)
    py += -extra_world_y * PPU      # e.g. TILE_VERTICAL_OFFSET applied by feature layers
    cx = origin_x + px
    cy = origin_y + py
    left = round(cx - pivX * sw)
    top  = round(cy - (1 - pivY) * sh)
    sort_key = (x + y) * (-100) + H + layer_offset
    return (left, top, sort_key)

# --- compositing ---
# Paint ascending sort_key (lowest first = farthest back), so higher SortingOrder
# ends up on top. With (x+y)*(-100): front rows (large x+y) get the SMALLEST key,
# which in the game's world-Y-up space corresponds to the visually-front tiles being
# drawn LAST because they also have the largest screen-y after the negate. To get a
# painter's order directly usable in a Y-down image, sort by the TUPLE:
#     ( (x+y),  layer_offset )   ascending  -> back-to-front, then within a tile by layer
# This is equivalent to the engine's sortingOrder ordering and avoids sign confusion.
```
Note for implementer: the *engine* sort key is the signed integer above, but for a
top-down paint loop the simplest faithful order is **ascending `(x+y)` then ascending
`layer_offset`** (paint farthest-back rows first). Both yield identical visible
stacking because `+mapHeight` is a constant per map and `-100` only reverses sign.

## 6. Tint / color
None for this slice. Projection and depth carry no color. (The lone color constant
seen near terrain, `0x7FF3F3F3`/255 ≈ rgba(0.953,0.953,0.953,0.5), belongs to the
terrain/skin slice, not here.)

## 7. RVAs verified
- `MapExtensions$$ToPosition` 0x2CC11AC — disassembled. Reads packed coords (low32=x
  @0x0, high32=y @0x4 of `WorldCoordinates`, dump.cs:780058-59); computes
  `s0=(x-y)*0.4811` (const @0x2CC1204), `s1=(x+y)*0.288` (const @0x2CC121C); returns
  Vector2(s0,s1). No vertical offset.
- `MapRenderer$$GetDepthForTile` 0x2D507A4 — disassembled. `ldrh w20,[mapData,#0x12]`
  = `mapData.height` (MapData layout dump.cs:774333: width@0x10, height@0x12);
  `depth = (x+y) * (-100) + height` (`madd w0, (x+y), -100, height` @0x2D50808).
- `Tile$$set_Position` 0x2CE1C38 — disassembled. Pure pass-through of (s0,s1,s2) to
  Unity transform setter 0x38CF5F0; confirms NO TILE_VERTICAL_OFFSET on tile origin.
- `Tile$$set_Depth` 0x2CE1C84 — disassembled. Calls
  `PolytopiaSpriteRenderer$$set_SortingOrder` (0x2CD6CFC, symbol-resolved) per child
  with base+offset (+1, +3, …), confirming sub-layer offsets are Unity SortingOrder.
- `MapRenderer$$RenderMap` 0x2D4F6C0 — disassembled the placement site: calls
  `set_Depth` (0x2CE1C84) then `ToPosition` (0x2CC11AC) then `set_Position`
  (0x2CE1C38) per cell, in that order (@0x2D4FBE4–0x2D4FC00).
- Constants block dump.cs:371960-371981 (MapRenderer) — read directly.
- PPU 266.057 — derived from `sprite_catalog.json` (`ground_imperius` 256x245) ÷
  `TILE_WIDTH` 0.9622; cross-checks to exactly 128.0 px half-diamond.

## 8. Open questions / risks
1. **Vertical pivot (`pivY`) of tile sprites is not in the catalog** (only w/h). The
   256x245 ground sprite is taller than the 153px diamond, so the true pivot is some
   art-defined fraction (likely centered on the diamond surface, not the sprite
   center). Highest-impact unknown: a wrong `pivY` shifts the whole board vertically
   by tens of px and changes how features stack. Recommend the implementer extract
   pivots from the original Unity sprite atlas if available, or calibrate `pivY`
   against one known-good screenshot. Default assumption here: `pivX=0.5`, `pivY=0.5`.
2. **TILE_VERTICAL_OFFSET (-0.223 → -59.33 px) application** is delegated to the
   terrain-feature / improvement / unit slices; I confirmed it is absent from the base
   tile origin but did not trace each feature renderer's exact use. Those slices must
   own it.
3. **Canvas padding** depends on the tallest sprite actually placed (cities/units can
   be much taller than 245px). Size padding from the real max sprite height the other
   slices emit, not from ground alone.
4. **Sort ties / sub-sub-ordering** within the same `(x+y, layer)` (e.g. two units, or
   houses within a city) are resolved by city/unit slices' own internal ordering, not
   by this integer key.
5. The `-100` sign and `+mapHeight` bias are irrelevant to a self-contained Python
   painter (use ascending `(x+y, layer)`), but matter if you ever reproduce the exact
   integer `sortingOrder` values for debugging against the game.
