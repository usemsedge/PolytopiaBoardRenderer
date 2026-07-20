# Slice: Shorelines / Coast (`Tile$$RenderShorelines` 0x2CDEB78)

## 1. Summary
Shorelines are the thin coast/foam sprites drawn on the **edges of a water tile that
touch land**. They are produced by `ShoreLineContainer` (Tile field `shoreline` @0x70),
which owns four `PolytopiaSpriteRenderer`s — `north/south/east/west`. The per-edge
visibility and sprite-extension are precomputed once per map by
`MapDataExtensions.GenerateShoreLines(MapData)` (0x7FEC78) into each `TileData.shorelines`
(field @0x40, type `TileData.Shorelines` with `bool any` + four `TileData.Shoreline`
N/S/E/W). At render time `Tile.RenderShorelines(bool explored)` (0x2CDEB78) simply:
shows/hides the container (gated by `shorelines.any` and the `explored`/fog flag) and
calls `ShowN/S/E/W(shore)` for each side. Each `ShowX` does
`renderer.gameObject.SetActive(shore.visible)` and, if visible,
`UpdateSprite(renderer, dirIndex, shore.spriteExt)` to assign sprite
`originalSpriteNames[dirIndex] + spriteExt`. The base sprite is `shoreline`; the only
runtime extension is `""` (default) or `"_swamp"`. Shorelines are generated **only on
non-frozen Water tiles** (terrain==Water==1); Ocean tiles get none. A side becomes
visible when its grid neighbour `IsLand` (terrain in {Field,Mountain,Forest,Ice}). The
four direction sprites are distinct prefab child transforms sharing one base art rotated/
placed by the prefab, so the four-edge selection IS the "bitmask" (4-neighbour, edges only;
no diagonal/corner sprites in this container).

## 2. Constants
| Name | Value | Source |
|------|-------|--------|
| `TileData.Shoreline.SPRITE_EXT_DEFAULT` | `""` | dump.cs 774561 |
| `TileData.Shoreline.SPRITE_EXT_SWAMP` | `"_swamp"` | dump.cs 774562 |
| Direction index N | `0` | ShowN passes `w2=#0` (0x2CD9518) |
| Direction index S | `1` | ShowS passes `w2=#1` (0x2CD9584) |
| Direction index E | `2` | ShowE passes `w2=#2` (0x2CD95F0) |
| Direction index W | `3` | ShowW passes `w2=#3` (0x2CD965C) |
| `TerrainData.Type.Water` | `1` | dump.cs 784068 (center-tile gate) |
| `TerrainData.Type.Ocean` | `2` | dump.cs 784069 |
| IsLand range | terrain `- 3 < 4` ⇒ {3,4,5,6}=Field/Mountain/Forest/Ice | get_IsLand 0x7DCBC4 |
| `EffectType.Swamped` | `2` | dump.cs 774601 (HasEffect arg) |
| `SkinType.Swamp` | `17` (`0x11`) | dump.cs (SkinType enum); cmp `#0x11` |
| Frozen climate | `climate==15` (with terrain==Water) | IsFrozen 0x7D9E3C |
| `Tile.WATER_SELECTION_Y_OFFSET` | `-0.05` | dump.cs 418479 (selection only, not draw) |

**Struct field offsets (confirmed):**
- `Tile.shoreline` @0x70; `Tile.data` (TileData) @0xB8; `Tile.isDirty` @0x121; `Tile.fogOfWarRenderer` @0x40.
- `TileData.terrain` @0x18; `TileData.climate` @0x1C; `TileData._skin` @0x20; `TileData.effects` @0x28; `TileData.owner` @0x34; `TileData.shorelines` @0x40.
- `TileData.Shorelines.any` @0x10; `.N` @0x18; `.S` @0x20; `.E` @0x28; `.W` @0x30.
- `TileData.Shoreline.visible` (bool) @0x10; `.spriteExt` (string) @0x18.
- `ShoreLineContainer.north` @0x20, `.south` @0x28, `.east` @0x30, `.west` @0x38, `.originalSpriteNames` (string[]) @0x40.

