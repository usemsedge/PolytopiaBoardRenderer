# Slice: Territory Borders

## 1. Summary
Each owned tile draws up to four territory-border edge sprites — one per
**grid** direction (N, E, S, W) — but only on the edges where the orthogonal
neighbour tile has a **different owner** (or is off-map / unowned). The four
edges are split across two depth layers: the N+E edges go to the **back** layer
(tile sub-depth +0, "borders back"), and the S+W edges go to the **front** layer
(tile sub-depth +99, "borders front"). All four edges share a single white art
sprite per axis (`BorderXGFX` / `BorderYGFX`, tinted at draw time). The whole
border is tinted to the owning player's RGB colour; the two "side" edges
(E and W) are additionally darkened to 50.2% RGB to fake the isometric shading.
Unowned tiles (`owner == 0`) draw no borders.

## 2. Constants
| Constant | Decoded value | Source |
|----------|---------------|--------|
| Border side-edge darken multiplier | `0x3F008081` = **0.50196** (= 128/255), applied to RGB of E & W edges only | SetColor @0x2CD68BC (`fmul s,s,0x3F008081`) |
| Player-colour normaliser | `0x437F0000` = **255.0** (divisor for each channel) | GetPlayerColor @0x2CA790C-0x2CA7934 |
| Border alpha | **1.0** (constant; `fmov s3, #1.0`) | GetPlayerColor @0x2CA7938 |
| Front-layer depth offset | **+99** (`add w1, w8, #0x63`) added to base depth for S & W edges | BorderContainer.set_Depth @0x2CD6CD4 / @0x2CD6CE4 |
| Back-layer depth offset | **+0** (base depth) for N & E edges | BorderContainer.set_Depth @0x2CD6CB4 / @0x2CD6CC0 |
| `DEPTH_INCREASE_PER_ROW` | 100 (`madd w0, (x+y), -100, mapHeight`) | GetDepthForTile @0x2D50804-0x2D50808; MapRenderer (dump.cs ~371960) |
| Tile base depth | `depth = mapHeight - 100*(x+y)` | GetDepthForTile @0x2D507A4 |
| GridDirectionFlag bits | SW=1, W=2, NW=4, N=8, NE=16, E=32, SE=64, S=128 | dump.cs L774981 |
| GridDirection | SW=0,W=1,NW=2,N=3,NE=4,E=5,SE=6,S=7,NONE=8 | dump.cs L774964 |
| `TileData.owner` offset | 0x34 (byte) | dump.cs L774616 |
| `PlayerState.Id` offset | 0x10 (byte) | dump.cs L776693 |
| `PlayerState.color` offset | 0xC0 (int, packed 0x00RRGGBB) | dump.cs L776725 |
| `PlayerState.NO_PLAYER_ID` | 0 | dump.cs L776690 |

## 3. Sprite selection
Borders use only **two** art sprites, both confirmed present in
`pyrender/sprite_catalog.json`:

| Sprite file | Size | Role |
|-------------|------|------|
| `BorderXGFX.png` | 128×102 | One isometric axis edge (diagonal running upper-right → lower-left) |
| `BorderYGFX.png` | 128×102 | Other isometric axis edge (mirror of X: upper-left → lower-right) |

Both are solid **white** RGBA art meant to be colour-tinted at draw time (verified
by rendering the alpha/colour: only white pixels along a diagonal stripe).

The 4 `BorderContainer` sprite renderers (`northBorder`/`eastBorder`/
`southBorder`/`westBorder`, dump.cs L418076-418082) each carry one of these two
sprites, set in the Unity **prefab** (not in code, so the exact per-renderer
assignment is not recoverable from disassembly). Based on the two-sprite catalog
and the isometric layout, the strong inference (mark as **inference**) is:
- One axis sprite + its horizontal flip covers the two edges of that axis.
- N and S share one axis art; E and W share the other (N/S are the y-axis pair,
  E/W the x-axis pair) — the renderer whose direction points "down-screen" uses
  the horizontally/vertically flipped copy.

There is **no** separate "selected vs unselected" border sprite for territory —
the `Border_*` / `NoBorder_*` sprites in the catalog (29 + 30 entries) are
**gamepad button-prompt UI icons** (`Border_A`, `Border_PS_X`, `Border_Xbox_LB`,
etc.), NOT territory borders. Do not use them for this layer.

