"""Recover trimmed-PNG pivot registration for every Sprite in data.unity3d.

The extracted sprite PNGs are alpha-trimmed, but m_Pivot is normalized against the
sprite's ORIGINAL m_Rect. To place a trimmed PNG by its pivot we need the trim offset
(SpriteRenderData.textureRectOffset). We locate textureRect by scanning for a Rectf whose
(w,h) equals the trimmed PNG size, then read the following Vec2 as textureRectOffset, and
recompute the pivot in trimmed-PNG space (bottom-left origin). Writes pyrender/sprite_reg.json.
"""
from __future__ import annotations
import glob, json, os, sys, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unityfs import read_bundle
from unityserial import parse, Reader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "Polytopia.app/Contents/Resources/Data/data.unity3d")
# Themed sprites (per-tribe/skin heads, units, etc.) live in addressable bundles, NOT in
# data.unity3d. They must be registered too, or their pivots fall back to centre (0.5,0.5)
# and the parts (notably skinned heads) seat wrongly. Process every sprite bundle.
AA = os.path.join(ROOT, "Polytopia.app/Contents/Resources/Data/StreamingAssets/aa/StandaloneOSX")
BUNDLES = [BUNDLE] + sorted(glob.glob(os.path.join(AA, "sprites_assets_*.bundle")))


def read_sprite(raw, start, little):
    r = Reader(raw, little); r.o = start
    n = r.u32(); name = r.bytes(n).decode("utf-8", "replace"); r.align()
    rx, ry, rw, rh = r.f32(), r.f32(), r.f32(), r.f32()    # m_Rect (original size)
    r.f32(); r.f32()                                       # m_Offset
    r.f32(); r.f32(); r.f32(); r.f32()                     # m_Border
    ppu = r.f32()                                          # m_PixelsToUnits
    pvx, pvy = r.f32(), r.f32()                            # m_Pivot (norm in m_Rect)
    return name, (rw, rh), ppu, (pvx, pvy), r.o


def find_texture_rect_offset(raw, scan_from, scan_to, trimw, trimh, little):
    """Scan for a Rectf (x,y,w,h) with w~=trimw,h~=trimh; return the following Vec2 offset."""
    e = "<" if little else ">"
    for off in range(scan_from, min(scan_to, len(raw) - 24), 4):
        x, y, w, h = struct.unpack_from(e + "ffff", raw, off)
        if abs(w - trimw) <= 1.0 and abs(h - trimh) <= 1.0 and 0 <= x < 8192 and 0 <= y < 8192:
            ox, oy = struct.unpack_from(e + "ff", raw, off + 16)
            if -4096 < ox < 4096 and -4096 < oy < 4096:
                return (ox, oy)
    return None


def _register_from_bundle(path, cat, out):
    """Register trimmed pivots for every Sprite (213) in one bundle, into ``out``.
    Skips a sprite already registered (data.unity3d is processed first and wins ties)."""
    n_added = 0
    for nd, sf in read_bundle(path):
        if nd.path.endswith(".resS"):           # raw texture payload, not a SerializedFile
            continue
        try:
            m = parse(sf)
        except Exception:
            continue
        if not m.get("objects"):
            continue
        little = m["little"]
        for (pid, start, size, tid) in m["objects"]:
            if m["types"][tid][0] != 213:
                continue
            try:
                name, (rw, rh), ppu, (pvx, pvy), after = read_sprite(m["raw"], start, little)
            except Exception:
                continue
            if name not in cat or name in out:
                continue
            tw, th = cat[name]["w"], cat[name]["h"]
            off = find_texture_rect_offset(m["raw"], after, start + size, tw, th, little)
            if off is None or rw <= 0 or rh <= 0:
                continue
            ox, oy = off
            # pivot point in original-rect bottom-left coords, then relative to trimmed PNG
            px = pvx * rw - ox
            py = pvy * rh - oy
            out[name] = {"pivot": [round(px / tw, 5), round(py / th, 5)]}
            n_added += 1
    return n_added


def main():
    cat = json.load(open(os.path.join(ROOT, "pyrender", "sprite_catalog.json")))
    out = {}
    for path in BUNDLES:
        added = _register_from_bundle(path, cat, out)
        print(f"  {os.path.basename(path):40} +{added} sprites")
    dest = os.path.join(ROOT, "pyrender", "sprite_reg.json")
    json.dump(out, open(dest, "w"))
    print(f"registered {len(out)} sprites -> {dest}")
    for s in ["body_default", "head", "weapon_club", "bodytint_default", "weapon_sword",
              "unit_quiver", "unit_ship", "body_knight", "body_knighthorse"]:
        if s in out:
            print(f"  {s:20} pivot_trim={out[s]['pivot']}")


if __name__ == "__main__":
    main()