## 3. Sprite selection
Per visible edge `dir` the sprite name = `originalSpriteNames[dirIndex] + spriteExt`,
assigned via `UpdateSprite` (0x2CD8F6C, calls `String.Concat` at 0x27667B0 then sets the
renderer's sprite from the SpriteAtlas). `originalSpriteNames` is a **serialized prefab
field** (not in code); the catalog confirms the base art is **`shoreline`**, and the only
runtime `spriteExt` values are `""` and `"_swamp"`. Therefore the concrete filenames this
code path produces are:

| Condition (neighbour land tile) | spriteExt | Sprite filename | In catalog? |
|---|---|---|---|
| normal land neighbour | `""` | `shoreline` | YES (128×33) |
| neighbour skin==Swamp(17) OR neighbour has Swamped effect | `_swamp` | `shoreline_swamp` | YES (128×33) |

Confirmed present in `pyrender/sprite_catalog.json`: `shoreline` {w:128,h:33},
`shoreline_swamp` {w:128,h:33}.

The selection of `_swamp` vs default is decided **from the neighbour (land) tile**, inside
`UpdateShorelineFromNeighbourtile` (0x7FEBB8): `spriteExt = (neighbour.skin==17 ||
neighbour.HasEffect(Swamped)) ? "_swamp" : ""`. (Branch: `cmp [tile+0x20],#0x11`/`HasEffect`
→ store swamp-string ptr else default-string ptr into `shoreline.spriteExt`.)

There is a single base sprite for all four directions; the prefab's four child renderers
each carry the same `shoreline` art placed/oriented for their edge (see Geometry). NOTE:
`shoreline_deep` / `shoreline_deep_swamp` exist in the catalog but are **NOT** emitted by
this container — they belong to `TerrainRenderer.WaterSpriteData` (oceanSprites/waterSprites,
dump.cs 418378-418403), i.e. the deep-water edge against shallow water rendered by the
terrain slice, out of scope here. Flagged in Open Questions.

## 4. Geometry
- Owner: prefab component `ShoreLineContainer` on each `Tile` GameObject (Tile @0x70),
  parented under the tile, so positioning is **relative to the tile's world position**
  `MapExtensions.ToPosition(coords)` (posX=(x−y)*0.4811, posY=(x+y)*0.288).
- Four child `PolytopiaSpriteRenderer`s (north/south/east/west). Each carries the SAME base
  art (`shoreline`, 128×33 px) but a fixed prefab transform (position + rotation/flip) for
  its edge. The exact child transforms are serialized in the Unity prefab and are **not in
  the binary** — implementer must place one shoreline strip along each of the four iso edges
  of the diamond tile (NE/SE/SW/NW screen edges), centered on the tile, with the per-edge
  rotation that the four-direction naming implies. Treat the base strip as the top/north
  edge and rotate/mirror for the other three (best-effort; see Open Questions).
- Sub-depth / sort: `ShoreLineContainer.set_Depth` (0x2CD967C) sets the **same**
  `SortingOrder` (`PolytopiaSpriteRenderer.set_SortingOrder` 0x2CD6CFC) on all four
  renderers — shorelines are one flat layer. They draw **above base terrain** and below
  resources/improvements. In the Part E.3 sub-layer table this maps to the low band
  (terrain=1 .. terrain-features=3); precise offset value is set by the prefab, not by
  `Tile.Render` (no explicit `set_Depth` call observed inside Tile.Render 0x2CDC5DC–0x2CDE0FC).
- No per-edge flip is applied at runtime; any mirroring is baked into the prefab transform.

## 5. Algorithm
### Precompute (once per map; mirrors `GenerateShoreLines` 0x7FEC78)
```
for each tile t at index i = y*width + x:        # width = map.width @[map+0x10]
    t.shorelines.ResetAll()                      # any=false, all 4 visible=false
    if t.terrain != Water(1):      continue      # gate: only Water tiles
    if t.IsFrozen:                 continue       # IsFrozen = terrain==Ice(6) OR (terrain==Water AND climate==15)
    s = t.shorelines
    # N  <- neighbour at i + width   (y+1)         [stored to s.N @0x18]
    if y+1 < height:  setEdge(s.N, tile[i+width])
    # S  <- neighbour at i - width   (y-1)         [stored to s.S @0x20]
    if y   >  0    :  setEdge(s.S, tile[i-width])
    # W  <- neighbour at i - 1       (x-1)         [stored to s.W @0x30]
    if (i % width) != 0:  setEdge(s.W, tile[i-1])
    # E  <- neighbour at i + 1       (x+1)         [stored to s.E @0x28]
    if (i % width) != (width-1): setEdge(s.E, tile[i+1])
    s.any = (s.N.visible | s.S.visible | s.E.visible | s.W.visible)

def setEdge(shoreEdge, neighbour):               # UpdateShorelineFromNeighbourtile 0x7FEBB8
    shoreEdge.visible  = neighbour.IsLand        # terrain in {Field,Mountain,Forest,Ice}
    shoreEdge.spriteExt = "_swamp" if (neighbour.skin==Swamp(17)
                                       or neighbour.HasEffect(Swamped)) else ""
```
Index/neighbour mapping confirmed by disasm of GenerateShoreLines:
`i+width`→`[shorelines+0x18]`=N, `i-width`→`[+0x20]`=S, `i-1`→`[+0x30]`=W, `i+1`→`[+0x28]`=E.
(Bounds: `i-width` block guarded by `i>width`; `i+width` by `i<width*(h-1)`; `i-1` by `i%width!=0`;
`i+1` by `i%width < width-1`.)

### Render (mirrors `RenderShorelines` 0x2CDEB78 + ShowN/S/E/W)
```
RenderShorelines(tile, explored):
    tile.isDirty = true
    s = tile.data.shorelines
    if s == null or s.any == false:
        shoreContainer.gameObject.SetActive(false); return    # hide all
    shoreContainer.gameObject.SetActive(explored)             # fog gate
    ShowEdge(north, 0, s.N)
    ShowEdge(south, 1, s.S)
    ShowEdge(east,  2, s.E)
    ShowEdge(west,  3, s.W)

ShowEdge(renderer, dirIndex, shore):                          # ShowN/S/E/W
    renderer.gameObject.SetActive(shore.visible)
    if shore.visible:
        UpdateSprite(renderer, dirIndex, shore.spriteExt)     # sprite = originalSpriteNames[dirIndex] + spriteExt
```
For the Python renderer: on each non-frozen Water tile, for each of the 4 edges whose
land-neighbour test passes, paste `shoreline` (or `shoreline_swamp`) along that iso edge,
oriented per direction, at sort order just above terrain. Skip entirely if the tile is fogged
(`explored==false`) or `any==false`.

## 6. Tint/color
None specific to shorelines. `ShowN/S/E/W` and `UpdateSprite` set only the sprite name and
SetActive; no `set_Color`/outline/opacity call is made in this path. The shoreline strips
inherit the renderer's default white tint and the shared tile material. (No per-player tint —
shorelines are terrain decoration, not owned.)

