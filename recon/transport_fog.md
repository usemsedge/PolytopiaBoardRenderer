# Slice: transport_fog — Transport (roads/routes/bridges) + Fog of War

## 1. Summary
A tile's `TransportContainer` (Tile field `transport` @0x58) draws up to 8 directional
road/route segments, one per `GridDirection` (SW..S = indices 0..7). For each direction it
calls `ShouldShow(dir)`: a segment is drawn only if **this** tile has a transport path
(`HasRoad` for roads, or `hasRoute` for routes) **and** the neighbour tile in that direction
also has a matching transport path (`TileData.HasMatchingTransportPath`). The chosen sprite is
`roads000{dir}` for a road or `routes000{dir}` for a route (optionally a skin suffix like
`routes000{dir}_magma`), drawn at sub-depth `tileDepth + 2` (the "transport / world object"
layer). Bridges are NOT transport sprites — they are improvements (`ImprovementData.Type
Bridge = 48`) rendered by the `Bridge`/`Building` improvement renderer using one of two
pre-built children, `bridge` (vertical, NW–SE) or `bridge-flipped` (horizontal, NE–SW),
selected by `ImprovementState.level == 1 ? horizontal : vertical`; `HasRoad` treats a Bridge
tile as having a road so transport segments connect through it. Fog of war: a tile is hidden
when the local player has not explored it (`Tile.IsHidden = !TileData.GetExplored(localPlayer.id)`);
a hidden tile hides its terrain renderer and instead shows the single `hidden` sprite via the
prefab's `fogOfWarRenderer`. There are no cloud sprites in the catalog — fog is the one
`hidden` sprite, not per-edge clouds or a darkening tint.

## 2. Constants
| Constant | Value | Source |
|----------|-------|--------|
| Transport sub-depth offset | **+2** added to tile depth | `CreateRoad` @0x2CE2C04–0x2CE2C10: `SortingOrder = depth(field 0x44) + 2`. Matches Part E.3 "Transport / world object" = 2. |
| Road base name | `"roads000"` | string-literal slot 0x49274B0 (decoded via stringliteral.json) |
| Route base name | `"routes000"` | string-literal slot 0x4927670 |
| Skin separator | `"_"` | string-literal slot 0x491AC60, used by `Concat(base+dir, "_", skin)` |
| `TransportType.Road` | 0 | dump.cs:418835 |
| `TransportType.Route` | 1 | dump.cs:418836 |
| `GridDirection` SW..S | SW=0,W=1,NW=2,N=3,NE=4,E=5,SE=6,S=7,NONE=8 | dump.cs:774964-774977 |
| `ImprovementData.Type City` | 1 | dump.cs:783590 |
| `ImprovementData.Type Bridge` | 48 (0x30) | dump.cs:783637 |
| `ImprovementData.Type Port` | 8 | dump.cs:783597 |
| Bridge horizontal flag | `ImprovementState.level (0x16) == 1` | `GetIsBridgeHorizontal` @0x7EBFBC: type==0x30 then `(level==1)`; `SetIsBridgeHorizontal` @0x7EC0F4 stores `isHorizontal?1:0` into level (0x16). |
| Player "no fog" id | `0xFF` (255) → always explored | `GetExplored` @0x7D3418: `playerId==0xFF` → return 1 |
| Tile depth formula | `depth = map[0x12] - (x + y) * 100` | `GetDepthForTile` @0x2D50800-0x2D50808: `madd w0,(x+y),-100,w20`, `w20 = map.ushort@0x12`. (Per-row step magnitude = DEPTH_INCREASE_PER_ROW = 100, sign negative.) |
| Feature outline tint (forest/mountain hidden-pass) | ARGB `0x7FF3F3F3` ÷ 255 | RenderTerrain @0x2CDC9A0-0x2CDCA24 (NOT a fog constant; see §6). |
| `hidden` sprite size | 429×454 | pyrender/sprite_catalog.json |
| `roads000N` / `routes000N` size | 18×87 | sprite_catalog.json |
| `bridge` / `bridge-flipped` size | 234×220 / 234×219 | sprite_catalog.json |

## 3. Sprite selection
### Roads / Routes (TransportContainer)
For each `dir` in 0..7 where `ShouldShow(dir)` returns true:
- name base = `type == Road(0) ? "roads000" : "routes000"`  (`UpdateRoadInDirection` @0x2CE27B0: `csel` between slots 0x49274B0/0x4927670 keyed on `type==0`).
- name = `Concat(base, dir.ToString())` (`Int32.ToString` @0x2CE27D8 of the direction index, `String.Concat` @0x2CE27E8) → e.g. `roads0003`, `routes0005`.
- optional skin: if the tile's visual skin (`Tile.GetVisualSkinTypeForTile` @0x2CE0A28) has a game skin (`GameSkin.get_HasGameSkin`), append `"_" + skinName` → e.g. `routes0000_magma`.
- final sprite via `SpriteAtlasManager.DoSpriteLookup` (@0x2CE2990) then `PolytopiaSpriteRenderer.set_Sprite`.

