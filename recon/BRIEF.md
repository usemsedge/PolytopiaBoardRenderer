# Polytopia Renderer Reconstruction — Shared Recon Brief

**Goal of the whole project:** a pure-Python function `render(GameState) -> Image`
that reproduces *pixel-faithfully* the real game's board rendering, compositing
the **real extracted sprites** using the **real decompiled rendering logic**.

You are ONE research agent owning ONE slice of the render pipeline. Produce a
precise, implementable spec. Another set of agents will implement Python from
your spec, so be exact: real constants, real algorithms, real sprite names.

## Working directory
`/Users/owfei/testing/biblical_greed` (everything below is relative to it).

## Key material
| Path | What |
|------|------|
| `il2cpp_dump/dump.cs` (38MB) | Class/field/method signatures + RVAs. **Grep here first.** |
| `il2cpp_dump/script.json` | Address→symbol map (reassembled) |
| `il2cpp_dump/stringliteral.json` | String constants |
| `GameAssembly_arm64.dylib` | Native bodies — disassemble for real algorithms |
| `polytopia_extracted/sprites/*.png` | 2051 real RGBA sprites |
| `pyrender/sprite_catalog.json` | `{name: {w,h}}` for all sprites |
| `pyrender/image.py` | Zero-dep imaging core (Image: load_png/save_png/paste/tinted/flipped_x) |
| `CONVERSATION_MAP_AND_RENDERING.md` | High-level pipeline map + RVA tables (Parts D/E) |
| `polytopia_map_rules.md` | Game rules for the map (terrain/resources/territory/etc.) |
| `board_from_game_assets.txt` | Tile attribute notation (terrain/resource/building codes) |

## Tools (all work; verified)
```bash
# symbol lookup, name->RVA, callees, capstone disassembly:
python3 tools/re_tools.py sym 0x2CC11AC
python3 tools/re_tools.py rng MapExtensions ToPosition
python3 tools/re_tools.py callees 0x2D4F6C0 [end]
python3 tools/re_tools.py disasm  0x2CC11AC [end]      # ARM64 via bundled capstone
# grep signatures:
grep -nE "class MapRenderer" il2cpp_dump/dump.cs
```
Disassembly tips: float immediates appear as `mov/movk` building a 32-bit pattern
then `fmov s,w`; decode the hex as IEEE-754. E.g. `0x3EF652BD`≈0.4811 (TILE_WIDTH_HALF),
`0x3E9374BC`≈0.288 (TILE_HEIGHT_HALF). Verify constants against the doc's Part E.3.

## Verified facts (build on these, don't re-derive)
- **Projection** (`MapExtensions$$ToPosition` @0x2CC11AC): world position from grid (x,y) =
  `posX = (x - y) * 0.4811`, `posY = (x + y) * 0.288`. (coords packed: low32=x, high32=y.)
- **MapRenderer constants** (dump.cs ~371960): TILE_WIDTH=0.9622, TILE_HEIGHT=0.576,
  TILE_WIDTH_HALF=0.4811, TILE_HEIGHT_HALF=0.288, TILE_VERTICAL_OFFSET=-0.223,
  DEPTH_INCREASE_PER_ROW=100.
- **Sub-layer sort offsets** (added to row depth `y*100`): 0 borders-back, 1 terrain,
  2 transport/world-object, 3 terrain-features, 4 resource-outline, 5 resources,
  6 houses, 97 walls, 98 buildings, 99 borders-front.
- **SpriteData name constants** (dump.cs ~374187): terrain bases `ground` (field),
  `mountain`, `Forest`, `water`, `ocean`, `ice`, `wetland`, `hidden`; resources
  `ResourceGFX_fruit/crop/fish/whale/metal/spores/starfish/aquacrop`, `animal`;
  improvements `Farm`,`Mine`,`Forge_1`,`Sawmill_1`,`Windmill_1`,`Market`/`MarketIcon`,
  `Port`,`Lumber Hut`,`ruin`,`Customs House_1`,`sanctuary_1`,`Temple_1`,`Water Temple_1`,
  `Mountain Temple_1`,`Forest Temple_1`,`Ice Temple_1`,`Road`,`atoll`,`iceport`,`icebank_icon`.
- **Terrain sprite theme suffix:** terrain art is per tribe/climate theme, e.g.
  `ground_imperius`, `mountain_bardur`, `Forest_kickoo`, plus skins `magma`,`swamp`,
  `darkelf`,`aibo`,`aimo`,`arty`,`mercenary`,`polaris`,`elyrion`,`cymanti`,`aquarion`,
  `quetzali`,`luxidoor`,`hoodrick`,`oumaji`,`vengir`,`xinxi`,`kickoo`. Determine the
  exact tribe→theme mapping and climate→theme rule from the code/assets.
- **Sprite format:** all PNGs are 8-bit RGBA, non-interlaced.

## Render pipeline (from the doc)
`GameState.Map → MapRenderer.RenderMap → per cell Tile.Render →
{RenderTerrain, RenderShorelines, RenderResource, RenderImprovement, RenderUnit,
RenderBorder, TransportContainer.Render, fog} → BatchSprites (depth-sorted composite)`.
Key RVAs: RenderMap 0x2D4F6C0, GetDepthForTile 0x2D507A4, Tile.Render 0x2CDC5DC,
RenderTerrain 0x2CDC828, RenderShorelines 0x2CDEB78, RenderImprovement 0x2CDCF60,
RenderUnit 0x2CDD620, BatchSprites 0x2CDE3CC, TerrainRenderer.UpdateGraphics 0x2CDBD9C,
SkinVisualsRenderer.SkinTile 0x2D9DF94, CityRenderer.RefreshCity 0x2CCC13C,
GetTerrainSprite (UIUtils) ~0x2C8D..., GetResourceSprite 0x2C8DC68,
GetImprovementSprite 0x2C8DCC8/0x2C8DDA0.

## What to deliver
Write `recon/<your-slice>.md` with EXACTLY these sections:
1. **Summary** — one paragraph.
2. **Constants** — every numeric constant with its decoded value + source (RVA/dump.cs line).
3. **Sprite selection** — given the relevant GameState fields, the exact rule mapping to
   sprite filename(s) in `polytopia_extracted/sprites/`. List concrete example filenames
   and confirm they exist in `sprite_catalog.json`.
4. **Geometry** — placement offsets, anchor/pivot, flip rules, pixel positioning relative to
   the tile's world position; how this layer's sub-depth fits the sort order.
5. **Algorithm** — step-by-step pseudocode an implementer can follow directly.
6. **Tint/color** — any per-player tint, outline, saturation, opacity (give formulas/palette).
7. **RVAs verified** — list with one-line note of what you confirmed by disassembly.
8. **Open questions / risks** — anything uncertain for the implementer.

Keep it tight and factual. Prefer confirmed disassembly over guesses; mark guesses as such.
Confirm every sprite name you cite actually exists in the catalog.