## 7. RVAs verified
- `Tile$$RenderShorelines` 0x2CDEB78 — sets isDirty; reads data→shorelines→any; SetActive(container, explored); calls ShowN/S/E/W with shorelines.N/S/E/W (args `[+0x18]/+0x20/+0x28/+0x30`).
- `ShoreLineContainer$$ShowN` 0x2CD94CC — SetActive(north, shore.visible); if visible → UpdateSprite(north, index 0, shore.spriteExt).
- `ShoreLineContainer$$ShowS` 0x2CD9538 — south, index 1.
- `ShoreLineContainer$$ShowE` 0x2CD95A4 — east, index 2.
- `ShoreLineContainer$$ShowW` 0x2CD9610 — west, index 3.
- `ShoreLineContainer$$UpdateSprite` 0x2CD8F6C — name = String.Concat(originalSpriteNames[index], ext) (Concat @0x27667B0), then sets renderer sprite from atlas.
- `ShoreLineContainer$$set_Depth` 0x2CD967C — same SortingOrder on all four renderers (set_SortingOrder @0x2CD6CFC).
- `MapDataExtensions$$GenerateShoreLines` 0x7FEC78 — per-tile loop; ResetAll; Water-only + not-frozen gate; 4-neighbour edge assignment (N=i+w, S=i−w, W=i−1, E=i+1); sets shorelines.any.
- `MapDataExtensions$$UpdateShorelineFromNeighbourtile` 0x7FEBB8 — visible=neighbour.IsLand; spriteExt = swamp if neighbour.skin==17 or HasEffect(Swamped) else "".
- `TileData$$get_IsLand` 0x7DCBC4 — `(uint)(terrain-3) < 4` ⇒ {Field,Mountain,Forest,Ice}.
- `TileData$$IsFrozen` 0x7D9E3C — terrain==Ice(6) OR (terrain==Water(1) AND climate==15).
- `TileData$$HasEffect` 0x7D9BA4 — checks effects list for given EffectType (Swamped=2).

## 8. Open questions / risks
- **Per-direction prefab transforms unknown.** `originalSpriteNames[0..3]` and the four child
  renderers' positions/rotations/flips live in the Unity prefab, not the binary. I confirmed
  the runtime ext logic and that the base art is `shoreline`, but the exact pixel offset and
  orientation of each of the four edge strips (and whether some directions use a flipped/
  rotated copy of the single 128×33 sprite) must be derived from the prefab or matched
  visually against reference frames. Risk: implementer may need to hand-tune the 4 edge
  placements.
- **`originalSpriteNames` base values.** Assumed all four = `"shoreline"` (catalog has exactly
  one base + `_swamp`). If any direction's serialized base differs (e.g. a `_deep` variant),
  that is not visible in the dump. Low risk given catalog only has `shoreline`/`shoreline_swamp`
  for this container.
- **`shoreline_deep` / `shoreline_deep_swamp`** (catalog) are NOT produced here — they are
  `TerrainRenderer.WaterSpriteData` (ocean vs shallow-water edge), belonging to the terrain
  slice. Coordinate with that slice so deep-water coast isn't double-drawn.
- **Sort offset exact value** for the shoreline layer is set by the prefab (no `set_Depth`
  call seen in `Tile.Render`); confirmed only that it is a single flat layer above terrain.
  Use the Part E.3 band (≈terrain..terrain-features, offsets 1–3) and verify visually.
- **Wetland(7)/Mangrove(8)** neighbours do NOT trigger a shoreline (not in IsLand range), and
  the center tile must be Water(1) — Ocean(2) tiles never get shorelines. Confirmed by disasm.
- Coordinate convention: index `i=y*width+x`; verify against the chosen MapData row/column
  ordering in the implementation (matches ToPosition's packed low32=x/high32=y).
