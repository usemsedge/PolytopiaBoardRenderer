"""Build pyrender/sprite_catalog.json: {name: {w, h}} for every extracted sprite.

The catalog is the renderer's index of which sprites exist and at what pixel size
(``SpriteStore.exists`` / ``.size``). ``w``/``h`` are the dimensions of the trimmed
PNG on disk — the same image ``SpriteStore.get`` loads — because ``render.py`` scales
that loaded PNG by ``store.size(name)``. So we read each PNG's IHDR directly; no Unity
bundle needed. Run after re-extracting ``polytopia_extracted/sprites``.
"""
from __future__ import annotations
import glob, json, os, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITE_DIR = os.path.join(ROOT, "polytopia_extracted", "sprites")
DEST = os.path.join(ROOT, "pyrender", "sprite_catalog.json")

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


def png_size(path):
    """(width, height) from the PNG IHDR chunk, or None if not a PNG."""
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != _PNG_SIG or head[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", head[16:24])
    return w, h


def main():
    out = {}
    bad = 0
    for path in sorted(glob.glob(os.path.join(SPRITE_DIR, "*.png"))):
        name = os.path.splitext(os.path.basename(path))[0]
        dim = png_size(path)
        if dim is None:
            bad += 1
            continue
        out[name] = {"w": dim[0], "h": dim[1]}
    json.dump(out, open(DEST, "w"))
    print(f"catalogued {len(out)} sprites -> {DEST}" + (f" ({bad} unreadable)" if bad else ""))
    for s in ["cymanti_doomux_cute", "cymanti_centipede_head_cute", "shaman_cute",
              "ground_imperius", "House_1_cute", "weapon_sword"]:
        if s in out:
            print(f"  {s:28} {out[s]['w']}x{out[s]['h']}")


if __name__ == "__main__":
    main()
