"""Isometric board renderer — mirrors MapRenderer + Tile.Render (PolytopiaAssembly)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from .enums import (
    TRIBE_SKIN_SUFFIX,
    ImprovementType,
    ResourceType,
    TerrainType,
    UnitType,
    climate_skin,
)
from .game_state import GameState, PlayerState, TileData, WorldCoordinates
from .map_extensions import (
    HOUSES_SORT_OFFSET,
    WALLS_SORT_OFFSET,
    RESOURCES_OUTLINE_SORT_OFFSET,
    RESOURCES_SORT_OFFSET,
    TERRAIN_FEATURE_SORT_OFFSET,
    TERRAIN_SORT_OFFSET,
    TILE_WIDTH,
    TRANSPORT_SORT_OFFSET,
    WORLD_OBJECT_SORT_OFFSET,
    get_depth_for_tile,
    to_position,
)
from .sprite_metadata import GROUND_PIXELS_PER_UNIT, get_sprite_meta, pad_to_logical

DEFAULT_SPRITE_DIR = Path(__file__).resolve().parent.parent / "sprites"
PIXELS_PER_UNIT = 256.0 / TILE_WIDTH  # sprite 256px ≈ one TILE_WIDTH world unit
# Prefab local Y on Terrain (Unity Y-up → subtract for screen y-down).
FOREST_LOCAL_Y = 0.7069
MOUNTAIN_LOCAL_Y = 0.0821


@dataclass(order=True)
class DrawLayer:
    sort_key: int
    sub: int
    image: Image.Image = field(compare=False)
    px: int = field(compare=False)
    py: int = field(compare=False)


UNIT_ICON: dict[UnitType, str] = {
    UnitType.Warrior: "warrior_icon.png",
    UnitType.Swordsman: "swordsman_icon.png",
    UnitType.Defender: "defender_icon.png",
    UnitType.Archer: "archer_icon.png",
    UnitType.Scout: "warrior_icon.png",
    UnitType.Rider: "warrior_icon.png",
    UnitType.Knight: "swordsman_icon.png",
}


class SpriteCache:
    def __init__(self, sprite_dir: Path):
        self.sprite_dir = sprite_dir
        self._images: dict[str, Optional[Image.Image]] = {}
        self._pivots: dict[str, tuple[float, float]] = {}
        self._ppu: dict[str, float] = {}

    def get(self, name: str) -> Optional[Image.Image]:
        if name not in self._images:
            path = self.sprite_dir / name
            raw = Image.open(path).convert("RGBA") if path.is_file() else None
            if raw is None:
                self._images[name] = None
            else:
                meta = get_sprite_meta(name.replace(".png", ""))
                if meta is not None:
                    self._images[name] = pad_to_logical(raw, meta)
                    self._pivots[name] = meta.pivot_pil
                    self._ppu[name] = meta.pixels_per_unit
                else:
                    self._images[name] = raw
                    self._pivots[name] = _sprite_pivot_bottom_center(raw)
                    self._ppu[name] = GROUND_PIXELS_PER_UNIT
        img = self._images[name]
        return img.copy() if img is not None else None

    def pivot(self, name: str) -> tuple[float, float]:
        self.get(name)
        return self._pivots.get(name, (0.0, 0.0))

    def pixels_per_unit(self, name: str) -> float:
        self.get(name)
        return self._ppu.get(name, GROUND_PIXELS_PER_UNIT)


def _sprite_pivot_bottom_center(img: Image.Image) -> tuple[float, float]:
    """Bottom-center of opaque pixels — isometric tile foot (Unity pivot)."""
    alpha = np.array(img)[:, :, 3]
    rows = np.where(alpha.max(axis=1) > 8)[0]
    if len(rows) == 0:
        w, h = img.size
        return w // 2, h - 1
    bottom = int(rows[-1])
    cols = np.where(alpha[bottom] > 8)[0]
    if len(cols) == 0:
        w, _ = img.size
        return w // 2, bottom
    return int((cols[0] + cols[-1]) // 2), bottom


def tribe_skin(player: Optional[PlayerState]) -> str:
    if player is None:
        return "imperius"
    return TRIBE_SKIN_SUFFIX.get(player.tribe, "imperius")


def tile_skin(state: GameState, tile: TileData) -> str:
    """Match SkinVisualsTransientData.SetupForTile: owner tribe, else climate style."""
    if tile.owner:
        p = state.try_get_player(tile.owner)
        if p:
            return tribe_skin(p)
    return climate_skin(tile.climate)


class BoardRenderer:
    def __init__(
        self,
        sprite_dir: Path | str = DEFAULT_SPRITE_DIR,
        pixels_per_unit: float = PIXELS_PER_UNIT,
        viewing_player_id: int = 1,
    ):
        self.sprite_dir = Path(sprite_dir)
        self.ppu = pixels_per_unit
        self.viewing_player_id = viewing_player_id
        self.sprites = SpriteCache(self.sprite_dir)
        self.layers: list[DrawLayer] = []

    def render(self, state: GameState) -> Image.Image:
        self.layers.clear()
        m = state.map
        if not m.tiles:
            return Image.new("RGBA", (64, 64), (26, 34, 46, 255))

        # Back → front: increasing (x+y); depth sort uses (x+y)*100 (see get_depth_for_tile).
        for y in range(m.height):
            for x in range(m.width):
                tile = m.get_tile_xy(x, y)
                if tile is not None:
                    self._render_tile(state, tile)

        return self._compose(state)

    def _world_to_pixel(self, wx: float, wy: float) -> tuple[int, int]:
        """Unity world → PIL. Map uses y-down screen space (0,0 at top of diamond)."""
        return int(round(wx * self.ppu)), int(round(wy * self.ppu))

    def _compose(self, state: GameState) -> Image.Image:
        m = state.map
        if not self.layers:
            return Image.new("RGBA", (64, 64), (26, 34, 46, 255))

        xs, ys = [], []
        for y in range(m.height):
            for x in range(m.width):
                wx, wy = to_position(WorldCoordinates(x, y))
                px, py = self._world_to_pixel(wx, wy)
                xs.append(px)
                ys.append(py)

        pad = int(self.ppu * 1.5)
        min_px, max_px = min(xs), max(xs)
        min_py, max_py = min(ys), max(ys)
        canvas = Image.new(
            "RGBA",
            (max_px - min_px + pad * 2, max_py - min_py + pad * 2),
            (0x1A, 0x22, 0x2E, 255),
        )
        ox, oy = -min_px + pad, -min_py + pad

        self.layers.sort()
        for layer in self.layers:
            canvas.alpha_composite(layer.image, (layer.px + ox, layer.py + oy))

        return canvas

    def _sprite_scale(self, sprite_name: str, extra: float = 1.0) -> float:
        """Unity draws sprites at pixel_size / sprite.pixelsPerUnit world units."""
        return (self.ppu / self.sprites.pixels_per_unit(sprite_name)) * extra

    def _apply_scale(
        self, img: Image.Image, pvx: float, pvy: float, scale: float,
    ) -> tuple[Image.Image, float, float]:
        if abs(scale - 1.0) < 1e-6:
            return img, pvx, pvy
        w, h = img.size
        img = img.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))), Image.Resampling.LANCZOS)
        return img, pvx * scale, pvy * scale

    def _queue_sprite(
        self,
        state: GameState,
        coords: WorldCoordinates,
        sprite_name: str,
        layer: int,
        sub: int = 0,
        foot_offset: tuple[float, float] = (0.0, 0.0),
        scale: float = 1.0,
    ) -> None:
        img = self.sprites.get(sprite_name)
        if img is None:
            return
        pvx, pvy = self.sprites.pivot(sprite_name)
        display_scale = self._sprite_scale(sprite_name, scale)
        img, pvx, pvy = self._apply_scale(img, pvx, pvy, display_scale)

        wx, wy = to_position(coords)
        wx += foot_offset[0]
        wy += foot_offset[1]
        fx, fy = self._world_to_pixel(wx, wy)

        depth = get_depth_for_tile(state.map, coords, layer)
        self.layers.append(
            DrawLayer(
                sort_key=depth,
                sub=sub,
                image=img,
                px=int(round(fx - pvx)),
                py=int(round(fy - pvy)),
            )
        )

    def _feature_world_offset(self, feature_name: str) -> tuple[float, float]:
        """Offset from ground (Terrain) origin — prefab localPosition of feature renderers."""
        if "Forest_" in feature_name:
            return 0.0, -FOREST_LOCAL_Y
        if "mountain_" in feature_name:
            return 0.0, -MOUNTAIN_LOCAL_Y
        return 0.0, 0.0

    def _queue_feature_on_ground(
        self,
        state: GameState,
        coords: WorldCoordinates,
        ground_name: str,
        feature_name: str,
        layer: int,
    ) -> None:
        """Place forest/mountain using Unity sprite pivot, PPU, and prefab offset."""
        ox, oy = self._feature_world_offset(feature_name)
        self._queue_sprite(
            state, coords, feature_name, layer, foot_offset=(ox, oy),
        )

    def _is_hidden(self, tile: TileData) -> bool:
        if not tile.explorers:
            return False
        return self.viewing_player_id not in tile.explorers

    def _ground_sprite(self, skin: str) -> str:
        return f"ground_{skin}.png"

    def _feature_sprite(self, tile: TileData, skin: str) -> Optional[str]:
        if tile.terrain == TerrainType.Forest:
            return f"Forest_{skin}.png"
        if tile.terrain == TerrainType.Mountain:
            return f"mountain_{skin}.png"
        return None

    def _exclusive_terrain_sprite(self, tile: TileData, skin: str) -> Optional[str]:
        t = tile.terrain
        if t == TerrainType.Ocean:
            return "ocean.png"
        if t == TerrainType.Water:
            return "water.png"
        if t == TerrainType.Ice:
            return "ground_polaris.png"
        return None

    def _render_tile(self, state: GameState, tile: TileData) -> None:
        if self._is_hidden(tile):
            return
        skin = tile_skin(state, tile)
        self._render_terrain(state, tile, skin)
        self._render_shorelines(state, tile)
        self._render_resource(state, tile, skin)
        self._render_improvement(state, tile, skin)
        self._render_unit(state, tile, skin)

    def _render_terrain(self, state: GameState, tile: TileData, skin: str) -> None:
        exclusive = self._exclusive_terrain_sprite(tile, skin)
        if exclusive:
            self._queue_sprite(state, tile.coordinates, exclusive, TERRAIN_SORT_OFFSET)
            return

        ground = self._ground_sprite(skin)
        self._queue_sprite(state, tile.coordinates, ground, TERRAIN_SORT_OFFSET)

        feature = self._feature_sprite(tile, skin)
        if feature:
            self._queue_feature_on_ground(
                state, tile.coordinates, ground, feature, TERRAIN_FEATURE_SORT_OFFSET,
            )

    def _render_shorelines(self, state: GameState, tile: TileData) -> None:
        if not tile.shorelines.any_visible:
            return
        coords = tile.coordinates
        for shoreline, sprite in (
            (tile.shorelines.s, "water_wall_left.png"),
            (tile.shorelines.n, "water_wall_right.png"),
            (tile.shorelines.w, "water_wall_left.png"),
            (tile.shorelines.e, "water_wall_right.png"),
        ):
            if shoreline.visible:
                self._queue_sprite(state, coords, sprite, TERRAIN_SORT_OFFSET, sub=1)

    def _render_resource(self, state: GameState, tile: TileData, skin: str) -> None:
        if not tile.resource or tile.resource.type == ResourceType.None_:
            return
        rt = tile.resource.type
        if rt == ResourceType.Fruit:
            body = f"ResourceGFX_fruit_{skin}.png"
        elif rt == ResourceType.Crop:
            body = "ResourceGFX_crop.png"
        elif rt == ResourceType.Fish:
            body = "ResourceGFX_fish.png"
        else:
            body = "ResourceGFX_crop.png"
        outline = body.replace(".png", "_Outline.png")
        self._queue_sprite(state, tile.coordinates, outline, RESOURCES_OUTLINE_SORT_OFFSET)
        self._queue_sprite(state, tile.coordinates, body, RESOURCES_SORT_OFFSET)

    def _render_improvement(self, state: GameState, tile: TileData, skin: str) -> None:
        imp = tile.improvement
        if not imp or imp.type == ImprovementType.None_:
            return
        coords = tile.coordinates
        if imp.type == ImprovementType.City:
            level = max(1, min(int(imp.level), 5))
            self._queue_sprite(state, coords, f"House_{level}_{skin}.png", HOUSES_SORT_OFFSET, sub=0)
            self._queue_sprite(
                state, coords, f"roof_{skin}.png", WALLS_SORT_OFFSET, sub=0, foot_offset=(0.0, 0.04),
            )

    def _render_unit(self, state: GameState, tile: TileData, skin: str) -> None:
        unit = tile.unit
        if not unit or unit.type == UnitType.None_:
            return
        icon = UNIT_ICON.get(unit.type, "warrior_icon.png")
        self._queue_sprite(
            state, tile.coordinates, icon, WORLD_OBJECT_SORT_OFFSET, sub=0,
            foot_offset=(0.0, 0.05), scale=2.0,
        )


def render_game_state(
    state: GameState,
    output_path: Path | str,
    sprite_dir: Path | str = DEFAULT_SPRITE_DIR,
    pixels_per_unit: float = PIXELS_PER_UNIT,
    viewing_player_id: int = 1,
) -> Path:
    renderer = BoardRenderer(
        sprite_dir=sprite_dir,
        pixels_per_unit=pixels_per_unit,
        viewing_player_id=viewing_player_id,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    renderer.render(state).save(output_path)
    return output_path
