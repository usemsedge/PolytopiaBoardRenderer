"""Canonical test scenes for verification. `python3 scenes.py` renders the
canonical example board re-themed across **all 16 tribes + all 16 skins** to
/tmp/scene_*.png (one PNG per theme) plus two montage sheets. Verifiers use these
as consistent inputs.

"Same map, every theme": we take recon/example_gamestate.json (the hand-built real
board) and re-theme it without touching its layout. Terrain art is themed by each
tile's `climate` (a Tribe value) + `skin`; cities/units/borders are themed by the
owning player's tribe/skin (see context.tile_theme / context.player_tribe_skin).
So a faithful re-theme just rewrites both: every tile's climate/skin and every
player's tribe/skin_type. DoSpriteLookup then resolves `base_<skin>` -> `base_<tribe>`
-> `base`, so a skin that lacks a given sprite falls back to its parent tribe's art.
"""
from __future__ import annotations
import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gamestate as GS
import render
import tribecolors as TC
from image import Image
from enums import Terrain, Improvement, Tribe, Skin, TRIBE_THEME, SKIN_THEME


# ---------------------------------------------------------------- theme tables
# The 16 playable tribes (TRIBE_THEME minus NATURE, which is a theme not a player).
TRIBES = [t for t in Tribe if t in TRIBE_THEME and t != Tribe.NATURE]

# skin -> parent tribe, from GameLogicData's tribe->special-skin table
# (tribecolors.TRIBE_SPECIAL_SKIN). All 16 playable tribes pair 1:1 with their special
# skin — including Cymanti<->Cute — so every skin resolves to a parent tribe directly.
_SKIN_TRIBE = {int(s): int(t) for t, s in TC.TRIBE_SPECIAL_SKIN.items()}

SKINS = sorted(SKIN_THEME, key=int)

# Smaller pad than a standalone render: 32 boards tile into montage sheets, so we
# want a tight transparent margin around each.
PAD = 80


# ----------------------------------------------------------------- base + retheme
def _base_state() -> GS.GameState:
    """The hand-built recon/example_gamestate.json (real tiles) — the shared layout."""
    here = os.path.dirname(os.path.abspath(__file__))
    return GS.load(os.path.join(os.path.dirname(here), "recon", "example_gamestate.json"))


def _place_corner_lighthouse(gs: GS.GameState) -> GS.GameState:
    """Put a LightHouse on the visually top corner of the isometric board.

    Render y is ``-(x+y)``, so the back vertex (max x+y) is the top of the PNG.
    Terrain is forced to water so the tower seats on a sea tile.
    """
    tile = max(gs.map.tiles, key=lambda t: t.x + t.y)
    tile.terrain = int(Terrain.WATER)
    tile.improvement = GS.ImprovementState(type=int(Improvement.LIGHTHOUSE))
    return gs


def _retheme(gs: GS.GameState, tribe: int, skin: int = 0) -> GS.GameState:
    """Deep-copy ``gs`` and re-theme every tile and player to (tribe, skin).

    Layout (terrain types, owners, improvements, units, fog) is untouched — only the
    theme keys change: tile.climate/tile.skin drive terrain art, player.tribe/
    player.skin_type drive cities/units/borders. color=0 lets the renderer derive
    each player's real game colour from its tribe/skin (GameLogicData.GetTribeColor).
    """
    gs = copy.deepcopy(gs)
    for t in gs.map.tiles:
        t.climate = int(tribe)
        t.skin = int(skin)
    for p in gs.player_states:
        p.tribe = int(tribe)
        p.skin_type = int(skin)
        p.color = 0
    return gs


def _tribe_scene(tribe: int):
    return lambda tribe=tribe: _place_corner_lighthouse(_retheme(_base_state(), tribe, 0))


def _skin_scene(skin: int):
    return lambda skin=skin: _retheme(_base_state(), _SKIN_TRIBE[int(skin)], skin)


# One scene per tribe, then one per skin. Names sort tribes before skins.
SCENES = {}
for _t in TRIBES:
    SCENES[f"tribe_{TRIBE_THEME[_t]}"] = (_tribe_scene(int(_t)), PAD)
for _s in SKINS:
    SCENES[f"skin_{SKIN_THEME[_s]}"] = (_skin_scene(int(_s)), PAD)


# ----------------------------------------------------------------------- montage
def _montage(images, cols: int) -> Image:
    """Tile ``images`` into a grid of ``cols`` columns; each cell is the max sprite
    size, every board bottom-aligned and horizontally centred in its cell."""
    if not images:
        return Image.new(1, 1, (0, 0, 0, 0))
    cw = max(im.w for im in images)
    ch = max(im.h for im in images)
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new(cols * cw, rows * ch, (0, 0, 0, 0))
    for i, im in enumerate(images):
        cx, cy = (i % cols) * cw, (i // cols) * ch
        sheet.paste(im, cx + (cw - im.w) // 2, cy + (ch - im.h))
    return sheet


def render_all(outdir="/tmp"):
    """Render every theme to its own PNG and assemble per-group montage sheets.

    Returns {name: (path, w, h)}; montage entries are keyed "all_tribes"/"all_skins".
    """
    paths = {}
    tribe_imgs, skin_imgs = [], []
    for name, (fn, pad) in SCENES.items():
        img = render.render(fn(), pad=pad)
        p = os.path.join(outdir, f"scene_{name}.png")
        img.save_png(p)
        paths[name] = (p, img.w, img.h)
        (tribe_imgs if name.startswith("tribe_") else skin_imgs).append(img)
        print(f"scene rendered: {name}")

    for group, imgs in (("all_tribes", tribe_imgs), ("all_skins", skin_imgs)):
        sheet = _montage(imgs, cols=4)
        p = os.path.join(outdir, f"scene_{group}.png")
        sheet.save_png(p)
        paths[group] = (p, sheet.w, sheet.h)
        print(f"tribe rendered: {group}")
    return paths


if __name__ == "__main__":
    for name, (p, w, h) in render_all().items():
        print(f"{name:16} {p}  {w}x{h}")
