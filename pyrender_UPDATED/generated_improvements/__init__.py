"""Procedural multi-sprite improvements (market, city, lighthouse).

Each module exposes ``build(ctx, tile) -> Optional[(Image, origin_x, origin_y)]``
returning a single composite and the SpriteContainer origin inside it.
"""
