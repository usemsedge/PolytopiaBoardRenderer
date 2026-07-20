# Implementation Brief — per-layer renderer modules

The backbone is built and **verified working**: projection, depth sort, real-sprite
compositing, climate theming, and the terrain layer (base + mountain/forest features
+ fog) all render correctly and tessellate pixel-perfectly. Your job: implement ONE
remaining layer as `pyrender/layer_<name>.py`, against the stable API below.

Working dir: `/Users/owfei/testing/biblical_greed`. Run python with
`PYTHONPATH` including `pyrender` (the existing tests do `sys.path.insert(0,"pyrender")`).
Pillow/numpy are NOT available — only the zero-dep core. Don't add dependencies.

## The contract
Create `pyrender/layer_<name>.py` exposing:
```python
def items(ctx, tile):
    """Return a list of Item tuples for this tile (or [])."""
```
where **Item = (layer_offset, sprite_name|None, left, top, tint|None, opacity, flip_x)**:
- `layer_offset`: a SORT_* constant from `enums.py` (controls stacking; see below).
- `sprite_name`: catalog sprite name (NO `.png`); the renderer skips names not in catalog.
- `left, top`: integer top-left paste position on the canvas.
- `tint`: `(r,g,b)` 0..255 multiply, or None.
- `opacity`: 0..1.
- `flip_x`: bool (horizontal flip).

Read `pyrender/layerlib.py` — use its helpers:
- `place_base(ctx, tile, name)` → diamond-centre anchor (full-tile base sprites).
- `place_planted(ctx, tile, name, foot=FEATURE_FOOT, dx=0, dy=0)` → horizontally centred,
  sprite bottom at anchor_y+foot (objects sitting on the tile). `dx/dy` nudge in px.
- `resolve(ctx, base, tribe, skin, level=-1, check_outline=False)` → (sprite_name|None, outline|None)
  reproduces DoSpriteLookup (tries `base_<skin>`, `base_<tribe>`, `base`, with optional `_<level>`).
- `ctx.frame.anchor(x,y)` → (px,py) world anchor pixel of a tile.

`ctx` (render.RenderContext) gives you:
- `ctx.store` (SpriteStore: `.exists(name)`, `.get(name)`, `.size(name)`),
- `ctx.gs` (GameState), `ctx.map` (MapData: `.tile_at(x,y)`, `.width`, `.height`),
- `ctx.is_hidden(tile)`, `ctx.tile_theme(tile)` → (tribe, skin),
- `ctx.player_color(pid)` → (r,g,b) or None, `ctx.player_tribe_skin(pid)` → (tribe, skin),
- `ctx._theme_pivot_cache` (don't touch).

SORT offsets (enums.py): SORT_BORDERS_BACK=0, SORT_TERRAIN=1, SORT_TRANSPORT=2,
SORT_TERRAIN_FEATURE=3, SORT_RESOURCE_OUTLINE=4, SORT_RESOURCE=5, SORT_HOUSES=6,
SORT_WALLS=97, SORT_BUILDINGS=98, SORT_BORDERS_FRONT=99, SORT_UNIT=98.

`layers.py` already auto-loads `layer_shorelines`, `layer_transport`, `layer_resources`,
`layer_borders`, `layer_improvements`, `layer_units` if present — just create your file.

## Enums & schema
`enums.py` has Terrain/Resource/Improvement/Unit/Tribe/Skin/TileEffect/UnitEffect/
GridDirection + TRIBE_THEME/SKIN_THEME maps. `gamestate.py` has the dataclasses
(TileData, UnitState, ImprovementState, ResourceState, PlayerState, MapData, GameState)
and `load(path)`. `recon/asset_map.json` has machine-readable enum→sprite tables.

## Your spec
Follow your slice's recon spec EXACTLY for sprite selection, sub-depth, tint, geometry:
your spec file is named in the task. Confirm every sprite name exists via `ctx.store.exists`.

## Testing (REQUIRED)
Build a small synthetic GameState exercising your layer and render it; SAVE a PNG to
`/tmp/layer_<name>.png` and VIEW it (Read the image) to confirm it looks right. Example:
```python
import sys; sys.path.insert(0,"pyrender")
import gamestate as GS, render
from enums import *
tiles=[GS.TileData(x=x,y=y,terrain=Terrain.FIELD,climate=7,explorers=[0]) for y in range(3) for x in range(3)]
# ... set your tile.resource/improvement/unit/owner/etc on some tiles ...
gs=GS.GameState(map=GS.MapData(3,3,tiles),
                players=[GS.PlayerState(id=0,tribe=7,color=0xFF0000FF),
                         GS.PlayerState(id=1,tribe=4,color=0xFFFF0000)])
render.render(gs, pad=120).save_png("/tmp/layer_x.png")
```
Also run the full example: `render.render(GS.load("recon/example_gamestate.json"), pad=200)`.

Anchoring/pivot is the known hard part: there's no pivot data, so calibrate visually
(adjust `foot`/`dx`/`dy`) until objects sit correctly on the tile. Document any constant
you tuned. Keep code clean and match the established terrain-layer style in `layers.py`.

Deliver the module file + a one-paragraph note of what you tuned and any open issues.
