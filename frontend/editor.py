"""In-memory board editor session: GameState + brush + apply."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PY = os.path.join(_ROOT, "pyrender_UPDATED")
if _PY not in sys.path:
    sys.path.insert(0, _PY)

import gamestate as GS  # noqa: E402
import projection as P  # noqa: E402
import render as R  # noqa: E402
from enums import Improvement, Resource, Terrain, Tribe  # noqa: E402
from image import Image as RImage  # noqa: E402

try:
    from .catalog import build_catalog, unit_max_health
except ImportError:
    from catalog import build_catalog, unit_max_health  # noqa: E402

DEFAULT_STATE = os.path.join(_PY, "replayextractor", "state.json")
OMNISCIENT = 0xFF
PAD = 200
JPEG_QUALITY = 80

_LAND = frozenset({
    int(Terrain.FIELD), int(Terrain.MOUNTAIN), int(Terrain.FOREST),
    int(Terrain.ICE), int(Terrain.WETLAND), int(Terrain.MANGROVE),
})


@dataclass
class Modification:
    category: Optional[str] = None  # terrain|improvement|resource|road|unit
    value: Optional[int] = None  # enum id, or None when remove=True
    remove: bool = False

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "value": self.value,
            "remove": self.remove,
        }

    def describe(self) -> str:
        if not self.category:
            return "None selected"
        if self.remove:
            return f"Remove {self.category}"
        if self.category == "road":
            return "Place road"
        name = None
        try:
            if self.category == "terrain":
                name = Terrain(self.value).name
            elif self.category == "improvement":
                name = Improvement(self.value).name
            elif self.category == "resource":
                name = Resource(self.value).name
            elif self.category == "unit":
                from enums import Unit
                name = Unit(self.value).name
        except Exception:
            name = None
        if name:
            return f"Set {self.category}: {name.replace('_', ' ').title()}"
        return f"Set {self.category} = {self.value}"


def _encode_jpeg(img: RImage, quality: int = JPEG_QUALITY) -> bytes:
    """Opaque JPEG — much faster / smaller than PNG for interactive previews."""
    from PIL import Image as PILImage
    pil = img.to_pil()
    if pil.mode == "RGBA":
        bg = PILImage.new("RGB", pil.size, (15, 19, 24))
        bg.paste(pil, mask=pil.split()[3])
        pil = bg
    elif pil.mode != "RGB":
        pil = pil.convert("RGB")
    buf = BytesIO()
    pil.save(buf, format="JPEG", quality=quality, optimize=False)
    return buf.getvalue()


class EditorSession:
    def __init__(self, state_path: Optional[str] = None):
        path = state_path or DEFAULT_STATE
        self.state_path = path
        self.gs = GS.load(path)
        self.selected_player_id = self._default_player_id()
        self.modification = Modification()
        self.catalog = build_catalog()
        self._live = R.LiveBoard(self.gs, pad=PAD, player_id=OMNISCIENT)
        self._board_cache: Optional[Tuple[bytes, dict]] = None
        self._board_dirty = True

    def _default_player_id(self) -> int:
        for p in self.gs.player_states:
            if p.id not in (GS.PlayerState.NO_PLAYER_ID, GS.PlayerState.NATURE_PLAYER_ID):
                return p.id
        return GS.PlayerState.NO_PLAYER_ID

    def reload(self, path: Optional[str] = None) -> None:
        if path:
            self.state_path = path
        self.gs = GS.load(self.state_path)
        self.selected_player_id = self._default_player_id()
        self._live = R.LiveBoard(self.gs, pad=PAD, player_id=OMNISCIENT)
        self._invalidate()

    def _invalidate(self) -> None:
        self._board_dirty = True
        self._board_cache = None

    def players(self) -> List[dict]:
        from tribecolors import get_tribe_rgb

        out = []
        for p in self.gs.player_states:
            if p.id == GS.PlayerState.NO_PLAYER_ID:
                continue
            r, g, b = get_tribe_rgb(p.tribe, p.skin_type)
            try:
                tribe_name = Tribe(p.tribe).name
            except ValueError:
                tribe_name = str(p.tribe)
            out.append({
                "id": p.id,
                "user_name": p.user_name or f"Player {p.id}",
                "tribe": p.tribe,
                "tribe_name": tribe_name,
                "skin_type": p.skin_type,
                "color": f"#{r:02x}{g:02x}{b:02x}",
            })
        return out

    def set_player(self, player_id: int) -> None:
        if not any(p.id == player_id for p in self.gs.player_states):
            raise ValueError(f"unknown player_id {player_id}")
        self.selected_player_id = int(player_id)

    def set_modification(
        self,
        category: Optional[str],
        value: Optional[int] = None,
        remove: bool = False,
    ) -> None:
        if category is None:
            self.modification = Modification()
            return
        allowed = {"terrain", "improvement", "resource", "road", "unit"}
        if category not in allowed:
            raise ValueError(f"unknown category {category}")
        if remove:
            self.modification = Modification(category=category, value=None, remove=True)
            return
        if category == "road":
            self.modification = Modification(category="road", value=1, remove=False)
            return
        if value is None:
            raise ValueError("value required unless remove=true")
        self.modification = Modification(
            category=category, value=int(value), remove=False
        )

    def apply(self, x: int, y: int) -> dict:
        tile = self.gs.map.tile_at(x, y)
        if tile is None:
            raise ValueError(f"tile ({x},{y}) out of bounds")
        mod = self.modification
        if not mod.category:
            raise ValueError("no modification selected")

        if mod.category == "terrain":
            self._apply_terrain(tile, mod)
        elif mod.category == "improvement":
            self._apply_improvement(tile, mod)
        elif mod.category == "resource":
            self._apply_resource(tile, mod)
        elif mod.category == "road":
            self._apply_road(tile, mod)
        elif mod.category == "unit":
            self._apply_unit(tile, mod)
        else:
            raise ValueError(f"unknown category {mod.category}")

        self._live.bind(self.gs)
        self._invalidate()
        return {"ok": True, "x": x, "y": y, "modification": mod.to_dict()}

    def _selected_player(self) -> Optional[GS.PlayerState]:
        return self.gs.player_by_id(self.selected_player_id)

    def _is_land(self, x: int, y: int) -> bool:
        t = self.gs.map.tile_at(x, y)
        return t is not None and t.terrain in _LAND

    def _refresh_shoreline_tile(self, tile: GS.TileData) -> None:
        tile.shorelines = GS.Shorelines()
        if tile.terrain != int(Terrain.WATER):
            return
        if tile.climate == int(Tribe.POLARIS):
            return
        x, y = tile.x, tile.y
        n = self._is_land(x, y + 1)
        s = self._is_land(x, y - 1)
        e = self._is_land(x + 1, y)
        w = self._is_land(x - 1, y)
        tile.shorelines = GS.Shorelines(
            any=n or s or e or w,
            N=GS.Shoreline(visible=n),
            S=GS.Shoreline(visible=s),
            E=GS.Shoreline(visible=e),
            W=GS.Shoreline(visible=w),
        )

    def _refresh_shorelines_near(self, x: int, y: int) -> None:
        """Only recompute shorelines for the painted tile and orthogonal neighbours."""
        for cx, cy in R.neighbour_coords([(x, y)], orth_only=True):
            t = self.gs.map.tile_at(cx, cy)
            if t is not None:
                self._refresh_shoreline_tile(t)

    def _apply_terrain(self, tile: GS.TileData, mod: Modification) -> None:
        if mod.remove:
            tile.terrain = int(Terrain.NONE)
        else:
            tile.terrain = int(mod.value)
        self._refresh_shorelines_near(tile.x, tile.y)

    def _apply_improvement(self, tile: GS.TileData, mod: Modification) -> None:
        if mod.remove:
            if tile.improvement and tile.improvement.type == int(Improvement.CITY):
                tile.capital_of = 0
            tile.improvement = None
            return
        imp_type = int(mod.value)
        player = self._selected_player()
        owner = player.id if player else 0
        if imp_type == int(Improvement.CITY):
            tile.improvement = GS.ImprovementState(
                type=imp_type,
                level=1,
                name="City",
                founder=owner,
                owner=owner,
            )
            tile.owner = owner
            tile.capital_of = owner
        else:
            tile.improvement = GS.ImprovementState(
                type=imp_type,
                level=1,
                founder=owner,
                owner=owner,
            )

    def _apply_resource(self, tile: GS.TileData, mod: Modification) -> None:
        if mod.remove:
            tile.resource = None
            return
        tile.resource = GS.ResourceState(type=int(mod.value))

    def _apply_road(self, tile: GS.TileData, mod: Modification) -> None:
        tile.has_road = not mod.remove

    def _apply_unit(self, tile: GS.TileData, mod: Modification) -> None:
        if mod.remove:
            tile.unit = None
            return
        player = self._selected_player()
        if player is None:
            raise ValueError("select a player before placing a unit")
        utype = int(mod.value)
        self.gs.current_unit_id = int(self.gs.current_unit_id) + 1
        health = unit_max_health(utype)
        tile.unit = GS.UnitState(
            id=self.gs.current_unit_id,
            owner=player.id,
            birth_climate=player.tribe or player.climate,
            birth_climate_skin_type=player.skin_type,
            type=utype,
            coordinates=GS.WorldCoordinates(tile.x, tile.y),
            previous_turn_end_coordinates=GS.WorldCoordinates(tile.x, tile.y),
            home=GS.WorldCoordinates(tile.x, tile.y),
            health=health,
        )

    def _meta_from_live(self, img: RImage) -> dict:
        live = self._live
        centers = {}
        for t in live._tiles:
            ax, ay = live.frame.anchor(t.x, t.y)
            centers[f"{t.x},{t.y}"] = [
                round(ax + live._off_x),
                round(ay + live._off_y),
            ]
        return {
            "tile_centers": centers,
            "tile_size": int(P.HALF_W),
            "half_w": int(P.HALF_W),
            "half_h": round(float(P.HALF_H), 3),
            "image_w": img.w,
            "image_h": img.h,
            "map_width": self.gs.map.width,
            "map_height": self.gs.map.height,
            "format": "jpeg",
        }

    def board_image_and_meta(self) -> Tuple[bytes, dict]:
        if self._board_cache is not None and not self._board_dirty:
            return self._board_cache

        if not self._live._bg_cache:
            img = self._live.render()
        else:
            img = self._live.refresh_move()
        data = _encode_jpeg(img)
        meta = self._meta_from_live(img)
        self._board_cache = (data, meta)
        self._board_dirty = False
        return data, meta

    def board_png_and_meta(self) -> Tuple[bytes, dict]:
        """Alias kept for callers; payload is JPEG now."""
        return self.board_image_and_meta()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "players": self.players(),
            "selected_player_id": self.selected_player_id,
            "modification": self.modification.to_dict(),
            "modification_label": self.modification.describe(),
            "catalog": self.catalog,
            "state_path": self.state_path,
            "map_width": self.gs.map.width,
            "map_height": self.gs.map.height,
        }
