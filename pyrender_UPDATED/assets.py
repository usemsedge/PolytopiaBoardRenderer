"""Sprite store: load extracted PNGs by name, with caching.

Independent of the per-layer recon specs — just wraps ``image.Image`` + the
generated ``sprite_catalog.json`` so renderer modules can ask for a sprite by
name and get a cached, optionally tinted/flipped ``Image``.
"""
from __future__ import annotations

import json
import os
from typing import Dict, Optional, Tuple

from image import Image

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
SPRITE_DIR = os.path.join(_ROOT, "polytopia_extracted", "sprites")
CATALOG_PATH = os.path.join(_HERE, "sprite_catalog.json")


class SpriteStore:
    def __init__(self, sprite_dir: str = SPRITE_DIR, catalog_path: str = CATALOG_PATH):
        self.sprite_dir = sprite_dir
        with open(catalog_path) as f:
            self.catalog: Dict[str, dict] = json.load(f)
        self._cache: Dict[str, Image] = {}
        self._tint_cache: Dict[Tuple[str, Tuple[int, int, int], float], Image] = {}

    def exists(self, name: str) -> bool:
        return name in self.catalog

    def size(self, name: str) -> Tuple[int, int]:
        m = self.catalog[name]
        return m["w"], m["h"]

    def get(self, name: str) -> Image:
        """Return the cached base sprite (callers must NOT mutate it)."""
        img = self._cache.get(name)
        if img is None:
            path = os.path.join(self.sprite_dir, name + ".png")
            if not os.path.isfile(path):
                raise KeyError(f"sprite not found: {name}")
            img = Image.load_png(path)
            self._cache[name] = img
        return img

    def try_get(self, *names: str) -> Optional[Image]:
        """First existing sprite among ``names`` (useful for fallbacks)."""
        for n in names:
            if n in self.catalog:
                return self.get(n)
        return None

    def ensure_scaled(self, name: str, w: int, h: int) -> str:
        """Create (once) a resized copy of ``name`` and register it under a private
        catalog name; return that name so layers can reference it like any sprite."""
        w, h = max(1, int(w)), max(1, int(h))
        key = f"{name}@{w}x{h}"
        if key not in self.catalog:
            base = self.get(name)
            self._cache[key] = base.resized(w, h)
            self.catalog[key] = {"w": w, "h": h}
        return key

    def get_tinted(self, name: str, rgb: Tuple[int, int, int], strength: float = 1.0) -> Image:
        key = (name, rgb, round(strength, 3))
        img = self._tint_cache.get(key)
        if img is None:
            img = self.get(name).tinted(rgb, strength)
            self._tint_cache[key] = img
        return img