## 4. Geometry
- One `BorderContainer` per `Tile`, anchored at the tile's world position
  `ToPosition(x,y) = ((x−y)*0.4811, (x+y)*0.288)` (+ TILE_VERTICAL_OFFSET handled
  by the terrain/tile layer). The four edge renderers are positioned/oriented in
  the prefab so each lies along one diamond edge of the tile.
- **Direction → grid neighbour** (confirmed; WorldCoordinates ctor stores x@0,y@4,
  RenderBorder @0x2CDDC80-0x2CDD24):
  - **N** (flag 8)  → neighbour (x,   y+1) → `northBorder`
  - **S** (flag 128) → neighbour (x,   y−1) → `southBorder`
  - **E** (flag 32) → neighbour (x+1, y)   → `eastBorder`
  - **W** (flag 2)  → neighbour (x−1, y)   → `westBorder`
  (Grid-space, not screen-space. In iso projection +y is up-left, +x is up-right,
  so N maps to the upper-left screen edge and E to the upper-right screen edge.)
- **Depth split** (BorderContainer.set_Depth @0x2CD6C98, base = tile depth `d`):
  - `northBorder` depth = `d`     (back, sub-offset 0)
  - `eastBorder`  depth = `d`     (back, sub-offset 0)
  - `southBorder` depth = `d+99`  (front, sub-offset 99)
  - `westBorder`  depth = `d+99`  (front, sub-offset 99)
  Back-layer list = {north, east} (GetBackSpriteRenderers @0x2CD65DC adds fields
  0x28 then 0x30); front-layer list = {south, west} (GetFrontSpriteRenderers
  @0x2CD674C adds 0x38 then 0x40). This matches the global sort table: 0 =
  borders-back (below terrain), 99 = borders-front (above buildings).
- **Flip**: flips are encoded in the prefab transform / `MeshDescription.flip`,
  not in the disassembled border methods. Implementer should derive flips so the
  two diagonal art sprites cover all four diamond edges (see §3 inference).

## 5. Algorithm
Per tile (pseudocode, directly from Tile.RenderBorder @0x2CDDB54 and
BorderContainer.Render/SetColor/set_Depth):
```
RenderBorder(tile):
    tile.isDirty = true
    owner = tile.get_Owner()            # = TryGetPlayer(tile.data.owner); null if owner==0
    bc = tile.border                    # BorderContainer (Tile field 0x50)
    if owner == null or bc == null:
        bc.Render(directions = 0)       # all 4 edge GameObjects -> SetActive(false)
        return
    color = GetPlayerColor(owner)       # see §6
    bc.SetColor(color)                  # tints the 4 edge renderers (see §6)
    if tile.IsHidden:                   # fog: skip neighbour test, draw nothing
        bc.Render(0)
        return
    map = GameManager.GameState.Map
    me  = owner.Id                      # byte
    x, y = tile.coordinates
    nN = map.GetTile(x,   y+1)
    nS = map.GetTile(x,   y-1)
    nE = map.GetTile(x+1, y)
    nW = map.GetTile(x-1, y)
    dirs = 0
    if nN == null or nN.owner != me: dirs |= 8     # N
    if nS == null or nS.owner != me: dirs |= 128   # S
    if nE == null or nE.owner != me: dirs |= 32    # E
    if nW == null or nW.owner != me: dirs |= 2     # W
    bc.Render(dirs)

BorderContainer.Render(dirs):          # @0x2CD653C
    northBorder.gameObject.SetActive( (dirs>>3)&1 )   # N bit
    eastBorder .gameObject.SetActive( (dirs>>5)&1 )   # E bit
    southBorder.gameObject.SetActive( (dirs>>7)&1 )   # S bit
    westBorder .gameObject.SetActive( (dirs>>1)&1 )   # W bit
```
Depth assignment happens via `Tile.set_Depth(d)` → `BorderContainer.set_Depth(d)`
(N,E = d ; S,W = d+99), independent of which edges are visible.

## 6. Tint / colour
- **Source colour** (GetPlayerColor @0x2CA78FC): from `PlayerState.color` (int @0xC0),
  packed `0x00RRGGBB`:
  - `r = ((color >> 16) & 0xFF) / 255`
  - `g = ((color >>  8) & 0xFF) / 255`
  - `b = ( color        & 0xFF) / 255`
  - `a = 1.0`
  (If player is null the call returns the default/empty colour and no border is drawn.)