Concrete confirmed filenames (all present in sprite_catalog.json):
`roads0000, roads0001, roads0002, roads0003, roads0004, roads0005, roads0006, roads0007` (8);
`routes0000..routes0007` and `routes0000_magma..routes0007_magma` (16). Standalone `Road`
(128×106) also exists in the catalog but is the improvement-icon sprite, not a transport segment.

### Bridge (improvement layer, for reference)
`ImprovementState.level == 1` → child `bridge-flipped` active (horizontal / NE–SW);
else child `bridge` active (vertical / NW–SE). Sprites: `bridge`, `bridge-flipped`
(and skin variants `bridge_ikarus`, `bridge-flipped_ikarus`) — all confirmed in catalog.
`Bridge.SetVisible` @0x2CC8788-0x2CC87A4: `bridge.SetActive(!horiz); bridgeFlipped.SetActive(horiz)`.

### Fog of war
Single sprite **`hidden`** (429×454), pre-assigned to the prefab's `fogOfWarRenderer`
(`Tile` field @0x40). `TILE_UNKNOWN = "hidden"` constant at dump.cs:374197. No cloud/`clouds`
sprite exists in the catalog; fog is this one sprite shown in place of terrain.

## 4. Geometry
### Roads / Routes
- Each segment is a child `PolytopiaSpriteRenderer` GameObject created by `CreateRoad`
  (@0x2CE2A1C). Its localPosition / localRotation / localScale are copied from a template
  config object (static slots read at 0x2CE2AFC/0x2CE2B48/0x2CE2BA0) — i.e. fixed transform
  values, NOT a per-direction rotation. The directional appearance comes entirely from the
  pre-drawn art in `roads000N` / `routes000N` (each of the 8 sprites already points the
  correct way). For the implementer: paste sprite `{base}{dir}` at the tile's world anchor
  (same anchor as terrain), with no rotation/flip applied beyond what the sprite encodes.
- Anchor/pivot: same tile world position as terrain (the container is parented to the Tile).
  Segments share the tile origin; do not flip_x. (The 8 distinct sprites cover all 8 edges.)
- Sub-depth: SortingOrder = `tileDepth + 2` (`CreateRoad` @0x2CE2C04). This places transport
  above terrain (sub-depth 1) and below terrain-features (3), per Part E.3. Use the same row
  depth as the tile: `mapConst - (x+y)*100`, then `+2`.

### Bridge
- Two fixed children at the tile center; pick one by orientation (see §3). They live in the
  improvement layer (sub-depth ~98 "Buildings"), not transport. NW–SE = `bridge`,
  NE–SW = `bridge-flipped`.

### Fog
- `fogOfWarRenderer` is a single sprite at the tile center, same anchor as terrain. When a
  tile is hidden the terrain renderer's GameObject is deactivated and `fogOfWarRenderer`'s
  GameObject is activated (RenderTerrain @0x2CDCAFC-0x2CDCB28). No offset/flip; sub-depth is
  the terrain slot (the fog sprite simply replaces the terrain sprite at the tile origin).

## 5. Algorithm
```
# ---- TransportContainer.Render (RVA 0x2CDF120) ----
def transport_render(tile, gamestate, localPlayer):
    container = tile.transport
    anyShown = False
    for dir in range(len(container.lines)):          # lines length = 8 (SW..S)
        shown, type = ShouldShow(container, dir, gamestate, localPlayer)
        anyShown |= shown
        UpdateRoadInDirection(container, dir, type, shown)
    # (remaining body handles container visibility cleanup; not pixel-relevant)

# ---- ShouldShow (RVA 0x2CE2388) ----
def ShouldShow(container, dir, state, localPlayer):
    t = container.tile.data
    type = Road if t.HasRoad else Route          # out param: type = !HasRoad
    if not t.HasRoad:                            # route path: gated by visibility + opener
        if not container.visible:        return (False, type)
        if not t.IsRouteOpener(state):
            if not t.HasRoad:            return (False, type)   # (route opener required)
    neighborCoord = t.coordinates + GridDirections.ToCoordinates(dir)
    nb = MapDataExtensions.GetTile(state.Map, neighborCoord)
    if nb is None:                       return (False, type)
    return (t.HasMatchingTransportPath(nb, state), type)

# TileData.HasRoad  (get_HasRoad RVA 0x7DC600)
def HasRoad(t):
    return t.hasRoad or (t.improvement and t.improvement.type in (City=1, Bridge=48))

# TileData.IsConnectable (RVA 0x7DB5A4) — used by HasMatchingTransportPath
def IsConnectable(t, state):
    if t.hasRoad: return True
    if t.improvement and (t.improvement.type == City(1) or
                          ImprovementData(t.improvement).IsRouteOpener): return True
    return False

# TileData.HasMatchingTransportPath(self, other, state)  (RVA 0x7DB4C4)
def HasMatchingTransportPath(a, b, state):
    # owners must match (or one unowned) unless same player path
    if not (a.owner == 0 or a.owner == b.owner):
        ruling = state.GetCityFor(...) ; if cross-owner blocked: skip road branch
    if a.IsConnectable(state) and b.IsConnectable(state):   # both road-connectable
        return True
    if a.hasRoute and b.hasRoute:                           # both routes (water)
        return True
    return False

# ---- CreateRoad (RVA 0x2CE2A1C) builds one segment child ----
def UpdateRoadInDirection(container, dir, type, shouldShow):
    line = container.lines[dir]
    if line is None and shouldShow:
        line = CreateRoad(container)          # instantiate child PolytopiaSpriteRenderer
        container.lines[dir] = line
    if line is None: return
    line.gameObject.SetActive(shouldShow)
    if not shouldShow: return
    base = "roads000" if type == Road else "routes000"
    name = base + str(dir)
    skin = GetVisualSkinTypeForTile(container.tile)
    if skin and GameSkin.HasGameSkin(skin):
        name = name + "_" + skinName(skin)         # e.g. routes0003_magma
    sprite = SpriteAtlasManager.DoSpriteLookup(name)
    line.set_Sprite(sprite)
    # SortingOrder set in CreateRoad = container.depth + 2

# ---- Fog of war, inside Tile.RenderTerrain (RVA 0x2CDC828) ----
def render_terrain_fog(tile):
    hidden = tile.IsHidden                        # = not data.GetExplored(localPlayer.id)
    tile.terrainRenderer.gameObject.SetActive(not hidden)
    tile.fogOfWarRenderer.gameObject.SetActive(hidden)     # shows the "hidden" sprite
    tile.RenderShorelines(explored = not hidden)
    if hidden:
        return                                    # skip sway/fog-tween bookkeeping

# Tile.IsHidden (RVA 0x2CDA6D4)
def IsHidden(tile):
    if IsReplay and ReplayEnableFog:              # replay-only branch (ReplaySharedFog)
        ...                                       # uses shared/replay explorer set
    lp = GameManager.LocalPlayer
    if lp is None: return False
    return not tile.data.GetExplored(lp.id)       # GetExplored: id==0xFF -> always True
```
Note for the renderer: `RenderTerrain`, `RenderResource`, `RenderImprovement`, `RenderUnit`,
`RenderBorder` are all invoked *before* `IsHidden` is consulted in `Tile.Render`
(0x2CDC6AC..0x2CDC6E8), but `RenderTerrain` itself swaps terrain→fog when hidden, and
transport `Render` is only called for the non-hidden / explored path. For a from-scratch
renderer the simplest faithful rule is: **if hidden, draw only the `hidden` sprite at the tile
origin and nothing else for that tile; otherwise draw terrain + transport + the rest.**

## 6. Tint / color
- Roads/routes: no per-player tint or outline applied in `CreateRoad`/`UpdateRoadInDirection`;
  `set_Color` is not called on the segment — the sprite is drawn at full opacity, untinted.
  (Color comes only from the sprite art.)
- Fog `hidden` sprite: drawn untinted at full opacity — it fully replaces the terrain sprite.
  There is **no** darkening multiply or per-edge cloud blend; the game does not tint explored
  terrain for fog, it shows a distinct opaque sprite.
- The only color math in `RenderTerrain` is for the **forest/mountain feature** renderers
  (offsets 0x28/0x30/0x38), not fog or transport: when the feature should be dimmed the code
  uses packed ARGB `0x7FF3F3F3` (a≈0.5, rgb≈0.953) else white `0xFFFFFFFF`, each channel ÷255
  (0x437F0000 = 255.0f), via `set_Color` @0x2CD6978. Out of this slice's scope but recorded so
  the implementer does not mistake it for a fog tint.