- **Application** (BorderContainer.SetColor @0x2CD68BC), given owner colour (r,g,b,a):
  - `northBorder.Color = (r, g, b, a)`        — full colour
  - `southBorder.Color = (r, g, b, a)`        — full colour
  - `eastBorder.Color  = (r*0.50196, g*0.50196, b*0.50196, a)`  — darkened
  - `westBorder.Color  = (r*0.50196, g*0.50196, b*0.50196, a)`  — darkened
  i.e. the two **east/west (x-axis)** edges are multiplied by **128/255 = 0.50196**
  on RGB only (alpha unchanged); north/south keep the pure owner colour. This is a
  flat darken (no per-pixel saturation/HSV change). The white art means the final
  pixel = `sprite_rgb(=255) * tint = tint` (standard multiply tint).
- No outline, no opacity/fade applied here (alpha is hard 1.0).

## 7. RVAs verified
- `Tile.RenderBorder` 0x2CDDB54 — owner lookup, IsHidden gate, 4-neighbour
  owner comparison building the direction flag (bits 8/128/32/2), calls SetColor
  then Render. Confirmed neighbour offsets (x,y±1)/(x±1,y) and flag values.
- `BorderContainer.Render` 0x2CD653C — maps flag bits to
  north(bit3)/east(bit5)/south(bit7)/west(bit1) `gameObject.SetActive`.
- `BorderContainer.SetColor` 0x2CD68BC — N/S get full colour, E/W get RGB×0.50196
  (immediate 0x3F008081); alpha preserved; calls PolytopiaSpriteRenderer.set_Color.
- `BorderContainer.set_Depth` 0x2CD6C98 — N/E = base depth, S/W = base+99.
- `BorderContainer.GetBackSpriteRenderers` 0x2CD65DC — back list = {north, east}.
- `BorderContainer.GetFrontSpriteRenderers` 0x2CD674C — front list = {south, west}.
- `BorderContainer.ShowBorder` 0x2CD6ABC — alt per-direction predicate: false if
  tile unowned (owner==0); else neighbour.owner != tile.owner (`cset ne`). Confirms
  the "different owner = draw" rule independently.
- `Tile.set_Depth` 0x2CE1C84 — passes the tile base depth to BorderContainer.set_Depth
  (border field 0x50) with no extra offset (sub-offset 0).
- `Tile.get_Owner` 0x2CD74FC — resolves `tile.data.owner` (byte 0x34) via TryGetPlayer;
  returns null when id not found (owner 0 ⇒ no borders).
- `MapRenderer.GetDepthForTile` 0x2D507A4 — base depth = `mapHeight − 100*(x+y)`.
- `ClientPlayerExtensions.GetPlayerColor` 0x2CA78FC — unpacks PlayerState.color
  (0x00RRGGBB)/255, alpha=1.0.
- Helper symbols confirmed via re_tools: WorldCoordinates.ctor 0x82FF10
  (stores x@0, y@4), MapDataExtensions.GetTile 0x7F0974,
  GameObject.SetActive 0x38BC72C, Component.get_gameObject 0x38B8918.
- String literals `BorderXGFX` (0x49020C0) and `BorderYGFX` (0x49020C8) present in
  stringliteral.json; both PNGs exist (128×102) and are confirmed in sprite_catalog.json.

## 8. Open questions / risks
- **Per-renderer sprite + flip assignment is NOT in code** — it lives in the Tile
  prefab serialization (the 4 `[SerializeField] PolytopiaSpriteRenderer` fields).
  We confirmed only two art sprites exist (`BorderXGFX`, `BorderYGFX`) and that
  `BorderYGFX` is the horizontal mirror of `BorderXGFX`. The exact mapping
  {north,east,south,west} → {sprite, flipX/flipY} is an **inference**; an
  implementer should empirically pin it against a reference screenshot (e.g.
  N/S use BorderYGFX, E/W use BorderXGFX, with the down-screen edge flipped).
- **Pivot/exact pixel offset** of each edge relative to the tile centre is set in
  the prefab; not disassembled. Sprites are 128×102 (larger than a half-tile),
  so they overhang the tile edge — verify placement against a screenshot.
- The darken applies to **E and W** specifically (the x-axis pair). Confirm which
  screen edges these correspond to after fixing the sprite/flip mapping; the
  darkening is meant to shade the two "side/far-right & far-left" faces.
- `IsHidden` (fog) suppresses borders this frame; the fog/visibility slice owns
  the exact IsHidden semantics — borders just early-out to `Render(0)`.
- Diagonal neighbours (NE/NW/SE/SW) are **not** consulted; borders are purely the
  4 orthogonal-grid edges. No corner/diagonal border sprites are used.