## 7. RVAs verified
- `TransportContainer.Render` 0x2CDF120 — loops `lines[0..len]`, calls ShouldShow + UpdateRoadInDirection per direction; OR-accumulates "anyShown".
- `TransportContainer.ShouldShow` 0x2CE2388 — `type=!HasRoad`; neighbor = coords + GridDirections.ToCoordinates(dir); returns `HasMatchingTransportPath(neighborTile)`. Confirmed callees: get_HasRoad, IsRouteOpener, GridDirections.ToCoordinates, WorldCoordinates.op_Addition, MapDataExtensions.GetTile, HasMatchingTransportPath.
- `TransportContainer.UpdateRoadInDirection` 0x2CE25C8 — selects `roads000`/`routes000` literal via `csel` on type==0, `Concat`s direction index, appends skin, `DoSpriteLookup`, `set_Sprite`; `SetActive(shouldShow)`.
- `TransportContainer.CreateRoad` 0x2CE2A1C — instantiates child, copies localPosition/localScale/localRotation from template, `set_SharedMaterial`, `set_SortingLayer`, `set_SortingOrder = depth + 2`.
- `TransportContainer.SetVisible` 0x2CDF02C — sets `visible(0x40)`, toggles each `lines[]` GameObject active.
- `TileData.get_HasRoad` 0x7DC600 — `hasRoad || improvement.type==1(City) || ==48(Bridge)`.
- `TileData.HasMatchingTransportPath` 0x7DB4C4 — owner check then `(IsConnectable&&IsConnectable) || (hasRoute&&hasRoute)`.
- `TileData.IsConnectable` 0x7DB5A4 — `hasRoad || improvement is City/route-opener`.
- `string slots` 0x49274B0="roads000", 0x4927670="routes000", 0x491AC60="_" (stringliteral.json).
- `ImprovementState.GetIsBridgeHorizontal` 0x7EBFBC — type==0x30 then `level(0x16)==1`.
- `ImprovementState.SetIsBridgeHorizontal` 0x7EC0F4 — stores `isHorizontal?1:0` into level(0x16).
- `Bridge.SetVisible` 0x2CC8758 — `bridge.SetActive(!horiz); bridgeFlipped.SetActive(horiz)` (children @0x60/0x68).
- `Tile.get_IsHidden` 0x2CDA6D4 — replay-fog branch + main path `!GetExplored(LocalPlayer.id)`. Callees: GameManager.get_Client, ClientBase.get_IsReplay, SettingsUtils.get_ReplayEnableFog/ReplaySharedFog, GameManager.get_LocalPlayer, GetExplored.
- `TileData.GetExplored` 0x7D33D4 — `id==0xFF → true`, else explorers-list contains id.
- `Tile.RenderTerrain` 0x2CDC828 — `terrainRenderer.SetActive(!hidden)`, `fogOfWarRenderer(0x40).SetActive(hidden)`, `RenderShorelines(!hidden)`, early-return when hidden.
- `MapRenderer.GetDepthForTile` 0x2D507A4 — `depth = map.ushort@0x12 - (x+y)*100`.

## 8. Open questions / risks
- **Route-opener / ownership nuance in `HasMatchingTransportPath`:** the owner-comparison
  branch (0x7DB4F0-0x7DB524) calls a city/player lookup (`0x7D3FFC`, `0x821320`) to allow
  cross-owner connections in some cases; I confirmed the two final accept conditions
  (`IsConnectable&&IsConnectable` and `hasRoute&&hasRoute`) but did not fully decode the
  cross-owner gating. For static-board rendering, using `(both connectable) OR (both
  hasRoute)` should match the visible result in the common case; verify against a sample with
  enemy-adjacent roads.
- **Route visibility precondition:** `ShouldShow` requires `container.visible` and
  `IsRouteOpener` for the route (non-road) path. `container.visible` is set by `SetVisible`,
  driven by Tile.Render's explored/hidden logic — confirm the implementer sets routes visible
  only on explored, non-hidden tiles.
- **Skin suffix naming:** confirmed `_magma` variants exist for routes (and the code appends
  `"_" + skinName`); roads have no `_magma` variants in the catalog, so a skinned road likely
  falls back to the plain `roads000N` sprite (DoSpriteLookup miss → base). Treat any
  `roads000N_<skin>` lookups as falling back to `roads000N`.
- **Bridge orientation source:** orientation is persisted in `ImprovementState.level`, set at
  build time by `SetIsBridgeHorizontal`. A static GameState must carry that value; if absent,
  derive from `TileData.GetPossibleBridgeDirection` (0x7DC770) — NW/SE neighbours ⇒ vertical
  (`bridge`), NE/SW ⇒ horizontal (`bridge-flipped`). Not fully decoded; mark as guess.
- **Fog depth slot:** the `fogOfWarRenderer` reuses the terrain sub-depth (it replaces terrain
  at the same origin). I did not see a distinct sort offset for fog; assume it sorts with
  terrain (sub-depth 1). Low risk since hidden tiles draw essentially nothing else.
- **Sign of depth:** `GetDepthForTile` produces `mapConst - (x+y)*100` (decreasing with row),
  opposite sign to the brief's `y*100` shorthand. Relative ordering is unchanged; just keep
  the `+2` transport offset consistent with whatever sign convention the implementer adopts.
